"""Discord integration service (REST API wrapper, separate from the bot process)."""
import httpx
import structlog
from backend.config import get_settings

logger = structlog.get_logger()

DISCORD_API_BASE = "https://discord.com/api/v10"

CHANNEL_NAME_TO_ID: dict[str, str] = {}  # populated at runtime from Discord API


async def _headers() -> dict:
    settings = get_settings()
    return {
        "Authorization": f"Bot {settings.discord_bot_token}",
        "Content-Type": "application/json",
    }


async def fetch_guild_channels() -> list[dict]:
    """Fetch all channels in the configured guild."""
    settings = get_settings()
    if not settings.discord_bot_token or not settings.discord_guild_id:
        logger.warning("discord.not_configured")
        return []

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            f"{DISCORD_API_BASE}/guilds/{settings.discord_guild_id}/channels",
            headers=await _headers(),
        )
        r.raise_for_status()
        channels = r.json()

    # update local name→id map
    for ch in channels:
        if ch.get("type") == 0:  # text channel
            CHANNEL_NAME_TO_ID[f"#{ch['name']}"] = ch["id"]

    logger.info("discord.channels_loaded", count=len(CHANNEL_NAME_TO_ID))
    return channels


async def send_message(channel_name: str, content: str, embed: dict | None = None) -> dict:
    """Send a message to a Discord channel by name (e.g. '#neural')."""
    if not CHANNEL_NAME_TO_ID:
        await fetch_guild_channels()

    channel_id = CHANNEL_NAME_TO_ID.get(channel_name)
    if not channel_id:
        raise ValueError(f"Channel {channel_name!r} not found in guild. Known: {list(CHANNEL_NAME_TO_ID.keys())}")

    payload: dict = {"content": content}
    if embed:
        payload["embeds"] = [embed]

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"{DISCORD_API_BASE}/channels/{channel_id}/messages",
            headers=await _headers(),
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    logger.info("discord.message_sent", channel=channel_name, message_id=result.get("id"))
    return result


async def health_check() -> bool:
    settings = get_settings()
    if not settings.discord_bot_token:
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                f"{DISCORD_API_BASE}/users/@me",
                headers=await _headers(),
            )
            return r.status_code == 200
    except Exception as e:
        logger.warning("discord.health_check_failed", error=str(e))
        return False
