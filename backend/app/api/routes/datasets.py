from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse

from app.datasets.group_format import format_group_text, parse_local_groups
from app.datasets.loader import DatasetError
from app.datasets.ownership import owner_from_request
from app.models.schemas import (
    AddColumnRequest,
    AddRelationRequest,
    BuildRelationRequest,
    ColumnInfo,
    DatasetDetail,
    DatasetListResponse,
    DatasetSummary,
    GroupPreviewResponse,
    GroupTextRequest,
    GroupTextResponse,
    RelationData,
    RelationInfo,
    RenameColumnRequest,
    RenameDatasetRequest,
    RenameRelationRequest,
    RowValuesRequest,
    SetRowsRequest,
)

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


def _detail_from_group(
    group,
    *,
    owner_id: str | None = None,
    catalog=None,
) -> DatasetDetail:
    is_builtin = False
    if catalog is not None:
        is_builtin = catalog.is_builtin(group.id)
    owned = bool(group.owner_id and owner_id and group.owner_id == owner_id)
    relations = [
        RelationInfo(
            name=rel.name,
            columns=[ColumnInfo(name=c.name, type=c.type_name) for c in rel.columns],
            rowCount=len(rel.rows),
        )
        for rel in group.relations.values()
    ]
    return DatasetDetail(
        id=group.id,
        name=group.name,
        description=group.description,
        relations=relations,
        exampleRelAlg=group.example_relalg,
        exampleSql=group.example_sql,
        owned=owned or is_builtin,
        isBuiltin=is_builtin,
        shareToken=group.share_token if owned else None,
        forkedFrom=group.forked_from,
    )


def _relation_data(group, relation_name: str) -> RelationData:
    if relation_name not in group.relations:
        raise DatasetError(f"Unknown relation: {relation_name}")
    rel = group.relations[relation_name]
    return RelationData(
        name=rel.name,
        columns=[ColumnInfo(name=c.name, type=c.type_name) for c in rel.columns],
        rows=list(rel.rows),
    )


def _http_dataset_error(exc: DatasetError, *, not_found: bool = False) -> HTTPException:
    return HTTPException(
        status_code=404 if not_found else 400,
        detail={
            "message": str(exc),
            "code": "not_found" if not_found else "dataset_error",
        },
    )


@router.get("", response_model=DatasetListResponse)
def list_datasets(request: Request) -> DatasetListResponse:
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)
    return DatasetListResponse(
        datasets=[
            DatasetSummary(
                id=g.id,
                name=g.name,
                description=g.description,
                owned=bool(g.owner_id == owner_id) if g.owner_id else False,
                isBuiltin=catalog.is_builtin(g.id),
            )
            for g in catalog.list_groups(owner_id)
        ]
    )


# Static paths MUST be registered before /{dataset_id} or POSTs become 405s.
@router.post("/upload", response_model=DatasetDetail)
async def upload_dataset(
    request: Request,
    file: UploadFile = File(...),
    relationName: str | None = Form(default=None),
    hasHeader: str = Form(default="true"),
    skipRows: int = Form(default=0),
    delimiter: str = Form(default=","),
) -> DatasetDetail:
    users = request.app.state.user_store
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)
    content = await file.read()
    filename = file.filename or "upload"
    lower = filename.lower()
    has_header = hasHeader.lower() in ("1", "true", "yes", "on")
    try:
        if lower.endswith(".csv"):
            group = users.from_csv(
                filename=filename,
                content=content,
                owner_id=owner_id,
                relation_name=relationName,
                has_header=has_header,
                skip_rows=max(0, int(skipRows)),
                delimiter=delimiter or ",",
            )
        elif lower.endswith(".db") or lower.endswith(".sqlite") or lower.endswith(
            ".sqlite3"
        ):
            group = users.from_sqlite(
                filename=filename, content=content, owner_id=owner_id
            )
        else:
            raise DatasetError("Supported uploads: .csv, .db, .sqlite, .sqlite3")
    except DatasetError as exc:
        raise HTTPException(
            status_code=400, detail={"message": str(exc), "code": "upload_error"}
        ) from exc
    return _detail_from_group(group, owner_id=owner_id, catalog=catalog)


