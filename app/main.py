from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import RateLimitMiddleware, RequestIdMiddleware


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.APP_DEBUG,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)

# Rate limit auth-sensitive endpoints per client IP.
# Format: prefix -> (max_requests, window_seconds)
_AUTH_LIMITS: dict[str, tuple[int, float]] = {
    f"{settings.API_V1_PREFIX}/auth/login": (10, 60.0),
    f"{settings.API_V1_PREFIX}/auth/register": (5, 60.0),
    f"{settings.API_V1_PREFIX}/auth/refresh": (30, 60.0),
}
app.add_middleware(RateLimitMiddleware, rules=_AUTH_LIMITS)
app.add_middleware(RequestIdMiddleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        body: dict[str, Any] = {"error": detail}
    else:
        body = {
            "error": {
                "code": _default_code(exc.status_code),
                "message": str(detail) if detail else "Request failed",
                "details": {},
            }
        }
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": exc.errors()},
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(exc) if settings.APP_DEBUG else "Internal server error",
                "details": {},
            }
        },
    )


def _default_code(status_code: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
    }.get(status_code, "ERROR")


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
