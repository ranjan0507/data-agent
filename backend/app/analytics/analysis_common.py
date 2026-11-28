from contextlib import contextmanager
from datetime import date,datetime,time
from decimal import Decimal
import math
from typing import Any, Generator

import duckdb
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from backend.app.analytics.dataset_access import DatasetFileError, get_dataset_path
from backend.app.db.models import Dataset

MAX_ANALYSIS_COLUMNS=50

NUMERIC_TYPES={
	"TINYINT","SMALLINT","INTEGER","BIGINT","HUGEINT","UTINYINT","USMALLINT"
	"UINTEGER","UBIGINT","FLOAT","DOUBLE","REAL","DECIMAL"
}

class AnalysisFunctionError(Exception):
	"""Expected, structured error from an analysis operation."""
	def __init__(self, code:str,message:str,details:list[dict[str,str]]|None=None):
		super().__init__(message)
		self.code=code
		self.message=message
		self.details=details or []

	def as_dict(self)->dict[str,Any]:
		return {
			"error":{
				"code":self.code,
				"message":self.message,
				"details":self.details
			}
		}

class AnalysisParameters(BaseModel):
	model_config=ConfigDict(extra="forbid")

class ColumnParameters(AnalysisParameters):
	columns:list[str]|None=None

	@field_validator("columns")
	@classmethod
	def validate_columns(cls,value:list[str]|None)->list[str]|None:
		if value is not None:
			if not value:
				raise ValueError("Provide at least one column.")
			if len(value)!=len(set(value)):
				raise ValueError("Column names must not contain duplicates.")
		return value

def validate_parameters(
		model:type[AnalysisParameters],
		values:dict[str,Any]
)->AnalysisParameters:
	try:
		return model.model_validate(values)
	except ValidationError as exc:
		details=[
			{
				"field":".".join(str(part) for part in error["loc"]),
				"message": error["msg"]
			}
			for error in exc.errors()
		]
		raise AnalysisFunctionError(
			"invalid_arguments",
			"Function arguments are invalid.",
			details
		) from exc


@contextmanager
def dataset_connection(dataset:Dataset)-> Generator[duckdb.DuckDBPyConnection]:
	try:
		path=get_dataset_path(dataset)
	except DatasetFileError as exc:
		raise AnalysisFunctionError("dataset_unavailable",str(exc)) from exc

	try:
		connection = duckdb.connect(
			":memory:",
			config={
				"memory_limit":"512MB",
				"threads":"1"
			}
		)
	except duckdb.Error as exc:
		raise AnalysisFunctionError(
			"analysis_unavailable",
			"Could not initialize DuckDB."
		) from exc

	try:
		connection.read_csv(str(path),auto_detect=True).create_view(
			"_analysis_dataset"
		)
		yield connection
	except duckdb.Error as exc:
		raise AnalysisFunctionError(
			"analysis_failed",
			"DuckDB could not execute the analysis."
		) from exc
	finally:
		connection.close()

def quote_identifier(name:str)->str:
	return '"'+name.replace('"','""')+'"'

def column_types(connection: duckdb.DuckDBPyConnection)->dict[str,str]:
	rows=connection.execute("DESCRIBE _analysis_dataset").fetchall()
	return {row[0]:str(row[1]) for row in rows}

def is_numeric(type_name:str)->bool:
	base_type=type_name.split("(",maxsplit=1)[0].upper()
	return base_type in NUMERIC_TYPES

def resolve_columns(
		available:dict[str,str],
		requested:list[str]|None,
		*,
		numeric_only: bool = False,
    	default_limit: int = MAX_ANALYSIS_COLUMNS,
    	max_columns: int = MAX_ANALYSIS_COLUMNS,
)->list[str]:
	if requested is None:
		selected=[
			name 
			for name, kind in available.items()
			if not numeric_only or is_numeric(kind)
		][:default_limit]
	else:
		selected=requested
		unknown=[name for name in selected if name not in available]
		if unknown:
			raise AnalysisFunctionError(
				"invalid_columns",
				"One or more requested columns do not exist.",
				[
					{
						"field":"columns",
						"message":name 
					}
					for name in unknown
				]
			)
	if len(selected)>max_columns:
		raise AnalysisFunctionError(
			"too_many_columns",
			f"Select no more than {max_columns} columns."
		)

	if numeric_only:
		non_numeric=[name for name in selected if not is_numeric(available[name])]
		if non_numeric:
			raise AnalysisFunctionError(
				"invalid_columns",
				"This function requires numeric columns.",
				[{
					"field":"columns",
					"message":name
				}
				for name in non_numeric
				]
			)
	return selected

def json_value(value,Any)->Any:
	if isinstance(value,(datetime,date,time)):
		return value.isoformat()
	if isinstance(value, Decimal):
		value = float(value)
	if isinstance(value, float) and not math.isfinite(value):
		return None
	if isinstance(value, bytes):
		value = value.decode("utf-8", errors="replace")
	if isinstance(value, str) and len(value) > 200:
		return value[:200] + "..."
	return value