@router.post("/build", response_model=DatasetDetail)
def build_relation(body: BuildRelationRequest, request: Request) -> DatasetDetail:
    users = request.app.state.user_store
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)
    try:
        group = users.from_builder(
            name=body.name,
            relation_name=body.relationName,
            columns=[c.model_dump() for c in body.columns],
            rows=body.rows,
            owner_id=owner_id,
        )
    except DatasetError as exc:
        raise HTTPException(
            status_code=400, detail={"message": str(exc), "code": "build_error"}
        ) from exc
    return _detail_from_group(group, owner_id=owner_id, catalog=catalog)


@router.post("/group/preview", response_model=GroupPreviewResponse)
def preview_group_text(body: GroupTextRequest) -> GroupPreviewResponse:
    """Parse RelaX local_groups text without installing."""
    try:
        groups = parse_local_groups(body.text, materialize=True)
    except DatasetError as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": str(exc), "code": "group_parse_error"},
        ) from exc
    return GroupPreviewResponse(groups=[_detail_from_group(g) for g in groups])


@router.post("/group/install", response_model=GroupPreviewResponse)
def install_group_text(
    body: GroupTextRequest, request: Request
) -> GroupPreviewResponse:
    """Parse and install all groups from RelaX local_groups text."""
    users = request.app.state.user_store
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)
    try:
        groups = users.from_group_text(body.text, owner_id=owner_id)
    except DatasetError as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": str(exc), "code": "group_parse_error"},
        ) from exc
    return GroupPreviewResponse(
        groups=[
            _detail_from_group(g, owner_id=owner_id, catalog=catalog) for g in groups
        ]
    )


@router.get("/share/{token}", response_model=DatasetDetail)
def get_shared_dataset(token: str, request: Request) -> DatasetDetail:
    users = request.app.state.user_store
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)
    try:
        group = users.get_by_share_token(token)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found=True) from exc
    return _detail_from_group(group, owner_id=owner_id, catalog=catalog)


@router.post("/share/{token}/copy", response_model=DatasetDetail)
def copy_shared_dataset(token: str, request: Request) -> DatasetDetail:
    users = request.app.state.user_store
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)
    try:
        source = users.get_by_share_token(token)
        group = users.copy_for_owner(source, owner_id=owner_id)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown" in str(exc)) from exc
    return _detail_from_group(group, owner_id=owner_id, catalog=catalog)


@router.get("/{dataset_id}/export", response_model=GroupTextResponse)
def export_dataset(dataset_id: str, request: Request) -> GroupTextResponse:
    """Export a dataset as RelaX-compatible local_groups text."""
    catalog = request.app.state.catalog
    try:
        group = catalog.get(dataset_id)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found=True) from exc
    text = format_group_text(group)
    return GroupTextResponse(text=text, filename=f"{group.id}.txt")


@router.get("/{dataset_id}/export.txt")
def export_dataset_plain(dataset_id: str, request: Request) -> PlainTextResponse:
    catalog = request.app.state.catalog
    try:
        group = catalog.get(dataset_id)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found=True) from exc
    return PlainTextResponse(
        format_group_text(group),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{group.id}.txt"',
        },
    )


@router.get("/{dataset_id}", response_model=DatasetDetail)
def get_dataset(dataset_id: str, request: Request) -> DatasetDetail:
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)
    try:
        group = catalog.get(dataset_id)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found=True) from exc
    return _detail_from_group(group, owner_id=owner_id, catalog=catalog)


