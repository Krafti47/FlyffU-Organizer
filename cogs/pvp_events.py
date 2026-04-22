import discord
from discord.commands import Option
from discord.ext import commands

from core import database as db
from core.embeds import build_pvp_embed
from core.views import PvpEventView
from utils.checks import pvp_creator_only


class PvpEvents(commands.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    pvp = discord.SlashCommandGroup("pvp", "PvP event commands")

    @pvp.command(name="create", description="Create a new PvP event")
    @pvp_creator_only
    async def create_pvp(
        self,
        ctx: discord.ApplicationContext,
        title: Option(str, "Event title"),
        date: Option(str, "Date and time (format: YYYY-MM-DD HH:MM)"),
        description: Option(str, "Optional description") = "",
    ) -> None:
        from datetime import datetime
        try:
            datetime.strptime(date, "%Y-%m-%d %H:%M")
        except ValueError:
            await ctx.respond(
                "Invalid date format. Use `YYYY-MM-DD HH:MM` (e.g. `2026-05-01 20:00`).",
                ephemeral=True,
            )
            return

        event_id = await db.create_event(
            event_type="pvp",
            title=title,
            description=description,
            event_date=date,
            channel_id=ctx.channel_id,
            creator_id=ctx.author.id,
            creator_name=ctx.author.display_name,
        )

        event = await db.get_event_by_id(event_id)
        embed = build_pvp_embed(event, [], [])
        view = PvpEventView(event_id=event_id, bot=self.bot)

        msg = await ctx.channel.send(embed=embed, view=view)
        await db.update_event_message_id(event_id, msg.id)

        await ctx.respond("PvP event created!", ephemeral=True)

    @create_pvp.error
    async def create_pvp_error(
        self, ctx: discord.ApplicationContext, error: Exception
    ) -> None:
        if isinstance(error, commands.CheckFailure):
            await ctx.respond(str(error), ephemeral=True)
        else:
            raise error


def setup(bot: discord.Bot) -> None:
    bot.add_cog(PvpEvents(bot))
