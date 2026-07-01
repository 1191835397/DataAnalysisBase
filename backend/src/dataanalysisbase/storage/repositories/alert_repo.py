"""Repository for persisted surveillance alerts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from dataanalysisbase.domain.contracts import SurveillanceAlertRecord
from dataanalysisbase.domain.enums import AlertStatus
from dataanalysisbase.storage.repositories.base import BaseRepo


class AlertRepo(BaseRepo):
    """Persist alert lifecycle state and current trigger metadata."""

    def upsert_many(self, alerts: list[SurveillanceAlertRecord]) -> None:
        if not alerts:
            return
        values = [_alert_values(alert) for alert in alerts]
        with self.store.transaction() as conn:
            conn.executemany(
                """
                INSERT INTO surveillance_alerts (
                    alert_id, rule_id, severity, kind, status, title, message,
                    first_triggered_at, last_triggered_at, trigger_count,
                    security_id, name, industry_code, metric, value, threshold,
                    snapshot_time, source, created_at, updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now(), now()
                )
                ON CONFLICT (alert_id) DO UPDATE SET
                    rule_id = excluded.rule_id,
                    severity = excluded.severity,
                    kind = excluded.kind,
                    status = CASE
                        WHEN excluded.last_triggered_at > surveillance_alerts.last_triggered_at
                        THEN excluded.status
                        ELSE surveillance_alerts.status
                    END,
                    title = excluded.title,
                    message = excluded.message,
                    last_triggered_at = excluded.last_triggered_at,
                    trigger_count = CASE
                        WHEN excluded.last_triggered_at > surveillance_alerts.last_triggered_at
                        THEN surveillance_alerts.trigger_count + 1
                        ELSE surveillance_alerts.trigger_count
                    END,
                    security_id = excluded.security_id,
                    name = excluded.name,
                    industry_code = excluded.industry_code,
                    metric = excluded.metric,
                    value = excluded.value,
                    threshold = excluded.threshold,
                    snapshot_time = excluded.snapshot_time,
                    source = excluded.source,
                    updated_at = now()
                """,
                values,
            )

    def list_recent(
        self,
        *,
        limit: int,
        statuses: list[AlertStatus] | None = None,
    ) -> list[SurveillanceAlertRecord]:
        safe_limit = max(limit, 1)
        params: list[Any] = []
        where = ""
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            where = f"WHERE status IN ({placeholders})"
            params.extend(status.value for status in statuses)
        rows = self.store.query(
            f"""
            SELECT alert_id, rule_id, severity, kind, status, title, message,
                   first_triggered_at, last_triggered_at, trigger_count,
                   security_id, name, industry_code, metric, value, threshold,
                   snapshot_time, source
            FROM surveillance_alerts
            {where}
            ORDER BY last_triggered_at DESC, alert_id ASC
            LIMIT ?
            """,
            [*params, safe_limit],
        )
        return [_row_to_alert(row) for row in rows]

    def list_for_security(self, security_id: str, *, limit: int) -> list[SurveillanceAlertRecord]:
        safe_limit = max(limit, 1)
        rows = self.store.query(
            """
            SELECT alert_id, rule_id, severity, kind, status, title, message,
                   first_triggered_at, last_triggered_at, trigger_count,
                   security_id, name, industry_code, metric, value, threshold,
                   snapshot_time, source
            FROM surveillance_alerts
            WHERE security_id = ?
            ORDER BY last_triggered_at DESC, alert_id ASC
            LIMIT ?
            """,
            [security_id, safe_limit],
        )
        return [_row_to_alert(row) for row in rows]

    def get(self, alert_id: str) -> SurveillanceAlertRecord | None:
        rows = self.store.query(
            """
            SELECT alert_id, rule_id, severity, kind, status, title, message,
                   first_triggered_at, last_triggered_at, trigger_count,
                   security_id, name, industry_code, metric, value, threshold,
                   snapshot_time, source
            FROM surveillance_alerts
            WHERE alert_id = ?
            """,
            [alert_id],
        )
        return _row_to_alert(rows[0]) if rows else None

    def update_status(
        self,
        alert_id: str,
        status: AlertStatus,
    ) -> SurveillanceAlertRecord | None:
        self.store.execute(
            """
            UPDATE surveillance_alerts
            SET status = ?, updated_at = now()
            WHERE alert_id = ?
            """,
            [status.value, alert_id],
        )
        return self.get(alert_id)


def _alert_values(alert: SurveillanceAlertRecord) -> list[Any]:
    return [
        alert.alert_id,
        alert.rule_id,
        alert.severity.value,
        alert.kind,
        alert.status.value,
        alert.title,
        alert.message,
        alert.first_triggered_at,
        alert.last_triggered_at,
        alert.trigger_count,
        alert.security_id,
        alert.name,
        alert.industry_code,
        alert.metric,
        alert.value,
        alert.threshold,
        alert.snapshot_time,
        alert.source,
    ]


def _row_to_alert(row: dict[str, Any]) -> SurveillanceAlertRecord:
    normalized = dict(row)
    for key in ("first_triggered_at", "last_triggered_at", "snapshot_time"):
        value = normalized.get(key)
        if isinstance(value, str):
            normalized[key] = datetime.fromisoformat(value)
    return SurveillanceAlertRecord.model_validate(normalized)
