from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    data: T
    meta: dict[str, Any] = {}


class APIErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class APIErrorResponse(BaseModel):
    error: APIErrorBody


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
