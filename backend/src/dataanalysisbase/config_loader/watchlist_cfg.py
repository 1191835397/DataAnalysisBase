"""Watchlist configuration models."""

from pydantic import BaseModel, ConfigDict, Field

from dataanalysisbase.domain.enums import Market, SecurityType


class WatchSecurity(BaseModel):
    model_config = ConfigDict(frozen=True)

    security_id: str
    name: str
    type: SecurityType
    tags: list[str] = Field(default_factory=list)
    peers: list[str] = Field(default_factory=list)
    market: Market | None = None
    enabled: bool = True


class Watchlist(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str
    watchlist: list[WatchSecurity] = Field(default_factory=list)
    funds: list[WatchSecurity] = Field(default_factory=list)
