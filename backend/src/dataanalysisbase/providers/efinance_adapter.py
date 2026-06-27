"""Efinance provider adapter."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from typing import Any, cast

from dataanalysisbase.common.errors import InvalidSecurityId, ProviderError
from dataanalysisbase.domain.symbols import SecurityId

INDUSTRY_MAPPING_DATASET = "industry_mapping"
INDUSTRY_FIELD_NAMES = ("industry", "industry_name", "所属行业", "行业", "板块")


class EfinanceAdapter:
    """Fetch and normalize optional A-share reference data from efinance."""

    name = "efinance"

    def __init__(
        self,
        *,
        realtime_quotes_fetcher: Callable[..., Any] | None = None,
    ) -> None:
        self._realtime_quotes_fetcher = realtime_quotes_fetcher

    def fetch_industry_mapping(self) -> dict[str, str]:
        """Fetch security-to-industry mapping from efinance realtime quotes."""

        try:
            records = _records_from_frame(self._realtime_quotes_fetcher_or_default()())
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(self.name, INDUSTRY_MAPPING_DATASET, str(exc)) from exc

        if records and not any(_has_any_field(record, INDUSTRY_FIELD_NAMES) for record in records):
            raise ProviderError(
                self.name,
                INDUSTRY_MAPPING_DATASET,
                "efinance realtime quotes do not include industry fields",
                retryable=False,
            )

        mapping: dict[str, str] = {}
        for record in records:
            security_id = _security_id_from_record(record)
            industry = _string_value(record, *INDUSTRY_FIELD_NAMES)
            if security_id is not None and industry is not None:
                mapping[security_id] = industry
        return mapping

    def _realtime_quotes_fetcher_or_default(self) -> Callable[..., Any]:
        if self._realtime_quotes_fetcher is not None:
            return self._realtime_quotes_fetcher

        try:
            ef = importlib.import_module("efinance")
        except ImportError as exc:
            raise ProviderError(
                self.name,
                INDUSTRY_MAPPING_DATASET,
                "efinance is not installed; install backend providers extra",
                retryable=False,
            ) from exc

        stock = getattr(ef, "stock", None)
        get_realtime_quotes = getattr(stock, "get_realtime_quotes", None)
        if not callable(get_realtime_quotes):
            raise ProviderError(
                self.name,
                INDUSTRY_MAPPING_DATASET,
                "efinance.stock.get_realtime_quotes is not available",
                retryable=False,
            )
        return cast(Callable[..., Any], get_realtime_quotes)


def _records_from_frame(frame: Any) -> list[Mapping[str, Any]]:
    if frame is None:
        return []
    if hasattr(frame, "to_dict"):
        raw = frame.to_dict(orient="records")
        if isinstance(raw, list):
            return [record for record in raw if isinstance(record, Mapping)]
    if isinstance(frame, list):
        return [record for record in frame if isinstance(record, Mapping)]
    msg = "efinance response must be a DataFrame-like object"
    raise TypeError(msg)


def _security_id_from_record(record: Mapping[str, Any]) -> str | None:
    raw_code = _string_value(
        record,
        "security_id",
        "code",
        "stock_code",
        "股票代码",
        "代码",
        "symbol",
    )
    if raw_code is None:
        return None
    try:
        return str(SecurityId.parse(raw_code))
    except InvalidSecurityId:
        return None


def _string_value(record: Mapping[str, Any], *names: str) -> str | None:
    for name in names:
        if name in record:
            value = record[name]
            if value is None:
                return None
            text = str(value).strip()
            return text or None
    return None


def _has_any_field(record: Mapping[str, Any], names: tuple[str, ...]) -> bool:
    return any(name in record for name in names)
