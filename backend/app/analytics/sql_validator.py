from sqlglot import exp, parse
from sqlglot.errors import ParseError

DATASET_TABLE="_dataset"

_ALLOWED_QUERY_TYPES=(
	exp.Select,exp.Union,exp.Intersect,exp.Except
)

_ALLOWED_ANONYMOUS_FUNCTIONS={
	"date_diff",
	"date_part",
	"date_trunc",
	"regexp_matches",
	"regexp_replace",
	"strftime",
	"strptime"
}

class SQLValidationError(Exception):
	pass

def validate_sql(query:str)->str:
	if not query.strip():
		raise SQLValidationError("SQL query must not be empty.")
	try:
		statements=[
			statement
			for statement in parse(query,read="duckdb")
			if statement is not None
		]
	except ParseError as exc:
		raise SQLValidationError("SQL query could not be parsed.") from exc

	if len(statements)!=1:
		raise SQLValidationError("Exactly one SQL statement is allowed.")
	statement=statements[0]
	if not isinstance(statement,_ALLOWED_QUERY_TYPES):
		raise SQLValidationError("Only read-only SELECT queries are allowed.")

	cte_names={
		cte.alias_or_name.casefold()
		for cte in statement.find_all(exp.CTE)
	}

	for table in statement.find_all(exp.Table):
		if not isinstance(table.this,exp.Identifier):
			raise SQLValidationError("Table-valued functions are not allowed.")
		if table.catalog or table.db:
			raise SQLValidationError("Schema-qualified tables are not allowed.")
		table_name=table.name.casefold()
		if table_name!=DATASET_TABLE and table_name not in cte_names:
			raise SQLValidationError(
				"Queries may reference only the selected dataset."
			)

	for function in statement.find_all(exp.Anonymous):
		if function.name.casefold() not in _ALLOWED_ANONYMOUS_FUNCTIONS:
			raise SQLValidationError(
				f"SQL function '{function.name}' is not supported."
			)

	if any(isinstance(node,exp.Into) for node in statement.walk()):
		raise SQLValidationError("SELECT INTO is not allowed.")

	return statement.sql(dialect="duckdb")
