"""Repositories for Phase A aggregate tables."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from dataanalysisbase.domain.enums import RunStatus
from dataanalysisbase.domain.price_limits import (
    BSE_LIMIT_UP_PCT,
    GROWTH_BOARD_LIMIT_UP_PCT,
    REGULAR_LIMIT_UP_PCT,
    RISK_WARNING_LIMIT_UP_PCT,
)
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
        self._ensure_snapshot_columns()
        self.store.execute(
            """
            CREATE OR REPLACE TABLE latest_market_snapshot AS
            SELECT snapshot_time, security_id, name, price, change_pct, volume, amount,
                   turnover_rate, volume_ratio, pe_ttm, pb, market_cap, industry_code,
                   listing_date, ex_dividend, is_suspended, source, fetched_at
            FROM market_snapshots
            WHERE snapshot_time = ?
            """,
            [snapshot_time],
        )

    def refresh_overview(self, snapshot_time: datetime) -> None:
        self._ensure_snapshot_columns()
        self.store.execute(
            """
            DELETE FROM market_overview_snapshots WHERE snapshot_time = ?
            """,
            [snapshot_time],
        )
        self.store.execute(
            f"""
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
                sum(CASE WHEN change_pct >= {_limit_up_pct_sql()} THEN 1 ELSE 0 END)::INTEGER,
                sum(CASE WHEN change_pct <= {_limit_down_pct_sql()} THEN 1 ELSE 0 END)::INTEGER,
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
        where, params = _build_stock_where(
            query,
            listing_date_sql=_column_or_default(
                self.store,
                "latest_market_snapshot",
                "listing_date",
                "CAST(NULL AS DATE)",
            ),
        )
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

    def get_stock(self, security_id: str) -> dict[str, Any] | None:
        listing_date = _column_or_default(
            self.store,
            "latest_market_snapshot",
            "listing_date",
            "CAST(NULL AS DATE)",
        )
        ex_dividend = _column_or_default(
            self.store,
            "latest_market_snapshot",
            "ex_dividend",
            "FALSE",
            expression="coalesce({column}, FALSE)",
        )
        is_suspended = _column_or_default(
            self.store,
            "latest_market_snapshot",
            "is_suspended",
            "FALSE",
            expression="coalesce({column}, FALSE)",
        )
        rows = self.store.query(
            f"""
            SELECT snapshot_time, security_id, name, price, change_pct, volume, amount,
                   turnover_rate, volume_ratio, pe_ttm, pb, market_cap, industry_code,
                   {listing_date} AS listing_date, {ex_dividend} AS ex_dividend,
                   {is_suspended} AS is_suspended, source, fetched_at
            FROM latest_market_snapshot
            WHERE security_id = ?
            LIMIT 1
            """,
            [security_id],
        )
        return rows[0] if rows else None

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

    def get_alert_candidates(
        self,
        *,
        limit_up_threshold: float,
        limit_down_threshold: float,
        volume_ratio_threshold: float,
        extreme_change_threshold: float,
        limit: int,
    ) -> list[dict[str, Any]]:
        latest_listing_date = _column_or_default(
            self.store,
            "latest_market_snapshot",
            "listing_date",
            "CAST(NULL AS DATE)",
            alias="latest",
        )
        latest_ex_dividend = _column_or_default(
            self.store,
            "latest_market_snapshot",
            "ex_dividend",
            "FALSE",
            alias="latest",
            expression="coalesce({column}, FALSE)",
        )
        latest_is_suspended = _column_or_default(
            self.store,
            "latest_market_snapshot",
            "is_suspended",
            "FALSE",
            alias="latest",
            expression="coalesce({column}, FALSE)",
        )
        limit_up_sql = _limit_up_pct_sql(
            "latest",
            "latest_time",
            latest_listing_date,
        )
        limit_down_sql = _limit_down_pct_sql(
            "latest",
            "latest_time",
            latest_listing_date,
        )
        rows = self.store.query(
            f"""
            WITH latest_time AS (
                SELECT max(snapshot_time) AS snapshot_time
                FROM latest_market_snapshot
            ),
            previous_time AS (
                SELECT max(snapshot_time) AS snapshot_time
                FROM market_snapshot_runs
                WHERE snapshot_time < (SELECT snapshot_time FROM latest_time)
                  AND status IN (?, ?)
            ),
            candidates AS (
                SELECT
                    latest.snapshot_time,
                    latest.security_id,
                    latest.name,
                    latest.price,
                    latest.change_pct,
                    latest.volume,
                    latest.amount,
                    latest.turnover_rate,
                    latest.volume_ratio,
                    latest.pe_ttm,
                    latest.pb,
                    latest.market_cap,
                    latest.industry_code,
                    {latest_listing_date} AS listing_date,
                    {latest_ex_dividend} AS ex_dividend,
                    {latest_is_suspended} AS is_suspended,
                    latest.source,
                    latest.fetched_at,
                    {limit_up_sql} AS limit_up_threshold,
                    {limit_down_sql} AS limit_down_threshold,
                    CASE
                        WHEN {latest_ex_dividend}
                          OR latest.price IS NULL
                          OR previous.price IS NULL
                          OR previous.price = 0
                        THEN NULL
                        ELSE (latest.price - previous.price) / previous.price * 100
                    END AS delta_price_pct
                FROM latest_market_snapshot latest
                LEFT JOIN market_snapshots previous
                  ON previous.snapshot_time = (SELECT snapshot_time FROM previous_time)
                 AND previous.security_id = latest.security_id
                 AND previous.source = latest.source
            )
            SELECT snapshot_time, security_id, name, price, change_pct, volume, amount,
                   turnover_rate, volume_ratio, pe_ttm, pb, market_cap, industry_code,
                   listing_date, ex_dividend, is_suspended, source, fetched_at,
                   limit_up_threshold, limit_down_threshold, delta_price_pct
            FROM candidates
            WHERE NOT is_suspended
              AND (
                  change_pct >= limit_up_threshold
                  OR change_pct <= limit_down_threshold
                  OR volume_ratio >= ?
                  OR abs(delta_price_pct) >= ?
              )
            ORDER BY
                CASE
                    WHEN change_pct >= limit_up_threshold
                      OR change_pct <= limit_down_threshold THEN 0
                    WHEN abs(delta_price_pct) >= ? THEN 1
                    ELSE 2
                END,
                abs(coalesce(delta_price_pct, change_pct, 0)) DESC,
                coalesce(volume_ratio, 0) DESC,
                security_id ASC
            LIMIT ?
            """,
            [
                RunStatus.SUCCESS.value,
                RunStatus.PARTIAL.value,
                volume_ratio_threshold,
                extreme_change_threshold,
                extreme_change_threshold,
                limit,
            ],
        )
        return rows

    def _ensure_snapshot_columns(self) -> None:
        _ensure_column(self.store, "market_snapshots", "listing_date", "DATE")
        _ensure_column(
            self.store,
            "market_snapshots",
            "ex_dividend",
            "BOOLEAN",
        )
        _ensure_column(
            self.store,
            "market_snapshots",
            "is_suspended",
            "BOOLEAN",
        )

    def _ensure_latest_snapshot_columns(self) -> None:
        _ensure_column(self.store, "latest_market_snapshot", "listing_date", "DATE")
        _ensure_column(
            self.store,
            "latest_market_snapshot",
            "ex_dividend",
            "BOOLEAN",
        )
        _ensure_column(
            self.store,
            "latest_market_snapshot",
            "is_suspended",
            "BOOLEAN",
        )


