"""Derived market alert API helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

from dataanalysisbase.common.errors import ConfigError, StorageError
from dataanalysisbase.config_loader import load_settings, load_surveillance_rules
from dataanalysisbase.config_loader.surveillance_cfg import RuleConfig
from dataanalysisbase.domain.enums import AlertSeverity, DataStatus
from dataanalysisbase.observability.system_status import RuntimeStatus, build_runtime_status
from dataanalysisbase.storage import AggregateRepo, DuckDBStore

AlertKind = Literal[
    "data_stale",
    "sync_failed",
    "partial_sync",
    "offline",
    "limit_up",
    "limit_down",
    "volume_surge",
    "extreme_move",
]


class MarketAlert(BaseModel):
    """Current derived alert shown in the dashboard."""

    model_config = ConfigDict(frozen=True)

    alert_id: str
    severity: AlertSeverity
    kind: AlertKind
    title: str
    message: str
    triggered_at: datetime
    security_id: str | None = None
    name: str | None = None
    industry_code: str | None = None
    metric: str | None = None
    value: float | None = None
    threshold: float | None = None
    snapshot_time: datetime | None = None


class MarketAlertGroup(BaseModel):
    """Denoised alert group for one system condition or one security."""

    model_config = ConfigDict(frozen=True)

    group_id: str
    severity: AlertSeverity
    kinds: list[AlertKind]
    title: str
    message: str
    triggered_at: datetime
    alert_count: int
    security_id: str | None = None
    name: str | None = None
    industry_code: str | None = None
    snapshot_time: datetime | None = None
    alerts: list[MarketAlert]


def get_market_alerts(limit: int = 50) -> list[MarketAlert]:
    """Return current system and market snapshot alerts."""

    settings = load_settings()
    status = build_runtime_status(settings=settings)
    alerts = _system_alerts(status)
    if status.latest_snapshot_time is None:
        return alerts[:limit]

    try:
        rules = load_surveillance_rules(settings.config_dir)
        repo, store = _aggregate_repo(settings.duckdb_path)
        try:
            rows = repo.get_alert_candidates(
                limit_up_threshold=_rule_threshold(rules.rules.get("limit_up"), 9.9),
                limit_down_threshold=_rule_threshold(rules.rules.get("limit_down"), -9.9),
                volume_ratio_threshold=_rule_threshold(rules.rules.get("volume_surge"), 2.0),
                extreme_change_threshold=_rule_threshold(rules.rules.get("price_spike"), 3.0),
                limit=max(limit - len(alerts), 1),
            )
        finally:
            store.close()
    except (ConfigError, StorageError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"market alerts are not available: {exc}",
        ) from exc

    alerts.extend(_stock_alerts(rows, rules.rules))
    return alerts[:limit]


def get_market_alert_groups(limit: int = 50) -> list[MarketAlertGroup]:
    """Return current alerts grouped by system condition or security."""

    alerts = get_market_alerts(limit=min(max(limit * 4, limit), 200))
    groups = _group_alerts(alerts)
    groups.sort(key=_group_sort_key, reverse=True)
    return groups[:limit]


def _system_alerts(status: RuntimeStatus) -> list[MarketAlert]:
    if status.data_status == DataStatus.FRESH:
        return []

    triggered_at = status.generated_at
    if status.data_status == DataStatus.OFFLINE:
        return [
            MarketAlert(
                alert_id="system:offline",
                severity=AlertSeverity.HIGH,
                kind="offline",
                title="没有可用市场快照",
                message="当前没有可用市场快照, 请先执行一次市场同步。",
                triggered_at=triggered_at,
                snapshot_time=status.latest_snapshot_time,
            )
        ]
    if status.data_status == DataStatus.FAILED:
        error = status.last_market_run.error if status.last_market_run else None
        return [
            MarketAlert(
                alert_id="system:sync_failed",
                severity=AlertSeverity.HIGH,
                kind="sync_failed",
                title="最近同步失败",
                message=error or "最近一次市场同步失败, 页面仍展示可用历史快照。",
                triggered_at=triggered_at,
                snapshot_time=status.latest_snapshot_time,
            )
        ]
    if status.data_status == DataStatus.PARTIAL:
        run = status.last_market_run
        missing = run.missing if run else 0
        return [
            MarketAlert(
                alert_id="system:partial_sync",
                severity=AlertSeverity.MEDIUM,
                kind="partial_sync",
                title="最近同步不完整",
                message=f"最近同步缺失 {missing} 条记录, 部分统计可能不完整。",
                triggered_at=triggered_at,
                metric="missing",
                value=float(missing),
                snapshot_time=status.latest_snapshot_time,
            )
        ]
    return [
        MarketAlert(
            alert_id="system:data_stale",
            severity=AlertSeverity.MEDIUM,
            kind="data_stale",
            title="市场快照已过期",
            message="最近快照已超过 freshness 阈值, 页面仍展示最后一次成功数据。",
            triggered_at=triggered_at,
            snapshot_time=status.latest_snapshot_time,
        )
    ]


def _stock_alerts(rows: list[dict[str, Any]], rules: dict[str, RuleConfig]) -> list[MarketAlert]:
    alerts: list[MarketAlert] = []
    for row in rows:
        alerts.extend(_row_alerts(row, rules))
    return alerts


def _group_alerts(alerts: list[MarketAlert]) -> list[MarketAlertGroup]:
    grouped: dict[str, list[MarketAlert]] = {}
    for alert in alerts:
        group_id = f"security:{alert.security_id}" if alert.security_id else alert.alert_id
        grouped.setdefault(group_id, []).append(alert)
    return [_alert_group(group_id, items) for group_id, items in grouped.items()]


def _alert_group(group_id: str, alerts: list[MarketAlert]) -> MarketAlertGroup:
    primary = max(alerts, key=lambda alert: _severity_rank(alert.severity))
    kinds = list(dict.fromkeys(alert.kind for alert in alerts))
    return MarketAlertGroup(
        group_id=group_id,
        severity=primary.severity,
        kinds=kinds,
        title=_group_title(primary, alerts),
        message=_group_message(alerts),
        triggered_at=max(alert.triggered_at for alert in alerts),
        alert_count=len(alerts),
        security_id=primary.security_id,
        name=primary.name,
        industry_code=primary.industry_code,
        snapshot_time=primary.snapshot_time,
        alerts=alerts,
    )


def _group_title(primary: MarketAlert, alerts: list[MarketAlert]) -> str:
    if primary.security_id is None:
        return primary.title
    return f"{primary.name} 触发 {len(alerts)} 项告警"


def _group_message(alerts: list[MarketAlert]) -> str:
    if len(alerts) == 1:
        return alerts[0].message
    titles = "、".join(dict.fromkeys(alert.title for alert in alerts))
    return f"触发项: {titles}"


def _group_sort_key(group: MarketAlertGroup) -> tuple[int, datetime, int, str]:
    return (
        _severity_rank(group.severity),
        group.triggered_at,
        group.alert_count,
        group.group_id,
    )


def _severity_rank(severity: AlertSeverity) -> int:
    ranks = {
        AlertSeverity.INFO: 1,
        AlertSeverity.MEDIUM: 2,
        AlertSeverity.HIGH: 3,
    }
    return ranks[severity]


def _row_alerts(row: dict[str, Any], rules: dict[str, RuleConfig]) -> list[MarketAlert]:
    alerts: list[MarketAlert] = []
    change_pct = _float(row.get("change_pct"))
    volume_ratio = _float(row.get("volume_ratio"))

    limit_up = rules.get("limit_up")
    if (
        limit_up is not None
        and limit_up.enabled
        and change_pct is not None
        and change_pct >= limit_up.condition.value
    ):
        alerts.append(_stock_alert(row, limit_up, "limit_up", "涨停告警", change_pct))

    limit_down = rules.get("limit_down")
    if (
        limit_down is not None
        and limit_down.enabled
        and change_pct is not None
        and change_pct <= limit_down.condition.value
    ):
        alerts.append(_stock_alert(row, limit_down, "limit_down", "跌停告警", change_pct))

    volume_surge = rules.get("volume_surge")
    if (
        volume_surge is not None
        and volume_surge.enabled
        and volume_ratio is not None
        and volume_ratio >= volume_surge.condition.value
    ):
        alerts.append(_stock_alert(row, volume_surge, "volume_surge", "放量告警", volume_ratio))

    price_spike = rules.get("price_spike")
    if (
        price_spike is not None
        and price_spike.enabled
        and change_pct is not None
        and abs(change_pct) >= price_spike.condition.value
    ):
        alerts.append(
            _stock_alert(
                row,
                price_spike,
                "extreme_move",
                "异常涨跌幅",
                change_pct,
                metric="change_pct",
            )
        )

    return alerts


def _stock_alert(
    row: dict[str, Any],
    rule: RuleConfig,
    kind: AlertKind,
    title: str,
    value: float,
    *,
    metric: str | None = None,
) -> MarketAlert:
    metric = metric or rule.condition.field
    threshold = rule.condition.value
    security_id = str(row["security_id"])
    return MarketAlert(
        alert_id=f"{kind}:{security_id}",
        severity=rule.severity,
        kind=kind,
        title=title,
        message=_stock_message(row, metric, value, threshold),
        triggered_at=_datetime(row.get("fetched_at")) or datetime.now(UTC),
        security_id=security_id,
        name=str(row["name"]),
        industry_code=row.get("industry_code"),
        metric=metric,
        value=value,
        threshold=threshold,
        snapshot_time=_datetime(row.get("snapshot_time")),
    )


def _stock_message(row: dict[str, Any], metric: str, value: float, threshold: float) -> str:
    name = row["name"]
    security_id = row["security_id"]
    return f"{name}({security_id}) {metric}={value:.2f}, 阈值 {threshold:.2f}"


def _rule_threshold(rule: RuleConfig | None, fallback: float) -> float:
    return rule.condition.value if rule is not None else fallback


def _float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _datetime(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _aggregate_repo(duckdb_path: Path) -> tuple[AggregateRepo, DuckDBStore]:
    store = DuckDBStore(duckdb_path, read_only=True)
    return AggregateRepo(store), store
