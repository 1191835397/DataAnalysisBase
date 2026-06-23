"""Shared pagination DTOs."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    model_config = ConfigDict(frozen=True)

    items: list[T]
    total: int
    page: int = Field(ge=1)
    size: int = Field(ge=1, le=200)
