from typing import Any
import duckdb
from pydantic import Field

from backend.app.analytics.analysis_common import(
	AnalysisFunctionError,
	AnalysisParameters,
	column_types,
	dataset_connection,
	is_numeric,
	json_value,
	quote_identifier,
	resolve_columns,
	validate_parameters
)

from backend.app.db.models import Dataset

class DescriptiveStatisticsParameters(AnalysisParameters):
	columns:list[str]|None=Field(default=None,max_length=50)
	top_values_limit:int=Field(default=10,ge=1,le=10)

def run(dataset:Dataset, values:dict[str,Any])->dict[str,Any]:
	params=validate_parameters(DescriptiveStatisticsParameters,values)
	with dataset_connection(dataset) as connection:
		available=column_types(connection)
		selected=resolve_columns(available,params.columns)
		summaries:dict[str,Any]={}
		for name in selected:
			column=quote_identifier(name)
			if is_numeric(available[name]):
				row=connection.execute(
					f"""
                    SELECT
                        COUNT({column}),
                        COUNT(*) FILTER (WHERE {column} IS NULL),
                        MIN({column}),
                        MAX({column}),
                        AVG({column}),
                        MEDIAN({column}),
                        STDDEV_SAMP({column})
                    FROM _analysis_dataset
                    """
				).fetchone()
				summaries[name]={
					"type": "numeric",
                    "count": row[0],
                    "missing_count": row[1],
                    "min": json_value(row[2]),
                    "max": json_value(row[3]),
                    "mean": json_value(row[4]),
                    "median": json_value(row[5]),
                    "std_dev": json_value(row[6]),
				}
			else:
				counts = connection.execute(
                    f"""
                    SELECT COUNT(DISTINCT {column}),
                           COUNT(*) FILTER (WHERE {column} IS NULL)
                    FROM _analysis_dataset
                    """
                ).fetchone()
				top_values = connection.execute(
                    f"""
                    SELECT CAST({column} AS VARCHAR), COUNT(*) AS frequency
                    FROM _analysis_dataset
                    WHERE {column} IS NOT NULL
                    GROUP BY {column}
                    ORDER BY frequency DESC, 1 ASC
                    LIMIT ?
                    """,
                    [params.top_values_limit],
                ).fetchall()
				summaries[name] = {
                    "type": "categorical",
                    "distinct_count": counts[0],
                    "missing_count": counts[1],
                    "top_values": [
                        {"value": json_value(value), "count": count}
                        for value, count in top_values
                    ],
                }
	return {
		"columns":summaries,
		"columns_truncated":params.columns is None
		and len(available)>len(selected)
	}