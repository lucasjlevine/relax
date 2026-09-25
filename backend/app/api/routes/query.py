from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings
from app.datasets.loader import DatasetError
from app.engine.executor import QueryError, execute_relalg, execute_sql_query
from app.models.schemas import QueryRequest, QueryResponse

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
        status = 400 if exc.code in {"parse_error", "compile_error", "validation_error"} else 400
        raise HTTPException(
            status_code=status,
            detail={"message": exc.message, "code": exc.code},
        ) from exc
