"""ASGI entry point and local development launcher."""

from fastapi import FastAPI

from src.application.web import WebService
from src.infrastructure.di.bootstrap import bootstrap_di
from src.infrastructure.di.inject import resolve
from src.infrastructure.utils.config_reader import ConfigReader


def create_app() -> FastAPI:
    bootstrap_di()
    return resolve(WebService).create_app()


app = create_app()


if __name__ == "__main__":
    import uvicorn

    config = resolve(ConfigReader)
    uvicorn.run(
        app,
        host=config.get_server_host(),
        port=config.get_server_port(),
    )
