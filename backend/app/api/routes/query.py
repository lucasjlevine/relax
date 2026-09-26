from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings
from app.datasets.loader import DatasetError
from app.datasets.ownership import owner_from_request
from app.engine.executor import QueryError, execute_relalg, execute_sql_query
from app.engine.type_coerce import infer_type_coercions
from app.models.schemas import (
    FormatRequest,
    FormatResponse,
    QueryRequest,
    QueryResponse,
    TypeChangeInfo,
)
from app.engine.messages import humanize_parse_error
from app.parsers.relalg.formatter import format_relalg_query
from app.parsers.relalg.parser import RelAlgParseError, parse_relalg
from app.parsers.relalg.statements import split_relalg_statements
from app.parsers.sql.validator import SqlValidationError, validate_sql
import sqlglot

router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query", response_model=QueryResponse)
def run_query(body: QueryRequest, request: Request) -> QueryResponse:
    settings = get_settings()
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)

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
            stmts = split_relalg_statements(body.query)
            if not stmts:
                raise QueryError("Query must not be empty", code="validation_error")
            nodes = [parse_relalg(body_text) for body_text, _label in stmts]

            type_changes: list[TypeChangeInfo] = []
            warnings: list[str] = []
            for rel_name, col_name, from_t, to_t in infer_type_coercions(nodes, group):
                try:
                    group = catalog.change_column_type(
                        group.id, rel_name, col_name, to_t, owner_id
                    )
                    type_changes.append(
                        TypeChangeInfo(
                            relation=rel_name,
                            column=col_name,
                            fromType=from_t,
                            toType=to_t,
                        )
                    )
                    warnings.append(
                        f"Converted {rel_name}.{col_name} from {from_t} to {to_t}"
                    )
                except DatasetError as exc:
                    warnings.append(
                        f"Could not convert {rel_name}.{col_name} to {to_t}: {exc}"
                    )

            result = execute_relalg(
                group,
                body.query,
                limit=limit,
                offset=body.offset,
                extra_warnings=warnings,
            )
            result.datasetId = group.id
            result.typeChanges = type_changes
            if warnings and result.results:
                result.results[0].warnings = list(
                    dict.fromkeys(result.results[0].warnings + warnings)
                )
            return result
        return execute_sql_query(group, body.query, limit=limit, offset=body.offset)
    except RelAlgParseError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "message": humanize_parse_error(str(exc)),
                "code": "parse_error",
            },
        ) from exc
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
            style = body.style if body.style in ("pretty", "dense") else "pretty"
            return FormatResponse(
                formatted=format_relalg_query(body.query, style=style)
            )
        validate_sql(body.query)
        statements = sqlglot.parse(body.query.strip().rstrip(";"), read="duckdb")
        pretty = body.style != "dense"
        formatted = statements[0].sql(dialect="duckdb", pretty=pretty)
        return FormatResponse(formatted=formatted)
    except (RelAlgParseError, SqlValidationError) as exc:
        message = getattr(exc, "message", str(exc))
        lang = body.language if body.language in ("relalg", "sql") else "relalg"
        raise HTTPException(
            status_code=400,
            detail={
                "message": humanize_parse_error(message, language=lang),
                "code": "parse_error",
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "message": humanize_parse_error(str(exc), language=body.language),
                "code": "format_error",
            },
        ) from exc
