"""DuckDB connection and query helpers."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import duckdb

from dataanalysisbase.common.errors import StorageError


class DuckDBStore:
    """Thin DuckDB wrapper used by repository classes."""

    def __init__(self, path: Path | str, *, read_only: bool = False) -> None:
        self.path = Path(path)
        self.read_only = read_only
        if not read_only:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: duckdb.DuckDBPyConnection | None = None

    def connect(self) -> duckdb.DuckDBPyConnection:
        if self._connection is None:
            try:
                self._connection = duckdb.connect(str(self.path), read_only=self.read_only)
            except duckdb.Error as exc:
                raise StorageError(f"Failed to connect DuckDB at {self.path}: {exc}") from exc
        return self._connection

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @contextmanager
    def transaction(self) -> Iterator[duckdb.DuckDBPyConnection]:
        conn = self.connect()
        try:
            conn.execute("BEGIN")
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def init_schema(self) -> None:
        schema_path = Path(__file__).with_name("schema.sql")
        try:
            self.connect().execute(schema_path.read_text(encoding="utf-8"))
        except (OSError, duckdb.Error) as exc:
            raise StorageError(f"Failed to initialize schema: {exc}") from exc

    def query(self, sql: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
        try:
            cursor = self.connect().execute(sql, params or [])
            columns = [column[0] for column in cursor.description or []]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        except duckdb.Error as exc:
            raise StorageError(f"DuckDB query failed: {exc}") from exc

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> int:
        try:
            cursor = self.connect().execute(sql, params or [])
            return cursor.rowcount if cursor.rowcount is not None else 0
        except duckdb.Error as exc:
            raise StorageError(f"DuckDB execute failed: {exc}") from exc
