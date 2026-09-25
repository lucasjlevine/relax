from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings
from app.datasets.loader import DatasetError
from app.engine.executor import QueryError, execute_relalg, execute_sql_query
from app.models.schemas import (
    FormatRequest,
    FormatResponse,
    QueryRequest,
    QueryResponse,
)
from app.parsers.relalg.formatter import format_relalg_query
from app.parsers.relalg.parser import RelAlgParseError
from app.parsers.sql.validator import SqlValidationError, validate_sql
import sqlglot

router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query", response_model=QueryResponse)
def run_query(body: QueryRequest, request: Request) -> QueryResponse:
    settings = get_settings()
    catalog = request.app.state.catalog

    if not body.query.strip():
        raise HTTPException(
            status_code=400,
            detail={"message": "Query must not be empty", "code": "validation_error"},
        )

    limit = min(body.limit, settings.max_rows)
    try:
        group = catalog.get(body.datasetId)
    except DatasetError as exc:
        raise HTTPException(
            status_code=404, detail={"message": str(exc), "code": "not_found"}
        ) from exc

    try:
        if body.language == "relalg":
            return execute_relalg(group, body.query, limit=limit, offset=body.offset)
        return execute_sql_query(group, body.query, limit=limit, offset=body.offset)
    except QueryError as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": exc.message, "code": exc.code},
        ) from exc


@router.post("/format", response_model=FormatResponse)
def format_query(body: FormatRequest) -> FormatResponse:
    if not body.query.strip():
        raise HTTPException(
            status_code=400,
            detail={"message": "Query must not be empty", "code": "validation_error"},
        )
    try:
        if body.language == "relalg":
            return FormatResponse(formatted=format_relalg_query(body.query))
        # SQL: pretty via sqlglot
        validate_sql(body.query)
        statements = sqlglot.parse(body.query.strip().rstrip(";"), read="duckdb")
        formatted = statements[0].sql(dialect="duckdb", pretty=True)
        return FormatResponse(formatted=formatted)
    except (RelAlgParseError, SqlValidationError) as exc:
        message = getattr(exc, "message", str(exc))
        raise HTTPException(
            status_code=400, detail={"message": message, "code": "parse_error"}
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail={"message": str(exc), "code": "format_error"}
        ) from exc
