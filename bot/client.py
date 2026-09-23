"""FRONTIER Discord Bot — broadcaster only. Posts messages to channels, no slash commands."""
import structlog
import discord
from discord.ext import commands

from backend.config import get_settings

logger = structlog.get_logger()

intents = discord.Intents.default()
intents.message_content = False  # not needed — bot only sends, never reads


class FrontierBot(commands.Bot):
    def __init__(self):
        settings = get_settings()
        super().__init__(
            command_prefix="!",
            intents=intents,
            application_id=int(settings.discord_application_id) if settings.discord_application_id else None,
        )
        self.settings = settings

    async def setup_hook(self):
        # No slash commands — bot is a broadcaster only
        logger.info("bot.setup", mode="broadcaster")

    async def on_ready(self):
        logger.info("bot.ready", user=str(self.user), guilds=len(self.guilds))
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="the frontier 🤖",
        ))

    async def on_disconnect(self):
        logger.warning("bot.disconnected")

    async def on_error(self, event, *args, **kwargs):
        logger.error("bot.error", event=event)


def run_bot():
    settings = get_settings()
    if not settings.discord_bot_token:
        logger.error("bot.missing_token", msg="Set DISCORD_BOT_TOKEN in .env")
        return

    bot = FrontierBot()
    bot.run(settings.discord_bot_token, log_handler=None)
