from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    name: str
    type: str


class RelationInfo(BaseModel):
    name: str
    columns: list[ColumnInfo]
    rowCount: int


class DatasetSummary(BaseModel):
    id: str
    name: str
    description: str


class DatasetDetail(DatasetSummary):
    relations: list[RelationInfo]
    exampleRelAlg: str | None = None
    exampleSql: str | None = None


class RelationData(BaseModel):
    name: str
    columns: list[ColumnInfo]
    rows: list[list[Any]]


class DatasetListResponse(BaseModel):
    datasets: list[DatasetSummary]


class RenameDatasetRequest(BaseModel):
    name: str


class RenameRelationRequest(BaseModel):
    name: str


class RenameColumnRequest(BaseModel):
    name: str | None = None
    type: str | None = None


class AddColumnRequest(BaseModel):
    name: str
    type: str = "string"
    default: Any = None


class AddRelationRequest(BaseModel):
    relationName: str
    columns: list[ColumnInfo]
    rows: list[list[Any]] = Field(default_factory=list)


class RowValuesRequest(BaseModel):
    values: list[Any]


class SetRowsRequest(BaseModel):
    rows: list[list[Any]]


class QueryRequest(BaseModel):
    datasetId: str
    language: Literal["relalg", "sql"]
    query: str
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class OperatorTreeNode(BaseModel):
    id: str
    label: str
    operator: str
    children: list[OperatorTreeNode] = Field(default_factory=list)


class QueryResponse(BaseModel):
    columns: list[ColumnInfo]
    rows: list[list[Any]]
    rowCount: int
    executionMs: float
    tree: OperatorTreeNode | None = None
    warnings: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str


class FormatRequest(BaseModel):
    query: str
    language: Literal["relalg", "sql"] = "relalg"


class FormatResponse(BaseModel):
    formatted: str


class BuildRelationRequest(BaseModel):
    name: str = "Custom relation"
    relationName: str
    columns: list[ColumnInfo]
    rows: list[list[Any]]


class GroupTextRequest(BaseModel):
    """RelaX-compatible local_groups source text."""

    text: str


class GroupTextResponse(BaseModel):
    """Serialized group export."""

    text: str
    filename: str | None = None


class GroupPreviewResponse(BaseModel):
    groups: list[DatasetDetail]
