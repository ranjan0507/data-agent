import math
import re
from datetime import date,datetime,time
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from backend.app.core.config import settings
from backend.app.db.models import Dataset

MAX_PREVIEW_ROWS=100
MAX_PROFILE_COLUMNS=50
MAX_TOP_VALUES=10
MAX_VALUE_LENGTH=200
STORED_FILENAME_PATTERN=re.compile(r"[0-9a-f]{32}\.csv")

NUMERIC_TYPE = {
    "TINYINT",
    "SMALLINT",
    "INTEGER",
    "BIGINT",
    "HUGEINT",
    "UTINYINT",
    "USMALLINT",
    "UINTEGER",
    "UBIGINT",
    "FLOAT",
    "DOUBLE",
    "REAL",
    "DECIMAL",
}

class DatasetProfileError(Exception):
	pass

def _dataset_path(dataset: Dataset)->Path:
	filename=dataset.stored_filename
	if not STORED_FILENAME_PATTERN.fullmatch(filename):
		raise DatasetProfileError("Dataset has an invalid stored filename.")
	stored_dir=Path(settings.storage_dir).resolve()
	path=(stored_dir/filename).resolve()
	if path.parent!=stored_dir or not path.is_file():
		raise DatasetProfileError("Dataset file was not found.")
	return path

def _quote_identifier(name:str)->str:
	return '"'+name.replace('"','""')+'"'


def _json_value(value:Any)->Any:
	if isinstance(value,(datetime,date,time)):
		return value.isoformat()
	if isinstance(value,Decimal):
		value=float(value)
	if isinstance(value,float) and not math.isfinite(value):
		return None
	if isinstance(value,bytes):
		value=value.decode("utf-8",errors="replace")
	if isinstance(value,str) and len(value)>MAX_VALUE_LENGTH:
		return value[:MAX_VALUE_LENGTH]+"..."
	return value

def _is_numeric(type_name:str)->bool:
	base_type=type_name.split("(",maxsplit=1)[0].upper()
	return base_type in NUMERIC_TYPE

def get_dataset_profile(dataset:Dataset)->dict[str,Any]:
	path=_dataset_path(dataset)
	connection=duckdb.connect(":memory:")
	try:
		relation=connection.read_csv(
			str(path),
			auto_detect=True,
			nullstr=""
		)
		relation.create_view("_profile_dataset")
		all_columns=relation.columns
		all_types=[str(column_type) for column_type in relation.types]
		selected_columns=all_columns[:MAX_PROFILE_COLUMNS]
		selected_types=all_types[:MAX_PROFILE_COLUMNS]
		row_count=connection.execute(
			"SELECT COUNT(*) FROM _profile_dataset"
		).fetchone()[0]
		quoted_columns=[_quote_identifier(name) for name in selected_columns]
		missing_sql=",".join(
			f"COUNT(*) FILTER (WHERE {column} IS NULL)"
			for column in quoted_columns
		)
		missing_counts=connection.execute(
			f"SELECT {missing_sql} FROM _profile_dataset"
		).fetchone()

		numeric_columns = [
			(name,type_name)
			for name,type_name in zip(selected_columns,selected_types)
			if _is_numeric(type_name)
		]
		numeric_summaries: dict[str,dict[str,Any]]={}
		if numeric_columns:
			expressions=[]
			for name,_ in numeric_columns:
				column=_quote_identifier(name)
				expressions.extend(
					[
						f"COUNT({column})",
						f"MIN({column})",
						f"MAX({column})",
						f"AVG({column})",
						f"MEDIAN({column})",
						f"STDDEV_SAMP({column})"
					]
				)
			values = connection.execute(
				f"SELECT {','.join(expressions)} FROM _profile_dataset"
			).fetchone()

			for index,(name,_) in enumerate(numeric_columns):
				offset=index*6
				numeric_summaries[name]={
					"count":values[offset],
					"min":_json_value(values[offset+1]),
					"max":_json_value(values[offset+2]),
					"mean":_json_value(values[offset+3]),
					"median":_json_value(values[offset+4]),
					"std_dev":_json_value(values[offset+5])
				}

		profile_columns: list[dict[str,Any]]=[]
		for index,(name,type_name) in enumerate(
			zip(selected_columns,selected_types)
		):
			column_profile: dict[str,Any]={
				"name":name,
				"type":type_name,
				"missing_count":missing_counts[index]
			}
			if name in numeric_summaries:
				column_profile["numeric_summary"]=numeric_summaries[name]
			elif type_name.upper() in {"VARCHAR","BOOLEAN"}:
				column=_quote_identifier(name)
				top_values=connection.execute(
					f"""
					SELECT CAST({column} AS VARCHAR), COUNT(*) AS frequency
					FROM _profile_dataset
					WHERE {column} IS NOT NULL
					GROUP BY {column}
					ORDER BY frequency DESC, 1 ASC
					LIMIT ?
					""",
					[MAX_TOP_VALUES]
				).fetchall()
				column_profile["top_values"]=[
					{
						"value":_json_value(value),
						"count":frequency
					}
					for value,frequency in top_values
				]
			profile_columns.append(column_profile)

		if all_columns:
			group_columns=", ".join(
				_quote_identifier(name) for name in all_columns
			)
			duplicate_row_count=connection.execute(
				f"""
				SELECT COALESCE(SUM(occurences-1),0)
				FROM(
					SELECT COUNT(*) AS occurences
					FROM _profile_dataset
					GROUP BY {group_columns}
					HAVING COUNT(*)>1
				) duplicate_groups
				"""
			).fetchone()[0]
		else:
			duplicate_row_count=0

		preview_columns=", ".join(quoted_columns)
		preview_rows=connection.execute(
			f"SELECT {preview_columns} FROM _profile_dataset LIMIT ?",
			[MAX_PREVIEW_ROWS]
		).fetchall()

		preview = [
			{
				name:_json_value(value)
				for name, value in zip(selected_columns,row)
			}
			for row in preview_rows
		]

		return {
			"row_count":row_count,
			"column_count":len(all_columns),
			"columns_truncated":len(all_columns)>MAX_PROFILE_COLUMNS,
			"columns":profile_columns,
			"duplicate_row_count":duplicate_row_count,
			"preview":preview,
			"preview_truncated":row_count>MAX_PREVIEW_ROWS
		}
	except duckdb.Error as exc:
		raise DatasetProfileError("Could not profile the dataset CSV.") from exc
	finally:
		connection.close()