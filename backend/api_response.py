from typing import Generic, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int
    data: T
    message: str = "ok"


def success(data, message: str = "ok", code: int = 0):
    return {
        "code": code,
        "data": data,
        "message": message,
    }


def error(message: str, code: int = 1, status_code: int = 500, data=None):
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "data": data,
            "message": message,
        },
    )
