"""FRONTIER MCP Server — exposes tools to local AI agent via FastMCP."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
from mcp.tools import generation_tools, discord_tools, management_tools, discovery_tools

mcp = FastMCP(
    "FRONTIER",
    instructions=(
        "You are the FRONTIER AI agent for a university student tech community Discord server.\n\n"
        "Your workflow:\n"
        "1. discover_content or search_web to find relevant content\n"
        "2. analyze_content or score_content to verify it's worth posting\n"
        "3. check_duplicate to avoid repeats\n"
        "4. generate_post_tool to create the Discord post\n"
        "5. preview_post to show the human\n"
        "6. publish_post ONLY after explicit human approval\n\n"
        "FRONTIER channels: #neural (AI), #forge (build), #lab (research), "
        "#arena (hackathons), #bug-hunt (debugging), #missions, #launchpad, #signal\n\n"
        "NEVER publish unverified facts. NEVER publish without human approval."
    ),
)

# Register all tool modules
generation_tools.register(mcp)
discord_tools.register(mcp)
management_tools.register(mcp)
discovery_tools.register(mcp)


if __name__ == "__main__":
    mcp.run()
