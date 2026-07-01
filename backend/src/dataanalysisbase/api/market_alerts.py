"""Derived market alert API helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, cast

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

from dataanalysisbase.common.errors import ConfigError, StorageError
from dataanalysisbase.config_loader import load_settings, load_surveillance_rules
from dataanalysisbase.config_loader.surveillance_cfg import RuleConfig, SurveillanceRules
from dataanalysisbase.domain.contracts import SurveillanceAlertRecord
from dataanalysisbase.domain.enums import AlertSeverity, AlertStatus, DataStatus
from dataanalysisbase.domain.price_limits import limit_down_threshold, limit_up_threshold
from dataanalysisbase.observability.system_status import RuntimeStatus, build_runtime_status
from dataanalysisbase.storage import AggregateRepo, AlertRepo, DuckDBStore

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
    rule_id: str | None = None
    severity: AlertSeverity
    kind: AlertKind
    status: AlertStatus = AlertStatus.NEW
    title: str
    message: str
    triggered_at: datetime
    first_triggered_at: datetime | None = None
    last_triggered_at: datetime | None = None
    trigger_count: int = 1
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
    status: AlertStatus
    title: str
    message: str
    triggered_at: datetime
    first_triggered_at: datetime | None = None
    last_triggered_at: datetime | None = None
    alert_count: int
    security_id: str | None = None
    name: str | None = None
    industry_code: str | None = None
    snapshot_time: datetime | None = None
    alerts: list[MarketAlert]


class AlertStatusUpdate(BaseModel):
    """Request body for alert lifecycle transitions."""

    status: AlertStatus


def get_market_alerts(limit: int = 50) -> list[MarketAlert]:
    """Return current system and market snapshot alerts."""

    settings = load_settings()
    _refresh_persisted_alerts(settings.duckdb_path, settings.config_dir)
    repo, store = _alert_repo(settings.duckdb_path, read_only=True)
    try:
        return [_market_alert_from_record(alert) for alert in repo.list_recent(limit=limit)]
    except StorageError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"market alerts are not available: {exc}",
        ) from exc
    finally:
        store.close()


def update_market_alert_status(alert_id: str, status: AlertStatus) -> MarketAlert | None:
    """Update lifecycle state for one persisted alert."""

    settings = load_settings()
    repo, store = _alert_repo(settings.duckdb_path)
    try:
        updated = repo.update_status(alert_id, status)
    except StorageError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"market alerts are not available: {exc}",
        ) from exc
    finally:
        store.close()
    return _market_alert_from_record(updated) if updated is not None else None


def _refresh_persisted_alerts(duckdb_path: Path, config_dir: Path) -> None:
    derived = _derive_market_alerts()
    repo, store = _alert_repo(duckdb_path)
    try:
        rules = load_surveillance_rules(config_dir)
        records = [_record_from_market_alert(alert) for alert in derived]
        repo.upsert_many(_without_cooldown_hits(records, repo, rules))
    except (ConfigError, StorageError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"market alerts are not available: {exc}",
        ) from exc
    finally:
        store.close()


def _derive_market_alerts(limit: int = 200) -> list[MarketAlert]:
    """Derive current alerts from runtime status and latest market snapshot."""

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

    triggered_at = _system_triggered_at(status)
    if status.data_status == DataStatus.OFFLINE:
        return [
            MarketAlert(
                alert_id="system:offline",
                rule_id="system_offline",
                severity=AlertSeverity.HIGH,
                kind="offline",
                status=AlertStatus.NEW,
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
                rule_id="system_sync_failed",
                severity=AlertSeverity.HIGH,
                kind="sync_failed",
                status=AlertStatus.NEW,
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
                rule_id="system_partial_sync",
                severity=AlertSeverity.MEDIUM,
                kind="partial_sync",
                status=AlertStatus.NEW,
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
            rule_id="system_data_stale",
            severity=AlertSeverity.MEDIUM,
            kind="data_stale",
            status=AlertStatus.NEW,
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
        status=_group_status(alerts),
        title=_group_title(primary, alerts),
        message=_group_message(alerts),
        triggered_at=max(alert.triggered_at for alert in alerts),
        first_triggered_at=min(_first_triggered_at(alert) for alert in alerts),
        last_triggered_at=max(_last_triggered_at(alert) for alert in alerts),
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


def _group_status(alerts: list[MarketAlert]) -> AlertStatus:
    statuses = {alert.status for alert in alerts}
    if AlertStatus.NEW in statuses:
        return AlertStatus.NEW
    if AlertStatus.READ in statuses:
        return AlertStatus.READ
    if AlertStatus.HANDLED in statuses:
        return AlertStatus.HANDLED
    return AlertStatus.IGNORED


def _first_triggered_at(alert: MarketAlert) -> datetime:
    return alert.first_triggered_at or alert.triggered_at


def _last_triggered_at(alert: MarketAlert) -> datetime:
    return alert.last_triggered_at or alert.triggered_at


def _system_triggered_at(status: RuntimeStatus) -> datetime:
    if status.last_market_run is not None:
        return status.last_market_run.finished_at or status.last_market_run.started_at
    return status.latest_snapshot_time or status.generated_at


def _row_alerts(row: dict[str, Any], rules: dict[str, RuleConfig]) -> list[MarketAlert]:
    if _is_untradable_stock_row(row):
        return []

    alerts: list[MarketAlert] = []
    change_pct = _float(row.get("change_pct"))
    volume_ratio = _float(row.get("volume_ratio"))
    delta_price_pct = _float(row.get("delta_price_pct"))
    row_limit_up_threshold = _row_limit_up_threshold(row)
    row_limit_down_threshold = _row_limit_down_threshold(row)

    limit_up = rules.get("limit_up")
    if (
        limit_up is not None
        and limit_up.enabled
        and change_pct is not None
        and row_limit_up_threshold is not None
        and change_pct >= row_limit_up_threshold
    ):
        alerts.append(
            _stock_alert(
                row,
                limit_up,
                "limit_up",
                "涨停告警",
                change_pct,
                threshold=row_limit_up_threshold,
            )
        )

    limit_down = rules.get("limit_down")
    if (
        limit_down is not None
        and limit_down.enabled
        and change_pct is not None
        and row_limit_down_threshold is not None
        and change_pct <= row_limit_down_threshold
    ):
        alerts.append(
            _stock_alert(
                row,
                limit_down,
                "limit_down",
                "跌停告警",
                change_pct,
                threshold=row_limit_down_threshold,
            )
        )

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
        and not _bool(row.get("ex_dividend"))
        and delta_price_pct is not None
        and abs(delta_price_pct) >= price_spike.condition.value
    ):
        alerts.append(
            _stock_alert(
                row,
                price_spike,
                "extreme_move",
                "异常涨跌幅",
                delta_price_pct,
                metric=price_spike.condition.field,
            )
        )

    return alerts


def _is_untradable_stock_row(row: dict[str, Any]) -> bool:
    if _bool(row.get("is_suspended")):
        return True
    price = _float(row.get("price"))
    volume = _float(row.get("volume"))
    amount = _float(row.get("amount"))
    if price is None:
        return True
    return volume == 0 and amount == 0


def _row_limit_up_threshold(row: dict[str, Any]) -> float | None:
    value = _float(row.get("limit_up_threshold"))
    if value is not None:
        return value
    return limit_up_threshold(
        str(row["security_id"]),
        str(row["name"]),
        listing_date=_date(row.get("listing_date")),
        snapshot_date=_snapshot_date(row),
    )


def _row_limit_down_threshold(row: dict[str, Any]) -> float | None:
    value = _float(row.get("limit_down_threshold"))
    if value is not None:
        return value
    return limit_down_threshold(
        str(row["security_id"]),
        str(row["name"]),
        listing_date=_date(row.get("listing_date")),
        snapshot_date=_snapshot_date(row),
    )


def _stock_alert(
    row: dict[str, Any],
    rule: RuleConfig,
    kind: AlertKind,
    title: str,
    value: float,
    *,
    metric: str | None = None,
    threshold: float | None = None,
) -> MarketAlert:
    metric = metric or rule.condition.field
    threshold = threshold if threshold is not None else rule.condition.value
    security_id = str(row["security_id"])
    return MarketAlert(
        alert_id=f"{kind}:{security_id}",
        rule_id=rule.rule_id,
        severity=rule.severity,
        kind=kind,
        status=AlertStatus.NEW,
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


def _bool(value: object) -> bool:
    return bool(value) if isinstance(value, bool) else False


def _datetime(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else None


def _snapshot_date(row: dict[str, Any]) -> date | None:
    snapshot_time = _datetime(row.get("snapshot_time"))
    return snapshot_time.date() if snapshot_time is not None else None


def _aggregate_repo(duckdb_path: Path) -> tuple[AggregateRepo, DuckDBStore]:
    store = DuckDBStore(duckdb_path, read_only=True)
    return AggregateRepo(store), store


def _alert_repo(
    duckdb_path: Path,
    *,
    read_only: bool = False,
) -> tuple[AlertRepo, DuckDBStore]:
    store = DuckDBStore(duckdb_path, read_only=read_only)
    if not read_only:
        store.init_schema()
    return AlertRepo(store), store


def _record_from_market_alert(alert: MarketAlert) -> SurveillanceAlertRecord:
    return SurveillanceAlertRecord(
        alert_id=alert.alert_id,
        rule_id=alert.rule_id,
        severity=alert.severity,
        kind=alert.kind,
        status=alert.status,
        title=alert.title,
        message=alert.message,
        first_triggered_at=alert.first_triggered_at or alert.triggered_at,
        last_triggered_at=alert.last_triggered_at or alert.triggered_at,
        trigger_count=alert.trigger_count,
        security_id=alert.security_id,
        name=alert.name,
        industry_code=alert.industry_code,
        metric=alert.metric,
        value=alert.value,
        threshold=alert.threshold,
        snapshot_time=alert.snapshot_time,
        source="derived",
    )


def _market_alert_from_record(alert: SurveillanceAlertRecord) -> MarketAlert:
    return MarketAlert(
        alert_id=alert.alert_id,
        rule_id=alert.rule_id,
        severity=alert.severity,
        kind=_alert_kind(alert.kind),
        status=alert.status,
        title=alert.title,
        message=alert.message,
        triggered_at=alert.last_triggered_at,
        first_triggered_at=alert.first_triggered_at,
        last_triggered_at=alert.last_triggered_at,
        trigger_count=alert.trigger_count,
        security_id=alert.security_id,
        name=alert.name,
        industry_code=alert.industry_code,
        metric=alert.metric,
        value=alert.value,
        threshold=alert.threshold,
        snapshot_time=alert.snapshot_time,
    )


def _without_cooldown_hits(
    alerts: list[SurveillanceAlertRecord],
    repo: AlertRepo,
    rules: SurveillanceRules,
) -> list[SurveillanceAlertRecord]:
    return [
        alert
        for alert in alerts
        if not _is_cooling_down(alert, repo.get(alert.alert_id), rules)
    ]


def _is_cooling_down(
    alert: SurveillanceAlertRecord,
    existing: SurveillanceAlertRecord | None,
    rules: SurveillanceRules,
) -> bool:
    if existing is None:
        return False
    if alert.last_triggered_at <= existing.last_triggered_at:
        return False
    return alert.last_triggered_at < existing.last_triggered_at + timedelta(
        minutes=_cooldown_minutes(alert, rules)
    )


def _cooldown_minutes(alert: SurveillanceAlertRecord, rules: SurveillanceRules) -> int:
    if alert.rule_id and alert.rule_id in rules.rules:
        return rules.rules[alert.rule_id].cooldown_minutes
    return rules.dedupe.window_minutes


def _alert_kind(value: str) -> AlertKind:
    if value in (
        "data_stale",
        "sync_failed",
        "partial_sync",
        "offline",
        "limit_up",
        "limit_down",
        "volume_surge",
        "extreme_move",
    ):
        return cast(AlertKind, value)
    return "data_stale"
