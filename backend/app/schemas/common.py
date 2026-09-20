from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // self.page_size))


class ErrorResponse(BaseModel):
    code: str = Field(examples=["not_found"])
    message: str
    details: dict = Field(default_factory=dict)


class MessageResponse(BaseModel):
    message: str
