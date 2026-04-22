from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from config import ICONS_DIR, PVE_ROLE_LABELS
from core import database as db
from core import flyff_api
from core.embeds import build_pve_embed, build_pvp_embed

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: rebuild and update the event embed in the channel
# ---------------------------------------------------------------------------

async def _refresh_embed(bot: discord.Bot, event: dict) -> None:
    try:
        channel = bot.get_channel(event["channel_id"])
        if channel is None:
            channel = await bot.fetch_channel(event["channel_id"])
        message = await channel.fetch_message(event["message_id"])
    except discord.NotFound:
        await db.close_event(event["id"])
        log.warning("Event %d message not found; marked as closed.", event["id"])
        return

    confirmed, waitlist = await db.get_registrations(event["id"])
    if event["event_type"] == "pvp":
        embed = build_pvp_embed(event, confirmed, waitlist)
    else:
        embed = build_pve_embed(event, confirmed, waitlist)

    await message.edit(embed=embed)


# ---------------------------------------------------------------------------
# Class select options (shared)
# ---------------------------------------------------------------------------

def _build_class_options() -> list[discord.SelectOption]:
    return [
        discord.SelectOption(label=cls["name"]["en"], value=str(cls["id"]))
        for cls in flyff_api.get_all_classes()
    ]


# ---------------------------------------------------------------------------
# PVP registration (ephemeral, non-persistent)
# ---------------------------------------------------------------------------

