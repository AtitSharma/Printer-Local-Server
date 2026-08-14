import importlib
import logging
import os
from pathlib import Path
from typing import Any, Generic, TypeVar

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ResponseBaseSchema(BaseModel, Generic[T]):
    success: bool = True
    message: str | None = None
    data: T | None = None


class AppException(Exception):
    def __init__(
        self,
        message: str,
        exception_type: str = "bad_request",
        status_code: int = 400,
    ):
        self.message = message
        self.exception_type = exception_type
        self.status_code = status_code
        super().__init__(message)


class NotFound(AppException):
    def __init__(self, message: str = "Not Found"):
        super().__init__(
            message, exception_type="not_found", status_code=404
        )


class BadRequest(AppException):
    def __init__(self, message: str, exception_type: str = "bad_request"):
        super().__init__(message, exception_type=exception_type)


def response_ok(data: Any = None, message: str = "Success") -> dict:
    """Return a success response envelope."""
    return {
        "success": True,
        "message": message,
        "data": data,
    }


api_router = APIRouter(tags=["base"])


@api_router.get("/version", response_model=ResponseBaseSchema[dict])
def version() -> Any:
    """Provide version information about the web service."""
    return response_ok(data={"version": "1.0.0"})


def create_application(lifespan=None) -> FastAPI:
    """Create a FastAPI instance."""
    application = FastAPI(
        title=settings.project_name,
        debug=settings.debug,
        version="1.0.0",
        docs_url="/",
        openapi_url=f"{settings.api_str}/openapi.json",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.message,
                "data": None,
            },
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception(
            f"Unhandled exception on {request.method} {request.url.path}",
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Internal server error", "data": None},
        )

    return application


def add_routes(app: FastAPI) -> FastAPI:
    """
    Dynamically include all routers from the subdirectories
    of the application directory.
    """
    base_dir: str = "apps"
    api_prefix: str = settings.api_str
    base_path = Path(base_dir)

    app.include_router(api_router, prefix=api_prefix)

    for root, _, files in os.walk(base_path):
        for file in files:
            if (
                "routes" in file.lower()
                and file.endswith(".py")
                and not file.startswith("_")
            ):
                module_path = Path(root) / file
                relative_path = module_path.relative_to(base_path)
                module_name = (
                    str(relative_path)
                    .replace("/", ".")
                    .replace("\\", ".")
                    .replace(".py", "")
                )

                module = importlib.import_module(f"{base_dir}.{module_name}")
                if hasattr(module, "api_router"):
                    app.include_router(module.api_router, prefix=api_prefix)
                if hasattr(module, "public_router"):
                    app.include_router(module.public_router, prefix=api_prefix)

    return app
