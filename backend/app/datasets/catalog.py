from __future__ import annotations

from app.datasets.loader import DatasetCatalog, DatasetError, GroupDef
from app.datasets.user_store import UserDatasetStore


class CombinedCatalog:
    def __init__(self, static: DatasetCatalog, users: UserDatasetStore) -> None:
        self.static = static
        self.users = users

    def list_groups(self) -> list[GroupDef]:
        return self.static.list_groups() + self.users.list_groups()

    def get(self, group_id: str) -> GroupDef:
        try:
            return self.static.get(group_id)
        except DatasetError:
            return self.users.get(group_id)
