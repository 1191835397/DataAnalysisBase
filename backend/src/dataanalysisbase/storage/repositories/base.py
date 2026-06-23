"""Base repository helpers."""

from dataanalysisbase.storage.duckdb_store import DuckDBStore


class BaseRepo:
    def __init__(self, store: DuckDBStore) -> None:
        self.store = store
