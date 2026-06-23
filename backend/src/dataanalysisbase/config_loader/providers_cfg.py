"""Provider configuration models."""

from pydantic import BaseModel, ConfigDict, Field

from dataanalysisbase.domain.enums import DatasetType


class RateLimitConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    requests_per_minute: int | None = Field(default=None, gt=0)
    retry: int = Field(default=0, ge=0)
    retry_delay_sec: float = Field(default=0, ge=0)


class ProviderEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    priority: int = 100
    datasets: list[DatasetType] = Field(default_factory=list)
    token_env: str | None = None
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)


class ProvidersConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str
    providers: dict[str, ProviderEntry]
