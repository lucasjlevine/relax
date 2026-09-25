from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.datasets.loader import DatasetError
from app.models.schemas import (
    BuildRelationRequest,
    ColumnInfo,
    DatasetDetail,
    DatasetListResponse,
    DatasetSummary,
    RelationInfo,
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


@router.get("", response_model=DatasetListResponse)
def list_datasets(request: Request) -> DatasetListResponse:
    catalog = request.app.state.catalog
    return DatasetListResponse(
        datasets=[
            DatasetSummary(id=g.id, name=g.name, description=g.description)
            for g in catalog.list_groups()
        ]
    )


@router.get("/{dataset_id}", response_model=DatasetDetail)
def get_dataset(dataset_id: str, request: Request) -> DatasetDetail:
    catalog = request.app.state.catalog
    try:
        group = catalog.get(dataset_id)
    except DatasetError as exc:
        raise HTTPException(
            status_code=404, detail={"message": str(exc), "code": "not_found"}
        ) from exc
    return _detail_from_group(group)


@router.post("/upload", response_model=DatasetDetail)
async def upload_dataset(
    request: Request,
    file: UploadFile = File(...),
    relationName: str | None = Form(default=None),
) -> DatasetDetail:
    users = request.app.state.user_store
    content = await file.read()
    filename = file.filename or "upload"
    lower = filename.lower()
    try:
        if lower.endswith(".csv"):
            group = users.from_csv(
                filename=filename, content=content, relation_name=relationName
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
