"""Repositories for Phase A aggregate tables."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from dataanalysisbase.storage.repositories.base import BaseRepo
from dataanalysisbase.storage.repositories.page import Page


class StockQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    page: int = Field(default=1, ge=1)
    size: int = Field(default=50, ge=1, le=200)
    sort: str = "change_pct"
    order: Literal["asc", "desc"] = "desc"
    industry: str | None = None
    q: str | None = None
    filter: Literal["gainers", "losers", "limit_up", "limit_down", "volume"] | None = None


class IndustryQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    limit: int = Field(default=50, ge=1, le=200)
    sort: str = "change_pct_avg"
    order: Literal["asc", "desc"] = "desc"


class AggregateRepo(BaseRepo):
    """Maintain and query latest market aggregate tables."""

    def refresh_latest(self, snapshot_time: datetime) -> None:
        self.store.execute(
            """
            CREATE OR REPLACE TABLE latest_market_snapshot AS
            SELECT snapshot_time, security_id, name, price, change_pct, volume, amount,
                   turnover_rate, volume_ratio, pe_ttm, pb, market_cap, industry_code,
                   source, fetched_at
            FROM market_snapshots
            WHERE snapshot_time = ?
            """,
            [snapshot_time],
        )

    def refresh_overview(self, snapshot_time: datetime) -> None:
        self.store.execute(
            """
            DELETE FROM market_overview_snapshots WHERE snapshot_time = ?
            """,
            [snapshot_time],
        )
        self.store.execute(
            """
            INSERT INTO market_overview_snapshots (
                snapshot_time, stock_count, up_count, down_count, flat_count,
                limit_up_count, limit_down_count, total_amount, source
            )
            SELECT
                snapshot_time,
                count(*)::INTEGER,
                sum(CASE WHEN change_pct > 0 THEN 1 ELSE 0 END)::INTEGER,
                sum(CASE WHEN change_pct < 0 THEN 1 ELSE 0 END)::INTEGER,
                sum(CASE WHEN change_pct = 0 OR change_pct IS NULL THEN 1 ELSE 0 END)::INTEGER,
                sum(CASE WHEN change_pct >= 9.9 THEN 1 ELSE 0 END)::INTEGER,
                sum(CASE WHEN change_pct <= -9.9 THEN 1 ELSE 0 END)::INTEGER,
                sum(amount),
                any_value(source)
            FROM market_snapshots
            WHERE snapshot_time = ?
            GROUP BY snapshot_time
            """,
            [snapshot_time],
        )

    def refresh_industry(self, snapshot_time: datetime) -> None:
        self.store.execute(
            "DELETE FROM industry_snapshots WHERE snapshot_time = ?",
            [snapshot_time],
        )
        self.store.execute(
            """
            INSERT INTO industry_snapshots (
                snapshot_time, industry_code, stock_count, change_pct_avg, amount_sum,
                up_count, down_count, source
            )
            SELECT
                snapshot_time,
                coalesce(industry_code, 'UNKNOWN') AS industry_code,
                count(*)::INTEGER,
                avg(change_pct),
                sum(amount),
                sum(CASE WHEN change_pct > 0 THEN 1 ELSE 0 END)::INTEGER,
                sum(CASE WHEN change_pct < 0 THEN 1 ELSE 0 END)::INTEGER,
                any_value(source)
            FROM market_snapshots
            WHERE snapshot_time = ?
            GROUP BY snapshot_time, coalesce(industry_code, 'UNKNOWN')
            """,
            [snapshot_time],
        )

    def get_overview(self, snapshot_time: datetime | None = None) -> dict[str, Any] | None:
        if snapshot_time is None:
            rows = self.store.query(
                """
                SELECT *
                FROM market_overview_snapshots
                ORDER BY snapshot_time DESC
                LIMIT 1
                """
            )
        else:
            rows = self.store.query(
                "SELECT * FROM market_overview_snapshots WHERE snapshot_time = ?",
                [snapshot_time],
            )
        return rows[0] if rows else None

    def get_stocks_page(self, query: StockQuery) -> Page[dict[str, Any]]:
        where, params = _build_stock_where(query)
        order_by = _safe_sort(query.sort)
        order = query.order.upper()
        offset = (query.page - 1) * query.size

        total_rows = self.store.query(
            f"SELECT count(*) AS total FROM latest_market_snapshot {where}",
            params,
        )
        rows = self.store.query(
            f"""
            SELECT *
            FROM latest_market_snapshot
            {where}
            ORDER BY {order_by} {order} NULLS LAST, security_id ASC
            LIMIT ? OFFSET ?
            """,
            [*params, query.size, offset],
        )
        return Page(items=rows, total=int(total_rows[0]["total"]), page=query.page, size=query.size)

    def get_industries(self, query: IndustryQuery) -> list[dict[str, Any]]:
        order_by = _safe_industry_sort(query.sort)
        order = query.order.upper()
        rows = self.store.query(
            f"""
            SELECT snapshot_time, industry_code, stock_count, change_pct_avg, amount_sum,
                   up_count, down_count, source
            FROM industry_snapshots
            WHERE snapshot_time = (
                SELECT max(snapshot_time)
                FROM industry_snapshots
            )
            ORDER BY {order_by} {order} NULLS LAST, industry_code ASC
            LIMIT ?
            """,
            [query.limit],
        )
        return rows


def _build_stock_where(query: StockQuery) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if query.industry:
        clauses.append("industry_code = ?")
        params.append(query.industry)
    if query.q:
        clauses.append("(security_id ILIKE ? OR name ILIKE ?)")
        params.extend([f"%{query.q}%", f"%{query.q}%"])
    if query.filter == "gainers":
        clauses.append("change_pct > 0")
    elif query.filter == "losers":
        clauses.append("change_pct < 0")
    elif query.filter == "limit_up":
        clauses.append("change_pct >= 9.9")
    elif query.filter == "limit_down":
        clauses.append("change_pct <= -9.9")
    elif query.filter == "volume":
        clauses.append("volume_ratio >= 2.0")

    return (f"WHERE {' AND '.join(clauses)}", params) if clauses else ("", params)


def _safe_sort(sort: str) -> str:
    allowed = {
        "security_id",
        "name",
        "price",
        "change_pct",
        "amount",
        "volume_ratio",
        "pe_ttm",
        "pb",
        "market_cap",
        "industry_code",
        "snapshot_time",
    }
    return sort if sort in allowed else "change_pct"


def _safe_industry_sort(sort: str) -> str:
    allowed = {
        "industry_code",
        "stock_count",
        "change_pct_avg",
        "amount_sum",
        "up_count",
        "down_count",
        "snapshot_time",
    }
    return sort if sort in allowed else "change_pct_avg"
