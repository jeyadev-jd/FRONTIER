from fastapi import APIRouter, HTTPException
from backend.services import discord_service
from backend.services.style_service import CHANNEL_ROUTING, VALID_CHANNELS

router = APIRouter(prefix="/channels", tags=["channels"])

# Channels FRONTIER requires to function correctly
REQUIRED_CHANNELS = {
    "#signal": "Official FRONTIER announcements and important community info",
    "#frontier-guide": "Help students understand how FRONTIER works — guides and rules",
    "#frontier-lounge": "Casual student discussion and general tech chat",
    "#forge": "Building, GitHub, coding, vibe coding, tools, frameworks, deployment",
    "#bug-hunt": "Technical debugging and problem solving — errors, bugs, stack traces",
    "#neural": "AI tools, LLMs, agents, local models, AI engineering, AI tutorials",
    "#lab": "Research papers, datasets, research tools, academic content",
    "#arena": "Hackathons, competitions, AI challenges, team formation",
    "#missions": "FRONTIER-created challenges and weekly build tasks",
    "#launchpad": "Student project showcase — demos, repos, prototypes",
}


@router.get("")
async def list_channels():
    discord_channels = await discord_service.fetch_guild_channels()
    discord_names = {f"#{ch['name']}" for ch in discord_channels if ch.get("type") == 0}

    missing = [
        {
            "channel": ch,
            "purpose": REQUIRED_CHANNELS[ch],
            "action": f"Create a text channel named '{ch[1:]}' in your Discord server",
        }
        for ch in REQUIRED_CHANNELS
        if ch not in discord_names
    ]

    return {
        "frontier_channels": VALID_CHANNELS,
        "routing_rules": CHANNEL_ROUTING,
        "discord_channels": [
            {"id": ch["id"], "name": ch["name"]}
            for ch in discord_channels
            if ch.get("type") == 0
        ],
        "missing_channels": missing,
        "all_present": len(missing) == 0,
    }


@router.post("/resync")
async def resync_channels():
    """Force re-fetch Discord channel list and return sync status."""
    # Clear the cached channel map so it reloads
    discord_service.CHANNEL_NAME_TO_ID.clear()

    discord_channels = await discord_service.fetch_guild_channels()
    discord_names = {f"#{ch['name']}" for ch in discord_channels if ch.get("type") == 0}

    missing = [
        {
            "channel": ch,
            "purpose": REQUIRED_CHANNELS[ch],
            "action": f"In Discord: right-click your server → Create Channel → Text → name it '{ch[1:]}'",
        }
        for ch in REQUIRED_CHANNELS
        if ch not in discord_names
    ]

    synced = [ch for ch in REQUIRED_CHANNELS if ch in discord_names]

    return {
        "synced": synced,
        "synced_count": len(synced),
        "missing": missing,
        "missing_count": len(missing),
        "all_present": len(missing) == 0,
        "discord_channel_map": dict(discord_service.CHANNEL_NAME_TO_ID),
    }
