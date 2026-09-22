"""FastAPI application factory and process-level application instance."""

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.routes import router
from app.core.config import Settings
from app.core.errors import WindLayaError
from app.core.logging import configure_logging
from app.core.model_manager import ModelManager
from app.services.decision_service import DecisionService

logger = logging.getLogger(__name__)


def _new_request_id() -> str:
    return str(uuid.uuid4())


def _valid_request_id(value: str) -> bool:
    return 1 <= len(value) <= 128 and all(0x21 <= ord(character) <= 0x7E for character in value)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", _new_request_id())


def _error_response(status_code: int, code: str, message: str, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "request_id": request_id}},
        headers={"X-Request-ID": request_id},
    )


def create_app(
    settings: Settings | None = None,
    model_manager: ModelManager | None = None,
) -> FastAPI:
    """Build an application with injectable external model ownership."""
    resolved_settings = settings or Settings()
    configure_logging(resolved_settings.log_level)
    manager = model_manager or ModelManager(resolved_settings)
    service = DecisionService(manager)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        manager.startup()
        application.state.model_manager = manager
        application.state.decision_service = service
        try:
            yield
        finally:
            manager.shutdown()

    application = FastAPI(
        title="WindLaya",
        description="Local multilingual Laya System-1 Decision API",
        version=__version__,
        lifespan=lifespan,
    )

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next: Any):
        supplied = request.headers.get("X-Request-ID")
        if supplied is not None and not _valid_request_id(supplied):
            safe_id = _new_request_id()
            request.state.request_id = safe_id
            return _error_response(400, "INVALID_REQUEST", "Invalid X-Request-ID header.", safe_id)
        request.state.request_id = supplied or _new_request_id()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @application.exception_handler(WindLayaError)
    async def windlaya_error_handler(request: Request, exc: WindLayaError) -> JSONResponse:
        logger.error(
            "request_id=%s endpoint=%s code=%s success=false",
            _request_id(request),
            request.url.path,
            exc.code,
            exc_info=exc.__cause__ is not None,
        )
        return _error_response(exc.status_code, exc.code, exc.message, _request_id(request))

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning(
            "request_id=%s endpoint=%s code=INVALID_REQUEST validation_errors=%r success=false",
            _request_id(request),
            request.url.path,
            exc.errors(),
        )
        return _error_response(
            422,
            "INVALID_REQUEST",
            "Request validation failed.",
            _request_id(request),
        )

    @application.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return _error_response(
            exc.status_code,
            "INVALID_REQUEST",
            str(exc.detail),
            _request_id(request),
        )

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "request_id=%s endpoint=%s code=INTERNAL_ERROR success=false",
            _request_id(request),
            request.url.path,
            exc_info=exc,
        )
        return _error_response(
            500,
            "INTERNAL_ERROR",
            "Internal server error.",
            _request_id(request),
        )

    application.include_router(router)
    return application


app = create_app()
