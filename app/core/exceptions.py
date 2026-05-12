from typing import Any

from fastapi import HTTPException, status


class APIError(HTTPException):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            detail={"code": code, "message": message, "details": details or {}},
        )


class Unauthorized(APIError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__("UNAUTHORIZED", message, status.HTTP_401_UNAUTHORIZED)


class Forbidden(APIError):
    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__("FORBIDDEN", message, status.HTTP_403_FORBIDDEN)


class NotFound(APIError):
    def __init__(self, code: str = "NOT_FOUND", message: str = "Resource not found") -> None:
        super().__init__(code, message, status.HTTP_404_NOT_FOUND)


class ValidationError(APIError):
    def __init__(
        self, message: str = "Validation failed", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__("VALIDATION_ERROR", message, status.HTTP_422_UNPROCESSABLE_ENTITY, details)


class Conflict(APIError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, status.HTTP_409_CONFLICT)


class InvalidStateTransition(APIError):
    def __init__(self, message: str = "Invalid state transition") -> None:
        super().__init__("INVALID_STATE_TRANSITION", message, status.HTTP_409_CONFLICT)
