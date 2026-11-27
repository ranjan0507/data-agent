import json
import math
import threading
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
import duckdb

from backend.app.analytics.dataset_access import (
	DatasetFileError,
	get_dataset_path,
)
from backend.app.analytics.sql_validator import (
	DATASET_TABLE,
	SQLValidationError,
	validate_sql
)

from backend.app.db.models import Dataset

MAX_RESULT_ROWS=1000
MAX_RESPONSE_BYTES=4*1024*1024
QUERY_TIMEOUT_SECONDS=5

class SQLExecutionError(Exception):
	pass

class SQLQueryTimeoutError(SQLExecutionError):
	pass

def _json_value(value:Any)->Any:
	if isinstance(value,(datetime,date,time)):
		return value.isoformat()
	if isinstance(value,Decimal):
		value=float(value)
	if isinstance(value,float) and not math.isfinite(value):
		return None
	if isinstance(value,bytes):
		return value.decode("utf-8",errors="replace")
	if isinstance(value,list):
		return [_json_value(item) for item in value]
	if isinstance(value,tuple):
		return [_json_value(item) for item in value]
	if isinstance(value,dict):
		return {str(key):_json_value(item) for key,item in value.items()}
	if value is None or isinstance(value,(str,int,float,bool)):
		return value
	return str(value)

def _json_bytes(value:Any)->bytes:
	return json.dumps(
		value,
		ensure_ascii=False,
		allow_nan=False,
		separators=(",",":")
	).encode("utf-8")

def run_sql(dataset:Dataset, query:str)->dict[str,Any]:
	try:
		validated_sql=validate_sql(query)
		dataset_path=get_dataset_path(dataset)
	except (SQLValidationError,DatasetFileError) as exc:
		raise SQLExecutionError(str(exc)) from exc

	try:
		connection=duckdb.connect(
			":memory:",
			config={
				"memory_limit":"512MB",
				"threads":"1"
			}
		)
	except duckdb.Error as exc:
		raise SQLExecutionError("Could not initialize DuckDB.") from exc

	timed_out=threading.Event()
	lock=threading.Lock()
	connection_closed=False

	def interrupt_query()->None:
		nonlocal connection_closed
		with lock:
			if not connection_closed:
				timed_out.set()
				connection.interrupt()

	timer=threading.Timer(QUERY_TIMEOUT_SECONDS,interrupt_query)
	timer.start()
	try:
		connection.read_csv(str(dataset_path),auto_detect=True).create_view(
			"_dataset_source"
		)
		connection.execute(
			'CREATE TEMP TABLE "_dataset" AS SELECT * FROM "_dataset_source"' 
		)
		connection.execute('DROP VIEW "_dataset_source"')
		connection.execute("SET enable_external_access=false")
		cursor=connection.execute(validated_sql)
		if cursor.description is None:
			raise SQLExecutionError("The SQL query did not return tabular results.")
		response:dict[str,Any]={
			"columns":[description[0] for description in cursor.description],
			"column_types":[str(description[1]) for description in cursor.description],
			"rows":[],
			"returned_row_count":0,
			"truncated":False
		}
		current_size=len(_json_bytes(response))
		if current_size>MAX_RESPONSE_BYTES:
			raise SQLExecutionError(
				"Result metadata exceeds the response-size limit."
			)
		while True:
			row=cursor.fetchone()
			if row is None:
				break

			if response["returned_row_count"]>=MAX_RESULT_ROWS:
				response["truncated"]=True
				break
			json_row=_json_value(row)
			encoded_row=_json_bytes(json_row)
			next_count=response["returned_row_count"]+1
			seperator_size=1 if response["rows"] else 0
			count_size_increase = len(str(next_count))-len(
				str(response["returned_row_count"])
			)
			next_size=(
				current_size+seperator_size+len(encoded_row)+count_size_increase
			)
			if next_size>MAX_RESPONSE_BYTES:
				if not response["rows"]:
					raise SQLExecutionError(
						"A result row exceeds the response-size limit."
					)
				response["truncated"]=True
				break

			response["rows"].append(json_row)
			response["returned_row_count"]=next_count
			current_size=next_size

		if len(_json_bytes(response))>MAX_RESPONSE_BYTES:
			raise SQLExecutionError("Result exceeds the response-size limit.")
		return response
	except duckdb.Error as exc:
		if timed_out.is_set():
			raise SQLQueryTimeoutError(
				f"SQL execution exceeded {QUERY_TIMEOUT_SECONDS} seconds."
			) from exc
		raise SQLExecutionError("DuckDB could not execute the SQL query.")
	finally:
		timer.cancel()
		with lock:
			connection_closed=True
			connection.close()