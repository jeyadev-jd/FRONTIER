"""FRONTIER main runner — starts all services."""
import asyncio
import sys
import os
import signal
import structlog
import logging

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger()

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def wait_for_network(retries: int = 30, delay: float = 2.0) -> bool:
    """Wait for network connectivity before starting."""
    import httpx
    for i in range(retries):
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.get("https://discord.com")
            logger.info("network.available")
            return True
        except Exception:
            if i == 0:
                logger.info("network.waiting", attempt=f"1/{retries}")
            await asyncio.sleep(delay)
    logger.error("network.timeout")
    return False


async def start_backend():
    import uvicorn
    from backend.config import get_settings
    settings = get_settings()
    config = uvicorn.Config(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        log_level="info" if settings.is_dev else "warning",
    )
    server = uvicorn.Server(config)
    await server.serve()


def start_bot():
    from bot.client import run_bot
    run_bot()


async def main():
    logger.info("frontier.boot")

    # Wait for network
    connected = await wait_for_network()
    if not connected:
        logger.warning("frontier.no_network", msg="Starting anyway, will retry connections")

    # Start scheduler
    from backend.services.scheduler_service import start_scheduler
    start_scheduler()
    logger.info("frontier.scheduler_started")

    # Start FastAPI backend in background
    backend_task = asyncio.create_task(start_backend())

    # Give backend a moment to start
    await asyncio.sleep(2)

    # Start Discord bot in a thread (discord.py has its own event loop)
    # Skip if credentials are placeholders
    from backend.config import get_settings as _gs
    _s = _gs()
    if _s.discord_bot_token and _s.discord_bot_token not in ("", "your-bot-token-here"):
        import threading
        bot_thread = threading.Thread(target=start_bot, daemon=True)
        bot_thread.start()
    else:
        logger.warning("frontier.bot_skipped", reason="no Discord credentials configured")

    logger.info("frontier.all_services_started")

    # Wait for backend to exit
    try:
        await backend_task
    except asyncio.CancelledError:
        logger.info("frontier.shutdown")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("frontier.stopped")
