from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class ScreenerFormField(BaseModel, Generic[T]):
    value: T | None = None
    dirty: bool = False
    is_advanced_filter: bool = False
    enabled: bool = True


def field(
    value=None,
    *,
    is_advanced_filter: bool = True,
    enabled: bool = True,
):
    return Field(
        default_factory=lambda: ScreenerFormField(
            value=value,
            dirty=False,
            is_advanced_filter=is_advanced_filter,
            enabled=enabled,
        )
    )


class BaseScreenerForm(BaseModel):
    category: str
    description: str
