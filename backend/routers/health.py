from fastapi import APIRouter
from backend.services.llm.factory import get_llm_provider
from backend.services import discord_service
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health():
    llm = get_llm_provider()
    llm_ok = await llm.health_check()
    discord_ok = await discord_service.health_check()
    models = await llm.list_models() if llm_ok else []

    status = "ok" if (llm_ok and discord_ok) else "degraded"

    return {
        "status": status,
        "llm": {
            "healthy": llm_ok,
            "provider": llm.provider_name,
            "available_models": models,
        },
        "discord": {
            "healthy": discord_ok,
        },
    }
