from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from backend.config import get_settings
import structlog

logger = structlog.get_logger()

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.is_dev,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    from backend.database import models  # noqa: F401 — registers models
    from backend.services import autopublish_service  # noqa: F401 — registers AutoPublishRule
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database.initialized", url=settings.database_url)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
