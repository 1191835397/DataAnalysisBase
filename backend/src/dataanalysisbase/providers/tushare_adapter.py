"""Tushare provider adapter."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from typing import Any, cast

from dataanalysisbase.common.errors import InvalidSecurityId, ProviderError
from dataanalysisbase.domain.symbols import SecurityId

INDUSTRY_MAPPING_DATASET = "industry_mapping"


class TushareAdapter:
    """Fetch and normalize A-share reference data from Tushare."""

    name = "tushare"

    def __init__(
        self,
        *,
        token: str | None = None,
        stock_basic_fetcher: Callable[..., Any] | None = None,
    ) -> None:
        self._token = token
        self._stock_basic_fetcher = stock_basic_fetcher

    def fetch_industry_mapping(self) -> dict[str, str]:
        """Fetch security-to-industry mapping from Tushare stock_basic."""

        try:
            records = _records_from_frame(
                self._stock_basic_fetcher_or_default()(
                    exchange="",
                    list_status="L",
                    fields="ts_code,name,industry",
                )
            )
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(self.name, INDUSTRY_MAPPING_DATASET, str(exc)) from exc

        mapping: dict[str, str] = {}
        for record in records:
            security_id = _security_id_from_record(record)
            industry = _string_value(record, "industry", "industry_name", "行业")
            if security_id is not None and industry is not None:
                mapping[security_id] = industry
        return mapping

    def _stock_basic_fetcher_or_default(self) -> Callable[..., Any]:
        if self._stock_basic_fetcher is not None:
            return self._stock_basic_fetcher

        if not self._token:
            raise ProviderError(
                self.name,
                INDUSTRY_MAPPING_DATASET,
                "Tushare token is not configured",
                retryable=False,
            )

        try:
            ts = importlib.import_module("tushare")
        except ImportError as exc:
            raise ProviderError(
                self.name,
                INDUSTRY_MAPPING_DATASET,
                "tushare is not installed; install backend providers extra",
                retryable=False,
            ) from exc

        pro = ts.pro_api(self._token)
        stock_basic = getattr(pro, "stock_basic", None)
        if not callable(stock_basic):
            raise ProviderError(
                self.name,
                INDUSTRY_MAPPING_DATASET,
                "Tushare pro client does not provide stock_basic",
                retryable=False,
            )
        return cast(Callable[..., Any], stock_basic)


def _records_from_frame(frame: Any) -> list[Mapping[str, Any]]:
    if frame is None:
        return []
    if hasattr(frame, "to_dict"):
        raw = frame.to_dict(orient="records")
        if isinstance(raw, list):
            return [record for record in raw if isinstance(record, Mapping)]
    if isinstance(frame, list):
        return [record for record in frame if isinstance(record, Mapping)]
    msg = "Tushare response must be a DataFrame-like object"
    raise TypeError(msg)


def _security_id_from_record(record: Mapping[str, Any]) -> str | None:
    raw_code = _string_value(record, "ts_code", "security_id", "code", "symbol")
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
