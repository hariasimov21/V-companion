import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.ai.base import AIProvider
from app.api.websocket import router as websocket_router
from app.config.settings import Settings, get_settings
from app.container import build_container
from app.core.logging import configure_logging, get_logger

log = get_logger("app")


def create_app(settings: Settings | None = None, provider: AIProvider | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = build_container(settings, provider)
        app.state.container = container
        log.info(
            "Backend ready",
            extra={
                "fields": {
                    "character": container.character.name,
                    "provider": container.provider.name,
                }
            },
        )
        # Warm up in the background so a slow model load never blocks startup.
        warm_up = asyncio.create_task(container.provider.warm_up())
        try:
            yield
        finally:
            warm_up.cancel()
            await container.provider.aclose()

    app = FastAPI(title="Virtual companion backend", lifespan=lifespan)
    app.include_router(websocket_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        create_app(settings),
        host=settings.backend_host,
        port=settings.backend_port,
        access_log=False,
    )


if __name__ == "__main__":
    run()
