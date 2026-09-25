from fastapi import APIRouter, HTTPException, Request

from app.datasets.loader import DatasetError
from app.models.schemas import (
    ColumnInfo,
    DatasetDetail,
    DatasetListResponse,
    DatasetSummary,
    RelationInfo,
)

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


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
        raise HTTPException(status_code=404, detail={"message": str(exc), "code": "not_found"}) from exc

    relations = [
        RelationInfo(
            name=rel.name,
            columns=[
                ColumnInfo(name=c.name, type=c.type_name) for c in rel.columns
            ],
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
