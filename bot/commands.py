"""FRONTIER Discord slash commands."""
import uuid
import discord
from discord.ext import commands
from discord import app_commands
import structlog

from backend.services.generation_service import generate_post, regenerate_post
from backend.services.style_service import VALID_CHANNELS

logger = structlog.get_logger()

MAX_DISCORD_LEN = 2000


def truncate(text: str, max_len: int = MAX_DISCORD_LEN) -> str:
    return text[:max_len - 3] + "..." if len(text) > max_len else text


class ApproveView(discord.ui.View):
    """Inline approve/edit/reject buttons shown after generating a post."""

    def __init__(self, bot, post_data: dict):
        super().__init__(timeout=300)
        self.bot = bot
        self.post_data = post_data
        self.approved = False

    @discord.ui.button(label="✅ Approve & Publish", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        from backend.services import discord_service
        await interaction.response.defer()
        try:
            await discord_service.send_message(
                self.post_data["channel"],
                self.post_data["content"],
            )
            self.approved = True
            for child in self.children:
                child.disabled = True
            await interaction.followup.edit_message(
                interaction.message.id,
                content=f"✅ Published to **{self.post_data['channel']}**",
                view=self,
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Publish failed: {e}", ephemeral=True)

    @discord.ui.button(label="🔁 Regenerate", style=discord.ButtonStyle.primary)
    async def regenerate(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = FeedbackModal(self.bot, self.post_data, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content="❌ Post rejected.",
            view=self,
        )


class FeedbackModal(discord.ui.Modal, title="Regenerate with feedback"):
    feedback = discord.ui.TextInput(
        label="What should be changed?",
        style=discord.TextStyle.paragraph,
        placeholder="Make it shorter, add more technical detail, change the tone...",
        required=True,
        max_length=500,
    )

    def __init__(self, bot, post_data: dict, original_view: ApproveView):
        super().__init__()
        self.bot = bot
        self.post_data = post_data
        self.original_view = original_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        result = await regenerate_post(
            original_content=self.post_data["content"],
            feedback=self.feedback.value,
            channel=self.post_data["channel"],
        )
        self.post_data["content"] = result["content"]
        new_view = ApproveView(self.bot, self.post_data)
        preview = truncate(f"📋 **PREVIEW** — {self.post_data['channel']}\n```\n{result['content']}\n```")
        await interaction.followup.send(preview, view=new_view, ephemeral=True)


class FrontierCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="frontier", description="FRONTIER AI agent commands")
    @app_commands.describe(action="Command to run", query="Topic, URL, or post ID")
    @app_commands.choices(action=[
        app_commands.Choice(name="help", value="help"),
        app_commands.Choice(name="draft", value="draft"),
        app_commands.Choice(name="status", value="status"),
    ])
    async def frontier(
        self,
        interaction: discord.Interaction,
        action: str,
        query: str | None = None,
    ):
        if action == "help":
            await interaction.response.send_message(
                "**🤖 FRONTIER Commands**\n"
                "`/frontier action:draft query:<topic or URL>` — Generate a post\n"
                "`/frontier action:status` — Check system status\n"
                "`/frontier action:help` — Show this message",
                ephemeral=True,
            )

        elif action == "status":
            await interaction.response.defer(thinking=True, ephemeral=True)
            from backend.services.llm.factory import get_llm_provider
            from backend.services import discord_service
            llm = get_llm_provider()
            llm_ok = await llm.health_check()
            discord_ok = await discord_service.health_check()
            await interaction.followup.send(
                f"**FRONTIER Status**\n"
                f"{'✅' if llm_ok else '❌'} LLM: {llm.provider_name}\n"
                f"{'✅' if discord_ok else '❌'} Discord: connected",
                ephemeral=True,
            )

        elif action == "draft":
            if not query:
                await interaction.response.send_message("Please provide a topic or URL.", ephemeral=True)
                return

            await interaction.response.defer(thinking=True, ephemeral=True)

            # If query looks like a URL, fetch it first
            topic = query
            source_url = None
            if query.startswith("https://"):
                source_url = query
                topic = f"Write a post about the content at this URL: {query}"

            result = await generate_post(topic=topic, source_url=source_url)

            post_data = {
                "id": str(uuid.uuid4()),
                "content": result["content"],
                "channel": result["channel"],
                "category": result["category"],
            }

            view = ApproveView(self.bot, post_data)
            preview = truncate(
                f"📋 **PREVIEW** — {result['channel']}\n"
                f"*Model: {result['model']} ({result['provider']})*\n\n"
                f"```\n{result['content']}\n```"
            )
            await interaction.followup.send(preview, view=view, ephemeral=True)

    @app_commands.command(name="draft", description="Generate a FRONTIER post for a topic or URL")
    @app_commands.describe(
        topic="What to write about",
        channel="Target channel (optional, auto-routed if omitted)",
        category="Content category",
    )
    async def draft(
        self,
        interaction: discord.Interaction,
        topic: str,
        channel: str | None = None,
        category: str = "GENERAL",
    ):
        await interaction.response.defer(thinking=True, ephemeral=True)

        result = await generate_post(topic=topic, channel=channel, category=category)
        post_data = {
            "id": str(uuid.uuid4()),
            "content": result["content"],
            "channel": result["channel"],
            "category": result["category"],
        }

        view = ApproveView(self.bot, post_data)
        preview = truncate(
            f"📋 **PREVIEW** — {result['channel']}\n"
            f"*Model: {result['model']}*\n\n"
            f"```\n{result['content']}\n```"
        )
        await interaction.followup.send(preview, view=view, ephemeral=True)
