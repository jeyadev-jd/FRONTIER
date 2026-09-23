"""MCP tools for content generation."""
from fastmcp import FastMCP
from backend.services.generation_service import generate_post, regenerate_post
from backend.services.style_service import get_channel_for_category, VALID_CHANNELS, VALID_CATEGORIES
import httpx
import json


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def generate_post_tool(
        topic: str,
        channel: str | None = None,
        category: str = "GENERAL",
        source_url: str | None = None,
    ) -> str:
        """
        Generate a FRONTIER-style Discord post for a given topic.

        Args:
            topic: The topic or content to write about (be specific)
            channel: Target Discord channel (#neural, #forge, #lab, #arena, #bug-hunt, #missions, #launchpad, #signal)
            category: Content category (AI, BUILD, RESEARCH, HACKATHON, DEBUGGING, OPPORTUNITY, GENERAL)
            source_url: Optional source URL to cite
        """
        result = await generate_post(
            topic=topic,
            channel=channel,
            category=category,
            source_url=source_url,
        )
        return (
            f"✅ POST GENERATED\n"
            f"Channel: {result['channel']}\n"
            f"Category: {result['category']}\n"
            f"Model: {result['model']} ({result['provider']})\n"
            f"Hash: {result['content_hash']}\n\n"
            f"--- CONTENT ---\n{result['content']}"
        )

    @mcp.tool()
    async def apply_frontier_style(
        raw_content: str,
        channel: str = "#frontier-lounge",
        category: str = "GENERAL",
    ) -> str:
        """
        Rewrite raw content in FRONTIER style for a specific channel.

        Args:
            raw_content: The raw content to transform
            channel: Target Discord channel
            category: Content category
        """
        result = await generate_post(
            topic=f"Transform this into a FRONTIER post:\n\n{raw_content}",
            channel=channel,
            category=category,
        )
        return result["content"]

    @mcp.tool()
    async def suggest_channel(topic: str, category: str = "GENERAL") -> str:
        """
        Suggest the best FRONTIER Discord channel for a given topic.

        Args:
            topic: The topic or content description
            category: Content category
        """
        channel = get_channel_for_category(category)
        return f"Recommended channel: {channel}\n\nAll channels: {', '.join(VALID_CHANNELS)}"

    @mcp.tool()
    async def fetch_url_content(url: str) -> str:
        """
        Fetch and extract text content from a public URL.

        Args:
            url: Public URL to fetch (must start with https://)
        """
        if not url.startswith("https://"):
            return "ERROR: Only HTTPS URLs are allowed."

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                r = await client.get(url, headers={"User-Agent": "FRONTIER-Bot/1.0"})
                r.raise_for_status()
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(r.text, "html.parser")
                # Remove scripts and styles
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
                # Trim to first 3000 chars
                return text[:3000] + ("..." if len(text) > 3000 else "")
        except Exception as e:
            return f"ERROR fetching URL: {e}"
