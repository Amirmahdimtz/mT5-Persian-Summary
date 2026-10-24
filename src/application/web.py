"""FastAPI construction and feature-controller auto discovery."""

from __future__ import annotations

import importlib
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from src.application.summarization.upload_limit_middleware import (
    UploadBodyLimitMiddleware,
    configured_upload_budget,
)
from src.infrastructure.di.inject import inject
from src.infrastructure.utils.config_reader import ConfigReader, ConfigurationError


class ControllerDiscoveryError(RuntimeError):
    """Raised when a discovered controller violates its required convention."""


@inject
class WebService:
    def __init__(self, config_reader: ConfigReader) -> None:
        self._config_reader = config_reader

    def create_app(self) -> FastAPI:
        app_name = self._config_reader.get("app.name")
        version = self._config_reader.get("app.version")
        if not isinstance(app_name, str) or not app_name.strip():
            raise ConfigurationError("app.name must be a non-empty string")
        if not isinstance(version, str) or not version.strip():
            raise ConfigurationError("app.version must be a non-empty string")

        app = FastAPI(title=app_name, version=version)

        @app.exception_handler(RequestValidationError)
        async def request_validation_error_async(
            request: Request, error: RequestValidationError
        ) -> JSONResponse:
            # FastAPI's default validation errors may include user-supplied `input`.
            return JSONResponse(
                status_code=422,
                content={"detail": {
                    "code": "RequestValidationError",
                    "message": "Request fields or format are invalid.",
                }},
            )

        api_prefix = self._config_reader.get_api_prefix()
        application_dir = Path(__file__).resolve().parent
        for feature_dir in sorted(application_dir.iterdir()):
            if not feature_dir.is_dir() or feature_dir.name.startswith("_"):
                continue
            feature = feature_dir.name
            controller_file = feature_dir / f"{feature}_controller.py"
            if not controller_file.is_file():
                continue
            module_name = f"src.application.{feature}.{feature}_controller"
            class_name = "".join(part.capitalize() for part in feature.split("_")) + "Controller"
            try:
                module = importlib.import_module(module_name)
                controller_class = getattr(module, class_name)
                controller = controller_class()
                router = controller.api()
            except Exception as error:
                raise ControllerDiscoveryError(
                    f"Cannot initialize controller {module_name}.{class_name}: {error}"
                ) from error
            if not isinstance(router, APIRouter):
                raise ControllerDiscoveryError(
                    f"{module_name}.{class_name}.api() must return APIRouter"
                )
            app.include_router(router, prefix=f"{api_prefix}/{feature}")
        app.add_middleware(
            UploadBodyLimitMiddleware,
            api_prefix=api_prefix,
            max_total_bytes=configured_upload_budget(self._config_reader),
        )
        return app
