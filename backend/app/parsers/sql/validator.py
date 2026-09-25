from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError as SqlglotParseError


class SqlValidationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


_FORBIDDEN = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Command,
    exp.TruncateTable,
)


def validate_sql(query: str) -> str:
    """Parse and validate a read-only SQL SELECT (DuckDB dialect). Returns normalized SQL."""
    text = query.strip().rstrip(";")
    if not text:
        raise SqlValidationError("Empty SQL query")

    try:
        statements = sqlglot.parse(text, read="duckdb")
    except SqlglotParseError as exc:
        raise SqlValidationError(f"SQL parse error: {exc}") from exc

    if not statements or statements[0] is None:
        raise SqlValidationError("Could not parse SQL")
    if len(statements) > 1:
        raise SqlValidationError("Only a single SQL statement is allowed")

    statement = statements[0]
    for node in statement.walk():
        if isinstance(node, _FORBIDDEN):
            raise SqlValidationError(
                f"Statement type not allowed: {type(node).__name__}"
            )

    if not isinstance(statement, (exp.Select, exp.Union, exp.Except, exp.Intersect)):
        # With clause wrapping select is still Select
        if not any(isinstance(n, exp.Select) for n in statement.walk()):
            raise SqlValidationError("Only SELECT queries are allowed")

    return statement.sql(dialect="duckdb")
