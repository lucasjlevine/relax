from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.datasets.loader import DatasetError
from app.models.schemas import (
    AddColumnRequest,
    AddRelationRequest,
    BuildRelationRequest,
    ColumnInfo,
    DatasetDetail,
    DatasetListResponse,
    DatasetSummary,
    RelationData,
    RelationInfo,
    RenameColumnRequest,
    RenameDatasetRequest,
    RenameRelationRequest,
    RowValuesRequest,
    SetRowsRequest,
)

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


def _detail_from_group(group) -> DatasetDetail:
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
        detail={"message": str(exc), "code": "not_found" if not_found else "dataset_error"},
    )


@router.get("", response_model=DatasetListResponse)
def list_datasets(request: Request) -> DatasetListResponse:
    catalog = request.app.state.catalog
    return DatasetListResponse(
        datasets=[
            DatasetSummary(id=g.id, name=g.name, description=g.description)
            for g in catalog.list_groups()
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
    content = await file.read()
    filename = file.filename or "upload"
    lower = filename.lower()
    has_header = hasHeader.lower() in ("1", "true", "yes", "on")
    try:
        if lower.endswith(".csv"):
            group = users.from_csv(
                filename=filename,
                content=content,
                relation_name=relationName,
                has_header=has_header,
                skip_rows=max(0, int(skipRows)),
                delimiter=delimiter or ",",
            )
        elif lower.endswith(".db") or lower.endswith(".sqlite") or lower.endswith(".sqlite3"):
            group = users.from_sqlite(filename=filename, content=content)
        else:
            raise DatasetError("Supported uploads: .csv, .db, .sqlite, .sqlite3")
    except DatasetError as exc:
        raise HTTPException(
            status_code=400, detail={"message": str(exc), "code": "upload_error"}
        ) from exc
    return _detail_from_group(group)


@router.post("/build", response_model=DatasetDetail)
def build_relation(body: BuildRelationRequest, request: Request) -> DatasetDetail:
    users = request.app.state.user_store
    try:
        group = users.from_builder(
            name=body.name,
            relation_name=body.relationName,
            columns=[c.model_dump() for c in body.columns],
            rows=body.rows,
        )
    except DatasetError as exc:
        raise HTTPException(
            status_code=400, detail={"message": str(exc), "code": "build_error"}
        ) from exc
    return _detail_from_group(group)


@router.get("/{dataset_id}", response_model=DatasetDetail)
def get_dataset(dataset_id: str, request: Request) -> DatasetDetail:
    catalog = request.app.state.catalog
    try:
        group = catalog.get(dataset_id)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found=True) from exc
    return _detail_from_group(group)


@router.patch("/{dataset_id}", response_model=DatasetDetail)
def rename_dataset(
    dataset_id: str, body: RenameDatasetRequest, request: Request
) -> DatasetDetail:
    catalog = request.app.state.catalog
    try:
        group = catalog.rename_group(dataset_id, body.name)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown dataset" in str(exc)) from exc
    return _detail_from_group(group)


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: str, request: Request) -> dict:
    catalog = request.app.state.catalog
    try:
        catalog.delete_group(dataset_id)
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
        group = catalog.attach_relation(dataset_id, rel)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown dataset" in str(exc)) from exc
    return _detail_from_group(group)


@router.post("/{dataset_id}/relations", response_model=DatasetDetail)
def add_relation(
    dataset_id: str, body: AddRelationRequest, request: Request
) -> DatasetDetail:
    catalog = request.app.state.catalog
    try:
        group = catalog.add_relation(
            dataset_id,
            relation_name=body.relationName,
            columns=[c.model_dump() for c in body.columns],
            rows=body.rows,
        )
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown dataset" in str(exc)) from exc
    return _detail_from_group(group)


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
    try:
        group = catalog.rename_relation(dataset_id, relation_name, body.name)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown" in str(exc)) from exc
    return _detail_from_group(group)


@router.delete("/{dataset_id}/relations/{relation_name}", response_model=DatasetDetail)
def delete_relation(
    dataset_id: str, relation_name: str, request: Request
) -> DatasetDetail:
    catalog = request.app.state.catalog
    try:
        group = catalog.delete_relation(dataset_id, relation_name)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown" in str(exc)) from exc
    return _detail_from_group(group)


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
    try:
        group = catalog.get(dataset_id)
        current = column_name
        if body.name is not None and body.name != column_name:
            group = catalog.rename_column(
                dataset_id, relation_name, current, body.name
            )
            current = body.name
        if body.type is not None:
            group = catalog.change_column_type(
                dataset_id, relation_name, current, body.type
            )
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown" in str(exc)) from exc
    return _detail_from_group(group)


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
    try:
        group = catalog.add_column(
            dataset_id,
            relation_name,
            name=body.name,
            type_name=body.type,
            default=body.default,
        )
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown" in str(exc)) from exc
    return _detail_from_group(group)


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
    try:
        group = catalog.delete_column(dataset_id, relation_name, column_name)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown" in str(exc)) from exc
    return _detail_from_group(group)


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
    try:
        group = catalog.add_row(dataset_id, relation_name, body.values)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown" in str(exc)) from exc
    return _detail_from_group(group)


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
    try:
        group = catalog.set_rows(dataset_id, relation_name, body.rows)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown" in str(exc)) from exc
    return _detail_from_group(group)


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
    try:
        group = catalog.update_row(
            dataset_id, relation_name, row_index, body.values
        )
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown" in str(exc) or "out of range" in str(exc)) from exc
    return _detail_from_group(group)


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
    try:
        group = catalog.delete_row(dataset_id, relation_name, row_index)
    except DatasetError as exc:
        raise _http_dataset_error(exc, not_found="Unknown" in str(exc) or "out of range" in str(exc)) from exc
    return _detail_from_group(group)
