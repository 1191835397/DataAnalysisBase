"""Core entity models."""

from pydantic import BaseModel, ConfigDict

from dataanalysisbase.domain.enums import Market, SecurityType


class Issuer(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    credit_code: str | None = None
    industry: str | None = None
    main_business: str | None = None


class Security(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    market: Market
    symbol: str
    name: str
    type: SecurityType
    issuer_id: str | None = None
    currency: str = "CNY"
    is_active: bool = True


class IndustryRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    name: str
    source: str
    level: int = 1
