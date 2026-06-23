"""Security identifier parsing and source-specific formatting."""

from __future__ import annotations

from dataclasses import dataclass

from dataanalysisbase.common.errors import InvalidSecurityId, NameNotResolvable, UnsupportedMarket
from dataanalysisbase.domain.enums import Market

_A_SHARE_SYMBOL_LENGTH = 6


@dataclass(frozen=True, slots=True)
class SecurityId:
    """Canonical security identifier, formatted as SYMBOL.MARKET."""

    symbol: str
    market: Market

    def __post_init__(self) -> None:
        if not self.symbol:
            raise InvalidSecurityId("Security symbol cannot be empty.")
        if not self.symbol.isalnum():
            raise InvalidSecurityId(f"Security symbol contains invalid characters: {self.symbol}")

    def __str__(self) -> str:
        return f"{self.symbol}.{self.market.value}"

    @classmethod
    def parse(cls, raw: str) -> SecurityId:
        """Parse common source formats into a canonical security id."""

        value = raw.strip()
        if not value:
            raise InvalidSecurityId("Security id cannot be empty.")

        lower = value.lower()
        if lower.startswith(("sh", "sz", "bj")) and len(value) >= 4:
            return cls(symbol=value[2:], market=_parse_prefix(lower[:2]))

        if "." in value:
            symbol, market = value.rsplit(".", 1)
            return cls(symbol=symbol, market=_parse_market(market))

        if value.isdigit():
            return cls(symbol=value, market=_infer_a_share_market(value))

        raise NameNotResolvable(f"Name-like security input is not resolvable in domain: {raw}")


def to_source_code(sid: SecurityId, source: str) -> str:
    """Format canonical security id for a supported provider."""

    normalized = source.lower()
    if normalized == "akshare":
        return sid.symbol
    if normalized == "tushare":
        return str(sid)
    if normalized == "sina":
        return f"{sid.market.value.lower()}{sid.symbol}"
    raise UnsupportedMarket(f"Unsupported source for security code formatting: {source}")


def _parse_prefix(prefix: str) -> Market:
    mapping = {"sh": Market.SH, "sz": Market.SZ, "bj": Market.BJ}
    try:
        return mapping[prefix]
    except KeyError as exc:
        raise UnsupportedMarket(f"Unsupported market prefix: {prefix}") from exc


def _parse_market(raw: str) -> Market:
    try:
        return Market(raw.upper())
    except ValueError as exc:
        raise UnsupportedMarket(f"Unsupported market suffix: {raw}") from exc


def _infer_a_share_market(symbol: str) -> Market:
    if len(symbol) != _A_SHARE_SYMBOL_LENGTH:
        raise InvalidSecurityId(f"A-share symbol must have 6 digits: {symbol}")
    if symbol.startswith("6"):
        return Market.SH
    if symbol.startswith(("0", "3")):
        return Market.SZ
    if symbol.startswith(("8", "9")):
        return Market.BJ
    raise InvalidSecurityId(f"Cannot infer market from A-share symbol: {symbol}")