@router.patch("/{dataset_id}", response_model=DatasetDetail)
def rename_dataset(
    dataset_id: str, body: RenameDatasetRequest, request: Request
) -> DatasetDetail:
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)
    try:
        group = catalog.rename_group(dataset_id, body.name, owner_id)
    except DatasetError as exc:
        raise _http_dataset_error(
            exc, not_found="Unknown dataset" in str(exc)
        ) from exc
    return _detail_from_group(group, owner_id=owner_id, catalog=catalog)


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: str, request: Request) -> dict:
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)
    try:
        catalog.delete_group(dataset_id, owner_id)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found=True) from exc
    return {"ok": True}


@router.post("/{dataset_id}/upload", response_model=DatasetDetail)
async def upload_relation_into_dataset(
    dataset_id: str,
    request: Request,
    file: UploadFile = File(...),
    relationName: str | None = Form(default=None),
    hasHeader: str = Form(default="true"),
    skipRows: int = Form(default=0),
    delimiter: str = Form(default=","),
) -> DatasetDetail:
    """Add a CSV as a new relation inside an existing dataset."""
    catalog = request.app.state.catalog
    users = request.app.state.user_store
    owner_id = owner_from_request(request)
    content = await file.read()
    filename = file.filename or "upload"
    lower = filename.lower()
    if not lower.endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Only CSV can be added into an existing dataset",
                "code": "upload_error",
            },
        )
    has_header = hasHeader.lower() in ("1", "true", "yes", "on")
    try:
        rel = users.parse_csv_relation(
            filename=filename,
            content=content,
            relation_name=relationName,
            has_header=has_header,
            skip_rows=max(0, int(skipRows)),
            delimiter=delimiter or ",",
        )
        group = catalog.attach_relation(dataset_id, rel, owner_id)
    except DatasetError as exc:
        raise _http_dataset_error(
            exc, not_found="Unknown dataset" in str(exc)
        ) from exc
    return _detail_from_group(group, owner_id=owner_id, catalog=catalog)


@router.post("/{dataset_id}/relations", response_model=DatasetDetail)
def add_relation(
    dataset_id: str, body: AddRelationRequest, request: Request
) -> DatasetDetail:
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)
    try:
        group = catalog.add_relation(
            dataset_id,
            owner_id,
            relation_name=body.relationName,
            columns=[c.model_dump() for c in body.columns],
            rows=body.rows,
        )
    except DatasetError as exc:
        raise _http_dataset_error(
            exc, not_found="Unknown dataset" in str(exc)
        ) from exc
    return _detail_from_group(group, owner_id=owner_id, catalog=catalog)


@router.get("/{dataset_id}/relations/{relation_name}", response_model=RelationData)
def get_relation(
    dataset_id: str, relation_name: str, request: Request
) -> RelationData:
    catalog = request.app.state.catalog
    try:
        group = catalog.get(dataset_id)
        return _relation_data(group, relation_name)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found=True) from exc


@router.patch("/{dataset_id}/relations/{relation_name}", response_model=DatasetDetail)
def rename_relation(
    dataset_id: str,
    relation_name: str,
    body: RenameRelationRequest,
    request: Request,
) -> DatasetDetail:
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)
    try:
        group = catalog.rename_relation(
            dataset_id, relation_name, body.name, owner_id
        )
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown" in str(exc)) from exc
    return _detail_from_group(group, owner_id=owner_id, catalog=catalog)


@router.delete("/{dataset_id}/relations/{relation_name}", response_model=DatasetDetail)
def delete_relation(
    dataset_id: str, relation_name: str, request: Request
) -> DatasetDetail:
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)
    try:
        group = catalog.delete_relation(dataset_id, relation_name, owner_id)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown" in str(exc)) from exc
    return _detail_from_group(group, owner_id=owner_id, catalog=catalog)


