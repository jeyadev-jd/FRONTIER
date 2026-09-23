"""MCP tools for Discord operations."""
from fastmcp import FastMCP
from backend.services import discord_service
from backend.services.style_service import VALID_CHANNELS


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def get_discord_channels() -> str:
        """List all available FRONTIER Discord channels."""
        try:
            channels = await discord_service.fetch_guild_channels()
            text_channels = [ch for ch in channels if ch.get("type") == 0]
            lines = [f"#{ch['name']} (id: {ch['id']})" for ch in text_channels]
            return "Discord channels:\n" + "\n".join(lines) if lines else "No channels found (check bot token and guild ID)"
        except Exception as e:
            return f"Error fetching channels: {e}"

    @mcp.tool()
    async def preview_post(channel: str, content: str) -> str:
        """
        Preview a post before publishing — shows what it will look like.
        Does NOT send to Discord.

        Args:
            channel: Target channel name (e.g. #neural)
            content: The post content to preview
        """
        if channel not in VALID_CHANNELS:
            return f"WARNING: {channel!r} is not a known FRONTIER channel. Known: {', '.join(VALID_CHANNELS)}"

        return (
            f"📋 PREVIEW — {channel}\n"
            f"{'─' * 50}\n"
            f"{content}\n"
            f"{'─' * 50}\n"
            f"⚠️  This is a preview. Use publish_post to send to Discord."
        )

    @mcp.tool()
    async def publish_post(channel: str, content: str) -> str:
        """
        Publish a post to a FRONTIER Discord channel.
        Only call this after the user has explicitly approved the content.

        Args:
            channel: Target channel name (e.g. #neural)
            content: The approved post content
        """
        if channel not in VALID_CHANNELS:
            return f"ERROR: {channel!r} is not a known FRONTIER channel."

        if len(content) > 2000:
            return f"ERROR: Content exceeds Discord's 2000 character limit ({len(content)} chars). Shorten it."

        try:
            msg = await discord_service.send_message(channel, content)
            return f"✅ Published to {channel}\nMessage ID: {msg.get('id')}\nURL: https://discord.com/channels/{msg.get('guild_id', '')}/{msg.get('channel_id', '')}/{msg.get('id', '')}"
        except Exception as e:
            return f"❌ Failed to publish: {e}"

    @mcp.tool()
    async def check_discord_status() -> str:
        """Check if the Discord bot is connected and operational."""
        ok = await discord_service.health_check()
        if ok:
            return "✅ Discord bot is online and authenticated."
        return "❌ Discord bot is offline. Check DISCORD_BOT_TOKEN in .env"