def _build_stock_where(
    query: StockQuery,
    *,
    listing_date_sql: str = "listing_date",
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if query.industry:
        clauses.append("coalesce(industry_code, 'UNKNOWN') = ?")
        params.append(query.industry)
    if query.q:
        clauses.append("(security_id ILIKE ? OR name ILIKE ?)")
        params.extend([f"%{query.q}%", f"%{query.q}%"])
    if query.filter == "gainers":
        clauses.append("change_pct > 0")
    elif query.filter == "losers":
        clauses.append("change_pct < 0")
    elif query.filter == "limit_up":
        clauses.append(f"change_pct >= {_limit_up_pct_sql(listing_date_sql=listing_date_sql)}")
    elif query.filter == "limit_down":
        clauses.append(f"change_pct <= {_limit_down_pct_sql(listing_date_sql=listing_date_sql)}")
    elif query.filter == "volume":
        clauses.append("volume_ratio >= 2.0")

    return (f"WHERE {' AND '.join(clauses)}", params) if clauses else ("", params)


def _limit_up_pct_sql(
    alias: str | None = None,
    snapshot_alias: str | None = None,
    listing_date_sql: str | None = None,
) -> str:
    security_id = _column("security_id", alias)
    name = _column("name", alias)
    listing_date = listing_date_sql or _column("listing_date", alias)
    snapshot_date = (
        f"(SELECT snapshot_time::DATE FROM {snapshot_alias})"
        if snapshot_alias
        else "snapshot_time::DATE"
    )
    return f"""
CASE
    WHEN {listing_date} IS NOT NULL
      AND {snapshot_date} >= {listing_date}
      AND {snapshot_date} < {listing_date} + INTERVAL 5 DAY THEN NULL
    WHEN upper({name}) LIKE '*ST%'
      OR upper({name}) LIKE 'ST%'
      OR upper({name}) LIKE 'S*ST%' THEN {RISK_WARNING_LIMIT_UP_PCT}
    WHEN {security_id} LIKE '688%.SH'
      OR {security_id} LIKE '689%.SH'
      OR {security_id} LIKE '300%.SZ'
      OR {security_id} LIKE '301%.SZ' THEN {GROWTH_BOARD_LIMIT_UP_PCT}
    WHEN {security_id} LIKE '%.BJ' THEN {BSE_LIMIT_UP_PCT}
    ELSE {REGULAR_LIMIT_UP_PCT}
END
"""


def _limit_down_pct_sql(
    alias: str | None = None,
    snapshot_alias: str | None = None,
    listing_date_sql: str | None = None,
) -> str:
    return f"(-1 * ({_limit_up_pct_sql(alias, snapshot_alias, listing_date_sql)}))"


def _column(name: str, alias: str | None) -> str:
    return f"{alias}.{name}" if alias else name


def _ensure_column(store: Any, table_name: str, column_name: str, column_type: str) -> None:
    if _has_column(store, table_name, column_name):
        return
    store.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def _column_or_default(
    store: Any,
    table_name: str,
    column_name: str,
    default_sql: str,
    *,
    alias: str | None = None,
    expression: str = "{column}",
) -> str:
    if _has_column(store, table_name, column_name):
        return expression.format(column=_column(column_name, alias))
    return default_sql


def _has_column(store: Any, table_name: str, column_name: str) -> bool:
    rows = store.query(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = ?
          AND column_name = ?
        """,
        [table_name, column_name],
    )
    return bool(rows)


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
