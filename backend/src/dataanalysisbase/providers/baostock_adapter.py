"""BaoStock provider adapter."""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from typing import Any

from dataanalysisbase.common.errors import InvalidSecurityId, ProviderError
from dataanalysisbase.domain.symbols import SecurityId

INDUSTRY_MAPPING_DATASET = "industry_mapping"


class BaostockAdapter:
    """Fetch and normalize A-share industry mapping from BaoStock."""

    name = "baostock"

    def __init__(self, module: Any | None = None) -> None:
        self._module = module

    def fetch_industry_mapping(self) -> dict[str, str]:
        """Fetch security-to-industry mapping from BaoStock query_stock_industry."""

        bs = self._module_or_default()
        logged_in = False
        try:
            login_result = bs.login()
            logged_in = _is_success(login_result)
            if not logged_in:
                raise ProviderError(
                    self.name,
                    INDUSTRY_MAPPING_DATASET,
                    _error_message(login_result, "BaoStock login failed"),
                    retryable=False,
                )
            query_result = bs.query_stock_industry()
            if not _is_success(query_result):
                raise ProviderError(
                    self.name,
                    INDUSTRY_MAPPING_DATASET,
                    _error_message(query_result, "BaoStock query_stock_industry failed"),
                    retryable=True,
                )
            return _mapping_from_result(query_result)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(self.name, INDUSTRY_MAPPING_DATASET, str(exc)) from exc
        finally:
            if logged_in:
                bs.logout()

    def _module_or_default(self) -> Any:
        if self._module is not None:
            return self._module
        try:
            return importlib.import_module("baostock")
        except ImportError as exc:
            raise ProviderError(
                self.name,
                INDUSTRY_MAPPING_DATASET,
                "baostock is not installed; install backend providers extra",
                retryable=False,
            ) from exc


def _mapping_from_result(result: Any) -> dict[str, str]:
    fields = list(getattr(result, "fields", []))
    mapping: dict[str, str] = {}
    while result.next():
        row = dict(zip(fields, result.get_row_data(), strict=False))
        security_id = _security_id_from_record(row)
        industry = _string_value(row, "industry", "industryClassification", "industry_name")
        if security_id is not None and industry is not None:
            mapping[security_id] = industry
    return mapping


def _security_id_from_record(record: Mapping[str, Any]) -> str | None:
    raw_code = _string_value(record, "code", "security_id", "symbol")
    if raw_code is None:
        return None
    try:
        return str(SecurityId.parse(_normalize_baostock_code(raw_code)))
    except InvalidSecurityId:
        return None


def _normalize_baostock_code(raw_code: str) -> str:
    value = raw_code.strip()
    if "." not in value:
        return value
    market, symbol = value.split(".", 1)
    if market.lower() in {"sh", "sz", "bj"}:
        return f"{symbol}.{market.upper()}"
    return value


def _string_value(record: Mapping[str, Any], *names: str) -> str | None:
    for name in names:
        if name in record:
            value = record[name]
            if value is None:
                return None
            text = str(value).strip()
            return text or None
    return None


def _is_success(result: Any) -> bool:
    return str(getattr(result, "error_code", "")).strip() in {"", "0"}


def _error_message(result: Any, fallback: str) -> str:
    message = str(getattr(result, "error_msg", "")).strip()
    return message or fallback
