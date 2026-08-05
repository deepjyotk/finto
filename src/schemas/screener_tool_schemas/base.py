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
    # Basic filters (shown on the main tab) default to dirty=True so defaults apply;
    # advanced filters stay dirty=False until the user edits them.
    initial_dirty = not is_advanced_filter
    return Field(
        default_factory=lambda: ScreenerFormField(
            value=value,
            dirty=initial_dirty,
            is_advanced_filter=is_advanced_filter,
            enabled=enabled,
        )
    )


class BaseScreenerForm(BaseModel):
    category: str
    description: str