@router.patch(
    "/{dataset_id}/relations/{relation_name}/columns/{column_name}",
    response_model=DatasetDetail,
)
def update_column(
    dataset_id: str,
    relation_name: str,
    column_name: str,
    body: RenameColumnRequest,
    request: Request,
) -> DatasetDetail:
    if body.name is None and body.type is None:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Provide name and/or type to update",
                "code": "dataset_error",
            },
        )
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)
    try:
        current = column_name
        group = None
        if body.name is not None and body.name != column_name:
            group = catalog.rename_column(
                dataset_id, relation_name, current, body.name, owner_id
            )
            current = body.name
            dataset_id = group.id
        if body.type is not None:
            group = catalog.change_column_type(
                dataset_id, relation_name, current, body.type, owner_id
            )
        if group is None:
            group = catalog.get(dataset_id)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown" in str(exc)) from exc
    return _detail_from_group(group, owner_id=owner_id, catalog=catalog)


@router.post(
    "/{dataset_id}/relations/{relation_name}/columns",
    response_model=DatasetDetail,
)
def add_column(
    dataset_id: str,
    relation_name: str,
    body: AddColumnRequest,
    request: Request,
) -> DatasetDetail:
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)
    try:
        group = catalog.add_column(
            dataset_id,
            relation_name,
            owner_id,
            name=body.name,
            type_name=body.type,
            default=body.default,
        )
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown" in str(exc)) from exc
    return _detail_from_group(group, owner_id=owner_id, catalog=catalog)


@router.delete(
    "/{dataset_id}/relations/{relation_name}/columns/{column_name}",
    response_model=DatasetDetail,
)
def delete_column(
    dataset_id: str,
    relation_name: str,
    column_name: str,
    request: Request,
) -> DatasetDetail:
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)
    try:
        group = catalog.delete_column(
            dataset_id, relation_name, column_name, owner_id
        )
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown" in str(exc)) from exc
    return _detail_from_group(group, owner_id=owner_id, catalog=catalog)


@router.post(
    "/{dataset_id}/relations/{relation_name}/rows",
    response_model=DatasetDetail,
)
def add_row(
    dataset_id: str,
    relation_name: str,
    body: RowValuesRequest,
    request: Request,
) -> DatasetDetail:
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)
    try:
        group = catalog.add_row(dataset_id, relation_name, body.values, owner_id)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown" in str(exc)) from exc
    return _detail_from_group(group, owner_id=owner_id, catalog=catalog)


@router.put(
    "/{dataset_id}/relations/{relation_name}/rows",
    response_model=DatasetDetail,
)
def set_rows(
    dataset_id: str,
    relation_name: str,
    body: SetRowsRequest,
    request: Request,
) -> DatasetDetail:
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)
    try:
        group = catalog.set_rows(dataset_id, relation_name, body.rows, owner_id)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown" in str(exc)) from exc
    return _detail_from_group(group, owner_id=owner_id, catalog=catalog)


@router.put(
    "/{dataset_id}/relations/{relation_name}/rows/{row_index}",
    response_model=DatasetDetail,
)
def update_row(
    dataset_id: str,
    relation_name: str,
    row_index: int,
    body: RowValuesRequest,
    request: Request,
) -> DatasetDetail:
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)
    try:
        group = catalog.update_row(
            dataset_id, relation_name, row_index, body.values, owner_id
        )
    except DatasetError as exc:
        raise _http_dataset_error(
            exc, not_found="Unknown" in str(exc) or "out of range" in str(exc)
        ) from exc
    return _detail_from_group(group, owner_id=owner_id, catalog=catalog)


@router.delete(
    "/{dataset_id}/relations/{relation_name}/rows/{row_index}",
    response_model=DatasetDetail,
)
def delete_row(
    dataset_id: str,
    relation_name: str,
    row_index: int,
    request: Request,
) -> DatasetDetail:
    catalog = request.app.state.catalog
    owner_id = owner_from_request(request)
    try:
        group = catalog.delete_row(
            dataset_id, relation_name, row_index, owner_id
        )
    except DatasetError as exc:
        raise _http_dataset_error(
            exc, not_found="Unknown" in str(exc) or "out of range" in str(exc)
        ) from exc
    return _detail_from_group(group, owner_id=owner_id, catalog=catalog)