class PvpClassSelectView(discord.ui.View):
    def __init__(self, event_id: int, bot: discord.Bot) -> None:
        super().__init__(timeout=180)
        self.event_id = event_id
        self.bot = bot
        self.selected_class_id: int | None = None
        self.selected_class_name: str | None = None

        select = discord.ui.Select(
            placeholder="Choose your class…",
            options=_build_class_options(),
        )
        select.callback = self._on_class_select
        self.add_item(select)

        signup = discord.ui.Button(label="Sign Up", style=discord.ButtonStyle.success, row=1)
        signup.callback = self._confirm
        self.add_item(signup)

        bench = discord.ui.Button(label="🪑 Bench", style=discord.ButtonStyle.secondary, row=1)
        bench.callback = self._bench
        self.add_item(bench)

        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
        cancel.callback = self._cancel
        self.add_item(cancel)

    async def _on_class_select(self, interaction: discord.Interaction) -> None:
        self.selected_class_id = int(interaction.data["values"][0])
        cls = flyff_api.get_class(self.selected_class_id)
        self.selected_class_name = cls["name"]["en"] if cls else "Unknown"
        embed = discord.Embed(description=f"Selected: **{self.selected_class_name}**\nClick **Sign Up** to register or **Bench** to join as reserve.")
        icon_path = ICONS_DIR / cls["icon"] if cls and cls.get("icon") else None
        if icon_path and icon_path.exists():
            file = discord.File(icon_path, filename=cls["icon"])
            embed.set_thumbnail(url=f"attachment://{cls['icon']}")
            await interaction.response.defer()
            await interaction.edit_original_response(content=None, embed=embed, file=file, view=self)
        else:
            await interaction.response.edit_message(content=None, embed=embed, view=self)

    async def _confirm(self, interaction: discord.Interaction) -> None:
        if self.selected_class_id is None:
            await interaction.response.send_message("Please select a class first.", ephemeral=True)
            return

        event = await db.get_event_by_id(self.event_id)
        if not event or not event["is_open"]:
            await interaction.response.edit_message(content="This event is no longer open.", view=None)
            return

        result = await db.register_user(
            event_id=self.event_id,
            user_id=interaction.user.id,
            user_name=interaction.user.display_name,
            class_id=self.selected_class_id,
            class_name=self.selected_class_name,
        )

        from core.database import RegisterResult
        if result == RegisterResult.ALREADY_REGISTERED:
            msg = "You are already registered for this event."
        elif result == RegisterResult.WAITLISTED:
            msg = f"Slots are full — added to **Bench** as **{self.selected_class_name}**!"
        else:
            msg = f"Registered as **{self.selected_class_name}**!"

        await interaction.response.edit_message(content=msg, view=None)
        await _refresh_embed(self.bot, event)

    async def _bench(self, interaction: discord.Interaction) -> None:
        if self.selected_class_id is None:
            await interaction.response.send_message("Please select a class first.", ephemeral=True)
            return

        event = await db.get_event_by_id(self.event_id)
        if not event or not event["is_open"]:
            await interaction.response.edit_message(content="This event is no longer open.", view=None)
            return

        result = await db.register_user(
            event_id=self.event_id,
            user_id=interaction.user.id,
            user_name=interaction.user.display_name,
            class_id=self.selected_class_id,
            class_name=self.selected_class_name,
            force_bench=True,
        )

        from core.database import RegisterResult
        if result == RegisterResult.ALREADY_REGISTERED:
            msg = "You are already registered for this event."
        else:
            msg = f"Added to **Bench** as **{self.selected_class_name}**!"

        await interaction.response.edit_message(content=msg, view=None)
        await _refresh_embed(self.bot, event)

    async def _cancel(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(content="Registration cancelled.", view=None)


# ---------------------------------------------------------------------------
# PVE registration (ephemeral, non-persistent)
# ---------------------------------------------------------------------------

class PveRoleSelectView(discord.ui.View):
    def __init__(
        self,
        event_id: int,
        bot: discord.Bot,
        class_id: int,
        class_name: str,
        role_slots: dict[str, tuple[int, int]],
    ) -> None:
        super().__init__(timeout=180)
        self.event_id = event_id
        self.bot = bot
        self.class_id = class_id
        self.class_name = class_name

        for role_key, (filled, cap) in role_slots.items():
            label = PVE_ROLE_LABELS[role_key]
            btn = discord.ui.Button(
                label=f"{label} ({filled}/{cap})",
                style=discord.ButtonStyle.primary,
                disabled=filled >= cap,
            )
            # Capture role_key in closure
            btn.callback = self._make_role_callback(role_key)
            self.add_item(btn)

        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        cancel.callback = self._cancel
        self.add_item(cancel)

    def _make_role_callback(self, role_key: str):
        async def callback(interaction: discord.Interaction) -> None:
            event = await db.get_event_by_id(self.event_id)
            if not event or not event["is_open"]:
                await interaction.response.edit_message(
                    content="This event is no longer open.", view=None
                )
                return

            result = await db.register_user(
                event_id=self.event_id,
                user_id=interaction.user.id,
                user_name=interaction.user.display_name,
                class_id=self.class_id,
                class_name=self.class_name,
                role=role_key,
            )

            from core.database import RegisterResult
            display = PVE_ROLE_LABELS.get(role_key, role_key)
            if result == RegisterResult.ALREADY_REGISTERED:
                msg = "You are already registered for this event."
            elif result == RegisterResult.ROLE_FULL:
                msg = f"**{display}** is full. Please choose another role."
            elif result == RegisterResult.WAITLISTED:
                msg = f"Slot full — added to the **waitlist** as **{self.class_name}** ({display})!"
            else:
                msg = f"Registered as **{self.class_name}** — **{display}**!"

            await interaction.response.edit_message(content=msg, view=None)
            await _refresh_embed(self.bot, event)

        return callback

    async def _cancel(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(content="Registration cancelled.", view=None)


class PveClassSelectView(discord.ui.View):
    def __init__(self, event_id: int, bot: discord.Bot) -> None:
        super().__init__(timeout=180)
        self.event_id = event_id
        self.bot = bot
        self.selected_class_id: int | None = None
        self.selected_class_name: str | None = None

        select = discord.ui.Select(
            placeholder="Choose your class…",
            options=_build_class_options(),
        )
        select.callback = self._on_class_select
        self.add_item(select)

        next_btn = discord.ui.Button(label="Next →", style=discord.ButtonStyle.primary, row=1)
        next_btn.callback = self._next_step
        self.add_item(next_btn)

        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary, row=1)
        cancel.callback = self._cancel
        self.add_item(cancel)

    async def _on_class_select(self, interaction: discord.Interaction) -> None:
        self.selected_class_id = int(interaction.data["values"][0])
        cls = flyff_api.get_class(self.selected_class_id)
        self.selected_class_name = cls["name"]["en"] if cls else "Unknown"
        embed = discord.Embed(description=f"Selected: **{self.selected_class_name}**\nClick **Next** to choose your role.")
        icon_path = ICONS_DIR / cls["icon"] if cls and cls.get("icon") else None
        if icon_path and icon_path.exists():
            file = discord.File(icon_path, filename=cls["icon"])
            embed.set_thumbnail(url=f"attachment://{cls['icon']}")
            await interaction.response.defer()
            await interaction.edit_original_response(content=None, embed=embed, file=file, view=self)
        else:
            await interaction.response.edit_message(content=None, embed=embed, view=self)

    async def _next_step(self, interaction: discord.Interaction) -> None:
        if self.selected_class_id is None:
            await interaction.response.send_message("Please select a class first.", ephemeral=True)
            return

        role_slots = await db.get_role_slot_counts(self.event_id)
        if not role_slots:
            await interaction.response.edit_message(
                content="This event has no open role slots.", view=None
            )
            return

        role_view = PveRoleSelectView(
            event_id=self.event_id,
            bot=self.bot,
            class_id=self.selected_class_id,
            class_name=self.selected_class_name,
            role_slots=role_slots,
        )
        await interaction.response.edit_message(
            content=f"Class: **{self.selected_class_name}** — Choose your role:",
            view=role_view,
        )

    async def _cancel(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(content="Registration cancelled.", view=None)


# ---------------------------------------------------------------------------
# Persistent event views (live on the embed message, survive restarts)
# ---------------------------------------------------------------------------
# These use add_item with dynamic custom_ids so each event has unique IDs.
# On restart, bot.add_view(view, message_id=...) re-attaches them.

class PvpEventView(discord.ui.View):
    def __init__(self, event_id: int, bot: discord.Bot) -> None:
        super().__init__(timeout=None)
        self.event_id = event_id
        self.bot = bot

        register_btn = discord.ui.Button(
            label="Register",
            style=discord.ButtonStyle.success,
            custom_id=f"pvp_register:{event_id}",
        )
        register_btn.callback = self._register
        self.add_item(register_btn)

        leave_btn = discord.ui.Button(
            label="Leave",
            style=discord.ButtonStyle.danger,
            custom_id=f"pvp_unregister:{event_id}",
        )
        leave_btn.callback = self._leave
        self.add_item(leave_btn)

    async def _register(self, interaction: discord.Interaction) -> None:
        event = await db.get_event_by_id(self.event_id)
        if not event or not event["is_open"]:
            await interaction.response.send_message("This event is closed.", ephemeral=True)
            return
        if await db.is_user_registered(self.event_id, interaction.user.id):
            await interaction.response.send_message(
                "You are already registered for this event.", ephemeral=True
            )
            return

        view = PvpClassSelectView(event_id=self.event_id, bot=self.bot)
        await interaction.response.send_message("Choose your class:", view=view, ephemeral=True)

    async def _leave(self, interaction: discord.Interaction) -> None:
        event = await db.get_event_by_id(self.event_id)
        removed = await db.unregister_user(self.event_id, interaction.user.id)
        if not removed:
            await interaction.response.send_message(
                "You are not registered for this event.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            "You have been removed from the event.", ephemeral=True
        )
        if event:
            await _refresh_embed(self.bot, event)


class PveEventView(discord.ui.View):
    def __init__(self, event_id: int, bot: discord.Bot) -> None:
        super().__init__(timeout=None)
        self.event_id = event_id
        self.bot = bot

        register_btn = discord.ui.Button(
            label="Register",
            style=discord.ButtonStyle.success,
            custom_id=f"pve_register:{event_id}",
        )
        register_btn.callback = self._register
        self.add_item(register_btn)

        leave_btn = discord.ui.Button(
            label="Leave",
            style=discord.ButtonStyle.danger,
            custom_id=f"pve_unregister:{event_id}",
        )
        leave_btn.callback = self._leave
        self.add_item(leave_btn)

    async def _register(self, interaction: discord.Interaction) -> None:
        event = await db.get_event_by_id(self.event_id)
        if not event or not event["is_open"]:
            await interaction.response.send_message("This event is closed.", ephemeral=True)
            return
        if await db.is_user_registered(self.event_id, interaction.user.id):
            await interaction.response.send_message(
                "You are already registered for this event.", ephemeral=True
            )
            return

        view = PveClassSelectView(event_id=self.event_id, bot=self.bot)
        await interaction.response.send_message("Choose your class:", view=view, ephemeral=True)

    async def _leave(self, interaction: discord.Interaction) -> None:
        event = await db.get_event_by_id(self.event_id)
        removed = await db.unregister_user(self.event_id, interaction.user.id)
        if not removed:
            await interaction.response.send_message(
                "You are not registered for this event.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            "You have been removed from the event.", ephemeral=True
        )
        if event:
            await _refresh_embed(self.bot, event)


def make_event_view(event: dict, bot: discord.Bot) -> discord.ui.View:
    if event["event_type"] == "pvp":
        return PvpEventView(event_id=event["id"], bot=bot)
    return PveEventView(event_id=event["id"], bot=bot)
