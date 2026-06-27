"""Shared domain enumerations."""

from enum import StrEnum


class Market(StrEnum):
    SH = "SH"
    SZ = "SZ"
    BJ = "BJ"
    HK = "HK"
    US = "US"
    OF = "OF"


class SecurityType(StrEnum):
    STOCK = "stock"
    ETF = "etf"
    FUND = "fund"
    INDEX = "index"


class DatasetType(StrEnum):
    MARKET_SPOT = "market_spot"
    INDUSTRY_MAPPING = "industry_mapping"
    DAILY_BARS = "daily_bars"
    VALUATION = "valuation"
    FINANCIALS = "financials"
    MONEY_FLOW = "money_flow"
    NEWS = "news"
    ANNOUNCEMENTS = "announcements"
    FUND_NAV = "fund_nav"
    FUND_HOLDINGS = "fund_holdings"
    INDEX = "index"
    MACRO = "macro"


class Severity(StrEnum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class AlertSeverity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    INFO = "info"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class DataStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    PARTIAL = "partial"
    FAILED = "failed"
    OFFLINE = "offline"
