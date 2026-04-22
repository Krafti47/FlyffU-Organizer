import discord
from discord.commands import Option
from discord.ext import commands

from core import database as db
from core.embeds import build_pve_embed
from core.views import PveEventView
from utils.checks import member_only


class PveEvents(commands.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    pve = discord.SlashCommandGroup("pve", "PvE event commands")

    @pve.command(name="create", description="Create a new PvE event (requires Member role)")
    @member_only
    async def create_pve(
        self,
        ctx: discord.ApplicationContext,
        title: Option(str, "Event title"),
        date: Option(str, "Date and time (format: YYYY-MM-DD HH:MM)"),
        description: Option(str, "Optional description") = "",
        tanks: Option(int, "Tank slots", min_value=0, max_value=20) = 0,
        supports: Option(int, "Support slots", min_value=0, max_value=20) = 0,
        dps_1v1: Option(int, "DPS: 1v1 slots", min_value=0, max_value=20) = 0,
        aoe: Option(int, "DPS: AOE slots", min_value=0, max_value=20) = 0,
    ) -> None:
        if tanks + supports + dps_1v1 + aoe == 0:
            await ctx.respond(
                "Please configure at least one slot (tanks, supports, dps_1v1, or aoe).",
                ephemeral=True,
            )
            return

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
            event_type="pve",
            title=title,
            description=description,
            event_date=date,
            channel_id=ctx.channel_id,
            creator_id=ctx.author.id,
            creator_name=ctx.author.display_name,
            slots_tank=tanks or None,
            slots_support=supports or None,
            slots_1v1=dps_1v1 or None,
            slots_aoe=aoe or None,
        )

        event = await db.get_event_by_id(event_id)
        embed = build_pve_embed(event, [], [])
        view = PveEventView(event_id=event_id, bot=self.bot)

        msg = await ctx.channel.send(embed=embed, view=view)
        await db.update_event_message_id(event_id, msg.id)

        await ctx.respond("PvE event created!", ephemeral=True)

    @create_pve.error
    async def create_pve_error(
        self, ctx: discord.ApplicationContext, error: Exception
    ) -> None:
        if isinstance(error, commands.CheckFailure):
            await ctx.respond(str(error), ephemeral=True)
        else:
            raise error


def setup(bot: discord.Bot) -> None:
    bot.add_cog(PveEvents(bot))
