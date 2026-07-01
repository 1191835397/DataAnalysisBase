"""A-share price-limit threshold helpers."""

from __future__ import annotations

from datetime import date

REGULAR_LIMIT_UP_PCT = 9.9
REGULAR_LIMIT_DOWN_PCT = -9.9
RISK_WARNING_LIMIT_UP_PCT = 4.9
RISK_WARNING_LIMIT_DOWN_PCT = -4.9
GROWTH_BOARD_LIMIT_UP_PCT = 19.9
GROWTH_BOARD_LIMIT_DOWN_PCT = -19.9
BSE_LIMIT_UP_PCT = 29.9
BSE_LIMIT_DOWN_PCT = -29.9
NEW_LISTING_NO_LIMIT_DAYS = 5


def limit_up_threshold(
    security_id: str,
    name: str,
    *,
    listing_date: date | None = None,
    snapshot_date: date | None = None,
) -> float | None:
    """Return the effective limit-up threshold used by alert filters."""

    if _is_within_new_listing_no_limit_window(listing_date, snapshot_date):
        return None
    if _is_risk_warning_name(name):
        return RISK_WARNING_LIMIT_UP_PCT
    if _is_star_or_chinext(security_id):
        return GROWTH_BOARD_LIMIT_UP_PCT
    if _is_bse(security_id):
        return BSE_LIMIT_UP_PCT
    return REGULAR_LIMIT_UP_PCT


def limit_down_threshold(
    security_id: str,
    name: str,
    *,
    listing_date: date | None = None,
    snapshot_date: date | None = None,
) -> float | None:
    """Return the effective limit-down threshold used by alert filters."""

    if _is_within_new_listing_no_limit_window(listing_date, snapshot_date):
        return None
    if _is_risk_warning_name(name):
        return RISK_WARNING_LIMIT_DOWN_PCT
    if _is_star_or_chinext(security_id):
        return GROWTH_BOARD_LIMIT_DOWN_PCT
    if _is_bse(security_id):
        return BSE_LIMIT_DOWN_PCT
    return REGULAR_LIMIT_DOWN_PCT


def _is_risk_warning_name(name: str) -> bool:
    normalized = name.strip().upper()
    return normalized.startswith(("*ST", "ST", "S*ST"))


def _is_star_or_chinext(security_id: str) -> bool:
    symbol, _, market = security_id.partition(".")
    if market == "SH":
        return symbol.startswith(("688", "689"))
    if market == "SZ":
        return symbol.startswith(("300", "301"))
    return False


def _is_bse(security_id: str) -> bool:
    return security_id.endswith(".BJ")


def _is_within_new_listing_no_limit_window(
    listing_date: date | None,
    snapshot_date: date | None,
) -> bool:
    if listing_date is None or snapshot_date is None:
        return False
    return listing_date <= snapshot_date < listing_date.fromordinal(
        listing_date.toordinal() + NEW_LISTING_NO_LIMIT_DAYS
    )
