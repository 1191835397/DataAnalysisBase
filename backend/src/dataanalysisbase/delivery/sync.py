"""Manual sync command helpers."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, cast
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, ConfigDict, Field

from dataanalysisbase.common.errors import ConfigError
from dataanalysisbase.config_loader import load_providers, load_settings, load_sync_schedule
from dataanalysisbase.config_loader.providers_cfg import ProviderEntry
from dataanalysisbase.domain.contracts import SyncResult
from dataanalysisbase.domain.enums import DatasetType
from dataanalysisbase.ingest import MarketBulkSync
from dataanalysisbase.providers import (
    AkshareAdapter,
    BaostockAdapter,
    EfinanceAdapter,
    MarketDataProvider,
    ProviderRegistry,
    TushareAdapter,
)
from dataanalysisbase.providers.industry_mapping import (
    IndustryMappingBackfillResult,
    IndustryMappingCoverageResult,
    IndustryMappingProvider,
    IndustryMappingSyncResult,
    load_industry_mapping_file,
    normalize_security_id,
    write_industry_mapping_csv,
    write_missing_industry_mapping_csv,
)
from dataanalysisbase.storage import AggregateRepo, DuckDBStore, SnapshotRepo


class TradeCalendarProvider(Protocol):
    """Provider protocol for exchange trading dates."""

    name: str

    def fetch_trade_dates(self) -> set[date]:
        """Fetch known exchange trading dates."""


class TradeCalendarSyncResult(BaseModel):
    """Result of updating runtime freshness calendar overrides."""

    model_config = ConfigDict(frozen=True)

    task: str = "trade_calendar_sync"
    status: str
    source: str
    path: str
    year: int
    coverage_start: date | None
    coverage_end: date | None
    trade_dates: int
    holidays: int
    makeup_trading_days: int
    added_holidays: int = 0
    added_makeup_trading_days: int = 0
    removed_holidays: int = 0
    removed_makeup_trading_days: int = 0
    errors: list[str] = Field(default_factory=list)


def run_market_sync(
    snapshot_time: datetime,
    *,
    config_dir: Path | None = None,
    duckdb_path: Path | None = None,
    provider: MarketDataProvider | None = None,
) -> SyncResult:
    """Execute one whole-market sync run."""

    settings = load_settings()
    resolved_config_dir = config_dir or settings.config_dir
    resolved_duckdb_path = duckdb_path or settings.duckdb_path
    selected_provider = (
        provider or ProviderRegistry(load_providers(resolved_config_dir)).market_snapshot_provider()
    )

    store = DuckDBStore(resolved_duckdb_path)
    try:
        store.init_schema()
        sync = MarketBulkSync(selected_provider, SnapshotRepo(store), AggregateRepo(store))
        return sync.run_once(snapshot_time)
    finally:
        store.close()


def run_industry_mapping_sync(
    *,
    config_dir: Path | None = None,
    provider: IndustryMappingProvider | None = None,
    provider_name: str | None = None,
) -> IndustryMappingSyncResult:
    """Fetch provider industry membership and write the local fallback mapping file."""

    settings = load_settings()
    resolved_config_dir = config_dir or settings.config_dir
    providers = load_providers(resolved_config_dir)
    provider_config = _akshare_config(providers.providers)
    target_path = _resolve_data_path(settings.data_dir, provider_config.industry_mapping_path)
    try:
        selected_providers = (
            [provider]
            if provider is not None
            else _industry_mapping_providers(
                providers.providers,
                provider_name=provider_name,
                tushare_token=settings.tushare_token,
            )
        )
    except ValueError as exc:
        return IndustryMappingSyncResult(
            status="failed",
            source=provider_name or "none",
            path=str(target_path),
            records=0,
            errors=[str(exc)],
        )

    if not selected_providers:
        return IndustryMappingSyncResult(
            status="failed",
            source="none",
            path=str(target_path),
            records=0,
            errors=["No enabled provider supports industry_mapping"],
        )

    if provider is not None or provider_name is not None:
        errors: list[str] = []
        for selected_provider in selected_providers:
            result = _try_write_industry_mapping(selected_provider, target_path)
            if result.status == "success":
                return result.model_copy(update={"errors": errors}) if errors else result
            errors.extend(f"{selected_provider.name}: {error}" for error in result.errors)

        return IndustryMappingSyncResult(
            status="failed",
            source=",".join(provider.name for provider in selected_providers),
            path=str(target_path),
            records=0,
            errors=errors,
        )

    result = _try_write_merged_industry_mapping(selected_providers, target_path)
    if result.status == "success":
        return result

    return IndustryMappingSyncResult(
        status="failed",
        source=",".join(provider.name for provider in selected_providers),
        path=str(target_path),
        records=0,
        errors=result.errors,
    )


def run_trade_calendar_sync(
    *,
    config_dir: Path | None = None,
    provider: TradeCalendarProvider | None = None,
    year: int | None = None,
    through_date: date | None = None,
) -> TradeCalendarSyncResult:
    """Fetch exchange trade dates and update sync_schedule calendar overrides."""

    settings = load_settings()
    resolved_config_dir = config_dir or settings.config_dir
    target_path = resolved_config_dir / "sync_schedule.yaml"
    selected_provider = provider or AkshareAdapter()
    selected_year = _selected_calendar_year(year=year, through_date=through_date)

    try:
        trade_dates = selected_provider.fetch_trade_dates()
        if not trade_dates:
            raise ValueError("provider returned 0 trade calendar records")
        start, end = _trade_calendar_window(
            trade_dates,
            year=selected_year,
            through_date=through_date,
        )
        computed_holidays, computed_makeup_days = _calendar_overrides(
            trade_dates,
            start=start,
            end=end,
        )
        schedule = load_sync_schedule(resolved_config_dir)
        holidays = _merge_calendar_dates(schedule.holidays, computed_holidays, start=start, end=end)
        makeup_days = _merge_calendar_dates(
            schedule.makeup_trading_days,
            computed_makeup_days,
            start=start,
            end=end,
        )
        _write_sync_schedule_calendar(
            target_path,
            holidays=holidays,
            makeup_trading_days=makeup_days,
        )
    except Exception as exc:
        return TradeCalendarSyncResult(
            status="failed",
            source=selected_provider.name,
            path=str(target_path),
            year=selected_year,
            coverage_start=None,
            coverage_end=None,
            trade_dates=0,
            holidays=0,
            makeup_trading_days=0,
            errors=[str(exc)],
        )

    old_holidays = set(schedule.holidays)
    old_makeup_days = set(schedule.makeup_trading_days)
    new_holidays = set(holidays)
    new_makeup_days = set(makeup_days)
    return TradeCalendarSyncResult(
        status="success",
        source=selected_provider.name,
        path=str(target_path),
        year=selected_year,
        coverage_start=start,
        coverage_end=end,
        trade_dates=sum(1 for trade_date in trade_dates if start <= trade_date <= end),
        holidays=len(holidays),
        makeup_trading_days=len(makeup_days),
        added_holidays=len(new_holidays - old_holidays),
        added_makeup_trading_days=len(new_makeup_days - old_makeup_days),
        removed_holidays=len(old_holidays - new_holidays),
        removed_makeup_trading_days=len(old_makeup_days - new_makeup_days),
    )


def _try_write_industry_mapping(
    selected_provider: IndustryMappingProvider,
    target_path: Path,
) -> IndustryMappingSyncResult:
    try:
        mapping = selected_provider.fetch_industry_mapping()
        if not mapping:
            return IndustryMappingSyncResult(
                status="failed",
                source=selected_provider.name,
                path=str(target_path),
                records=0,
                errors=["provider returned 0 industry mapping records"],
            )
        records = write_industry_mapping_csv(target_path, mapping)
    except Exception as exc:
        return IndustryMappingSyncResult(
            status="failed",
            source=selected_provider.name,
            path=str(target_path),
            records=0,
            errors=[str(exc)],
        )

    return IndustryMappingSyncResult(
        status="success",
        source=selected_provider.name,
        path=str(target_path),
        records=records,
    )


def _try_write_merged_industry_mapping(
    selected_providers: list[IndustryMappingProvider],
    target_path: Path,
) -> IndustryMappingSyncResult:
    merged: dict[str, str] = {}
    successful_sources: list[str] = []
    errors: list[str] = []

    for selected_provider in selected_providers:
        try:
            mapping = selected_provider.fetch_industry_mapping()
        except Exception as exc:
            errors.append(f"{selected_provider.name}: {exc}")
            continue

        if not mapping:
            errors.append(f"{selected_provider.name}: provider returned 0 industry mapping records")
            continue

        successful_sources.append(selected_provider.name)
        for security_id, industry in mapping.items():
            if security_id not in merged:
                merged[security_id] = industry

    if not merged:
        return IndustryMappingSyncResult(
            status="failed",
            source=",".join(provider.name for provider in selected_providers),
            path=str(target_path),
            records=0,
            errors=errors,
        )

    try:
        records = write_industry_mapping_csv(target_path, merged)
    except Exception as exc:
        return IndustryMappingSyncResult(
            status="failed",
            source=",".join(successful_sources),
            path=str(target_path),
            records=0,
            errors=[*errors, str(exc)],
        )

    return IndustryMappingSyncResult(
        status="success",
        source=",".join(successful_sources),
        path=str(target_path),
        records=records,
        errors=errors,
    )


def run_industry_mapping_backfill(
    *,
    config_dir: Path | None = None,
    duckdb_path: Path | None = None,
    mapping_path: Path | None = None,
) -> IndustryMappingBackfillResult:
    """Apply the local industry mapping file to the latest committed market snapshot."""

    settings = load_settings()
    resolved_config_dir = config_dir or settings.config_dir
    resolved_duckdb_path = duckdb_path or settings.duckdb_path
    target_path = mapping_path or _default_industry_mapping_path(
        settings.data_dir,
        resolved_config_dir,
    )

    try:
        mapping = _load_industry_mapping(target_path)
    except Exception as exc:
        return IndustryMappingBackfillResult(
            status="failed",
            path=str(target_path),
            snapshot_time=None,
            mapping_records=0,
            backfilled=0,
            errors=[str(exc)],
        )
    if not mapping:
        return IndustryMappingBackfillResult(
            status="failed",
            path=str(target_path),
            snapshot_time=None,
            mapping_records=0,
            backfilled=0,
            errors=["industry mapping file contains 0 usable records"],
        )

    store = DuckDBStore(resolved_duckdb_path)
    try:
        store.init_schema()
        snapshot_repo = SnapshotRepo(store)
        aggregate_repo = AggregateRepo(store)
        snapshot_time = snapshot_repo.latest_committed()
        if snapshot_time is None:
            return IndustryMappingBackfillResult(
                status="failed",
                path=str(target_path),
                snapshot_time=None,
                mapping_records=len(mapping),
                backfilled=0,
                errors=["no committed market snapshot is available"],
            )
        backfilled = snapshot_repo.backfill_industries(snapshot_time, mapping)
        aggregate_repo.refresh_latest(snapshot_time)
        aggregate_repo.refresh_overview(snapshot_time)
        aggregate_repo.refresh_industry(snapshot_time)
        return IndustryMappingBackfillResult(
            status="success",
            path=str(target_path),
            snapshot_time=snapshot_time.isoformat(),
            mapping_records=len(mapping),
            backfilled=backfilled,
        )
    except Exception as exc:
        return IndustryMappingBackfillResult(
            status="failed",
            path=str(target_path),
            snapshot_time=None,
            mapping_records=len(mapping),
            backfilled=0,
            errors=[str(exc)],
        )
    finally:
        store.close()


def inspect_industry_mapping_coverage(
    *,
    config_dir: Path | None = None,
    duckdb_path: Path | None = None,
    mapping_path: Path | None = None,
    missing_output: Path | None = None,
) -> IndustryMappingCoverageResult:
    """Inspect latest snapshot industry mapping coverage without mutating DuckDB."""

    settings = load_settings()
    resolved_config_dir = config_dir or settings.config_dir
    resolved_duckdb_path = duckdb_path or settings.duckdb_path
    target_path = mapping_path or _default_industry_mapping_path(
        settings.data_dir,
        resolved_config_dir,
    )

    try:
        mapping = _load_industry_mapping(target_path)
    except Exception as exc:
        return IndustryMappingCoverageResult(
            status="failed",
            path=str(target_path),
            snapshot_time=None,
            total_snapshot_records=0,
            mapped_snapshot_records=0,
            unknown_snapshot_records=0,
            mapping_records=0,
            usable_mapping_records=0,
            missing_mapping_records=0,
            coverage_ratio=0,
            missing_output=str(missing_output) if missing_output else None,
            errors=[str(exc)],
        )

    store = DuckDBStore(resolved_duckdb_path, read_only=True)
    try:
        rows = store.query(
            """
            SELECT snapshot_time, security_id, name, industry_code
            FROM latest_market_snapshot
            ORDER BY security_id
            """
        )
    except Exception as exc:
        return IndustryMappingCoverageResult(
            status="failed",
            path=str(target_path),
            snapshot_time=None,
            total_snapshot_records=0,
            mapped_snapshot_records=0,
            unknown_snapshot_records=0,
            mapping_records=len(mapping),
            usable_mapping_records=len(mapping),
            missing_mapping_records=0,
            coverage_ratio=0,
            missing_output=str(missing_output) if missing_output else None,
            errors=[str(exc)],
        )
    finally:
        store.close()

    total = len(rows)
    mapped_snapshot_records = sum(1 for row in rows if _has_industry(row.get("industry_code")))
    unknown_snapshot_records = total - mapped_snapshot_records
    missing_rows = [
        {
            "security_id": str(row["security_id"]),
            "name": str(row["name"]),
            "industry": "",
        }
        for row in rows
        if not _has_industry(row.get("industry_code"))
        and str(row["security_id"]) not in mapping
    ]
    written_output = None
    errors: list[str] = []
    if missing_output is not None:
        try:
            write_missing_industry_mapping_csv(missing_output, missing_rows)
            written_output = str(missing_output)
        except Exception as exc:
            errors.append(str(exc))

    snapshot_time = rows[0]["snapshot_time"].isoformat() if rows else None
    status = "success" if not errors else "partial"
    return IndustryMappingCoverageResult(
        status=status,
        path=str(target_path),
        snapshot_time=snapshot_time,
        total_snapshot_records=total,
        mapped_snapshot_records=mapped_snapshot_records,
        unknown_snapshot_records=unknown_snapshot_records,
        mapping_records=len(mapping),
        usable_mapping_records=len(mapping),
        missing_mapping_records=len(missing_rows),
        coverage_ratio=0 if total == 0 else mapped_snapshot_records / total,
        missing_output=written_output,
        errors=errors,
    )


def _industry_mapping_providers(
    providers: dict[str, ProviderEntry],
    *,
    provider_name: str | None = None,
    tushare_token: str | None,
) -> list[IndustryMappingProvider]:
    candidates = [
        (name, provider)
        for name, provider in providers.items()
        if _matches_industry_mapping_provider(
            name,
            provider,
            provider_name,
            tushare_token=tushare_token,
        )
    ]
    return [
        _build_industry_mapping_provider(name, provider_config, tushare_token=tushare_token)
        for name, provider_config in sorted(
            candidates,
            key=lambda item: (item[1].priority, item[0]),
        )
    ]


def _matches_industry_mapping_provider(
    name: str,
    provider: ProviderEntry,
    provider_name: str | None,
    *,
    tushare_token: str | None,
) -> bool:
    if DatasetType.INDUSTRY_MAPPING not in provider.datasets:
        return False
    if provider_name is not None:
        return name == provider_name
    return provider.token_env != "DAB_TUSHARE_TOKEN" or bool(tushare_token)


def _build_industry_mapping_provider(
    name: str,
    provider_config: ProviderEntry,
    *,
    tushare_token: str | None,
) -> IndustryMappingProvider:
    if name == "akshare":
        return AkshareAdapter()
    if name == "baostock":
        return BaostockAdapter()
    if name == "efinance":
        return EfinanceAdapter()
    if name == "tushare":
        token = tushare_token
        if provider_config.token_env and token is None:
            token = None
        return TushareAdapter(token=token)
    msg = f"Unsupported industry_mapping provider: {name}"
    raise ValueError(msg)


def _akshare_config(providers: dict[str, ProviderEntry]) -> ProviderEntry:
    provider = providers.get("akshare")
    if provider is None:
        msg = "providers.yaml missing provider: akshare"
        raise ValueError(msg)
    return provider


def _default_industry_mapping_path(data_dir: Path, config_dir: Path) -> Path:
    providers = load_providers(config_dir)
    provider_config = _akshare_config(providers.providers)
    return _resolve_data_path(data_dir, provider_config.industry_mapping_path)


def _load_industry_mapping(path: Path) -> dict[str, str]:
    records = load_industry_mapping_file(path)
    mapping: dict[str, str] = {}
    for record in records:
        security_id = _string_field(record, "security_id", "code", "symbol")
        industry = _string_field(record, "industry", "industry_code", "industry_name")
        normalized_security_id = normalize_security_id(security_id)
        if normalized_security_id and industry:
            mapping[normalized_security_id] = industry
    return mapping


def _string_field(record: dict[str, object], *names: str) -> str | None:
    for name in names:
        value = record.get(name)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _resolve_data_path(data_dir: Path, path: Path | None) -> Path:
    if path is None:
        msg = "akshare.industry_mapping_path is not configured"
        raise ValueError(msg)
    return path if path.is_absolute() else data_dir / path


def _has_industry(value: object) -> bool:
    return value is not None and str(value).strip() not in {"", "UNKNOWN"}


def _selected_calendar_year(*, year: int | None, through_date: date | None) -> int:
    if year is not None:
        return year
    if through_date is not None:
        return through_date.year
    return datetime.now(ZoneInfo("Asia/Shanghai")).year


def _trade_calendar_window(
    trade_dates: set[date],
    *,
    year: int,
    through_date: date | None,
) -> tuple[date, date]:
    year_dates = {trade_date for trade_date in trade_dates if trade_date.year == year}
    if not year_dates:
        msg = f"provider returned 0 trade calendar records for {year}"
        raise ValueError(msg)
    if through_date is not None and through_date.year != year:
        msg = f"through_date {through_date.isoformat()} is outside selected year {year}"
        raise ValueError(msg)

    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    start = date(year, 1, 1)
    if through_date is not None:
        end = through_date
    elif year < today.year:
        end = date(year, 12, 31)
    elif year == today.year:
        end = today
    else:
        end = max(year_dates)

    if end < start:
        msg = f"trade calendar coverage end {end.isoformat()} is before {start.isoformat()}"
        raise ValueError(msg)
    return start, min(end, date(year, 12, 31))


def _calendar_overrides(
    trade_dates: set[date],
    *,
    start: date,
    end: date,
) -> tuple[list[date], list[date]]:
    holidays: list[date] = []
    makeup_trading_days: list[date] = []
    current = start
    while current <= end:
        is_weekday = current.weekday() < 5
        is_trade_date = current in trade_dates
        if is_weekday and not is_trade_date:
            holidays.append(current)
        elif not is_weekday and is_trade_date:
            makeup_trading_days.append(current)
        current += timedelta(days=1)
    return holidays, makeup_trading_days


def _merge_calendar_dates(
    existing: list[date],
    computed: list[date],
    *,
    start: date,
    end: date,
) -> list[date]:
    preserved = {day for day in existing if day < start or day > end}
    return sorted(preserved | set(computed))


def _write_sync_schedule_calendar(
    path: Path,
    *,
    holidays: list[date],
    makeup_trading_days: list[date],
) -> None:
    try:
        original_text = path.read_text(encoding="utf-8")
        raw = yaml.safe_load(original_text) or {}
    except OSError as exc:
        raise ConfigError(f"Failed to read config file {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"Config file must contain a mapping: {path}")

    _ = cast(dict[str, Any], raw)
    rendered_calendar = _render_calendar_block(
        holidays=holidays,
        makeup_trading_days=makeup_trading_days,
    )
    updated_text = _replace_top_level_calendar_block(original_text, rendered_calendar)
    try:
        path.write_text(updated_text, encoding="utf-8", newline="")
    except OSError as exc:
        raise ConfigError(f"Failed to write config file {path}: {exc}") from exc


def _render_calendar_block(
    *,
    holidays: list[date],
    makeup_trading_days: list[date],
) -> list[str]:
    return [
        *_render_date_list("holidays", holidays),
        *_render_date_list("makeup_trading_days", makeup_trading_days),
    ]


def _render_date_list(name: str, days: list[date]) -> list[str]:
    if not days:
        return [f"{name}: []"]
    return [f"{name}:", *[f'  - "{day.isoformat()}"' for day in days]]


def _replace_top_level_calendar_block(text: str, calendar_lines: list[str]) -> str:
    lines = text.splitlines()
    ranges = [
        _top_level_key_range(lines, "holidays"),
        _top_level_key_range(lines, "makeup_trading_days"),
    ]
    existing_ranges = [item for item in ranges if item is not None]
    if existing_ranges:
        start = min(item[0] for item in existing_ranges)
        end = max(item[1] for item in existing_ranges)
        updated_lines = [*lines[:start], *calendar_lines, *lines[end:]]
    else:
        insert_at = _top_level_key_range(lines, "jobs")
        target_index = insert_at[0] if insert_at is not None else len(lines)
        prefix = lines[:target_index]
        suffix = lines[target_index:]
        if prefix and prefix[-1] != "":
            prefix = [*prefix, ""]
        updated_lines = [*prefix, *calendar_lines, "", *suffix]

    trailing_newline = "\n" if text.endswith(("\n", "\r\n")) else ""
    return "\n".join(updated_lines) + trailing_newline


def _top_level_key_range(lines: list[str], key: str) -> tuple[int, int] | None:
    prefix = f"{key}:"
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            end = index + 1
            while end < len(lines) and (
                lines[end].startswith(" ") or lines[end].startswith("-") or lines[end] == ""
            ):
                end += 1
            return index, end
    return None
