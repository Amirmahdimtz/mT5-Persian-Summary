"""Dependency-free process liveness endpoint."""

from fastapi import APIRouter


class HealthController:
    def api(self) -> APIRouter:
        router = APIRouter(tags=["Health"])

        @router.get("", summary="Health check")
        async def health_async() -> dict[str, str]:
            return {"status": "ok"}

        return router
