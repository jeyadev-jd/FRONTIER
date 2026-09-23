"""FRONTIER FastAPI backend."""
import structlog
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.database.db import init_db
from backend.routers import posts, health, channels, discovery, style, sources, scheduler, queue, analytics, autopublish

# Structured logging setup
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("frontier.starting", env=settings.app_env, llm_provider=settings.llm_provider)
    await init_db()
    logger.info("frontier.ready")
    yield
    logger.info("frontier.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="FRONTIER",
        description="Local AI Community Agent for student tech communities",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_dev else None,
        redoc_url="/redoc" if settings.is_dev else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(posts.router)
    app.include_router(channels.router)
    app.include_router(discovery.router)
    app.include_router(style.router)
    app.include_router(sources.router)
    app.include_router(scheduler.router)
    app.include_router(queue.router)
    app.include_router(analytics.router)
    app.include_router(autopublish.router)

    @app.get("/")
    async def root():
        return {"service": "FRONTIER", "status": "online", "version": "0.1.0"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.is_dev,
    )
