from __future__ import annotations

from collections import defaultdict

import discord

from config import (
    COLOR_CLOSED,
    COLOR_PVE,
    COLOR_PVP,
    PVE_ROLE_EMOJIS,
    PVE_ROLE_LABELS,
    CLASS_EMOJIS,
)
from core import flyff_api


def _format_date(event_date: str) -> str:
    from datetime import datetime

    dt = datetime.strptime(event_date, "%Y-%m-%d %H:%M")
    timestamp = int(dt.timestamp())

    return f"<t:{timestamp}:F>"


def build_pvp_embed(
    event: dict,
    confirmed: list[dict],
    waitlist: list[dict],
) -> discord.Embed:
    is_open = bool(event["is_open"])
    colour = COLOR_PVP if is_open else COLOR_CLOSED
    embed = discord.Embed(
        title=event["title"],
        description=event.get("description") or "",
        colour=colour,
    )
    embed.add_field(name="📅 Date", value=_format_date(event["event_date"]), inline=False)

    max_slots = event["max_slots"]

    # Bench section (voluntary + overflow) — shown above class columns
    if waitlist:
        bench_lines = [
            f"{r['position']}. {r['user_name']}"
            for r in waitlist
        ]
        bench_value = "\n".join(bench_lines)
    else:
        bench_value = "-"
    embed.add_field(name=f"🪑 Bench ({len(waitlist)})", value=bench_value, inline=False)

    # Group confirmed by class name, preserving registration order
    by_class: dict[str, list[dict]] = defaultdict(list)
    for reg in confirmed:
        by_class[reg["class_name"]].append(reg)

    # One inline field per class — always shown even if empty
    all_classes = flyff_api.get_all_classes()
    for cls in all_classes:
        cls_name = cls["name"]["en"]
        emoji = CLASS_EMOJIS.get(cls_name, "•")
        regs = by_class.get(cls_name, [])

        field_name = f"{emoji} {cls_name} ({len(regs)})"
        if regs:
            field_value = "\n".join(
                f"{r['position']}. {r['user_name']}" for r in regs
            )
        else:
            field_value = "-"

        embed.add_field(name=field_name, value=field_value, inline=True)

    # Pad to a multiple of 3 so the last row aligns cleanly
    remainder = len(all_classes) % 3
    if remainder:
        for _ in range(3 - remainder):
            embed.add_field(name="​", value="​", inline=True)

    creator = event.get("creator_name") or f"user {event['creator_id']}"
    embed.set_footer(
        text=f"Sign ups: {len(confirmed)}/{max_slots} · Created by {creator}"
    )
    return embed


def build_pve_embed(
    event: dict,
    confirmed: list[dict],
    waitlist: list[dict],
) -> discord.Embed:
    is_open = bool(event["is_open"])
    colour = COLOR_PVE if is_open else COLOR_CLOSED
    embed = discord.Embed(
        title=event["title"],
        description=event.get("description") or "",
        colour=colour,
    )
    embed.add_field(name="📅 Date", value=_format_date(event["event_date"]), inline=False)

    role_caps = {
        "Tank":    event.get("slots_tank") or 0,
        "Support": event.get("slots_support") or 0,
        "1v1":     event.get("slots_1v1") or 0,
        "AOE":     event.get("slots_aoe") or 0,
    }

    # Group confirmed by role
    by_role: dict[str, list[dict]] = defaultdict(list)
    for reg in confirmed:
        if reg["role"]:
            by_role[reg["role"]].append(reg)

    slots_lines = []
    for role_key in ["Tank", "Support", "1v1", "AOE"]:
        cap = role_caps[role_key]
        if cap == 0:
            continue
        emoji = PVE_ROLE_EMOJIS[role_key]
        label = PVE_ROLE_LABELS[role_key]
        regs = by_role.get(role_key, [])
        filled = len(regs)

        if regs:
            player_text = "\n".join(
                f"{CLASS_EMOJIS.get(r['class_name'], '')}  {r['position']}. {r['user_name']}" for r in regs
            )
        else:
            player_text = "-"

        slots_lines.append(
            f"**{label}**  ({filled}/{cap})\n{player_text}"
           )

    embed.add_field(
        name="Slots",
        value="\n\u200b\n".join(slots_lines) if slots_lines else "*No roles configured*",
        inline=False,
    )

    if waitlist:
        wl_lines = [
            f"{i + 1}. {reg['user_name']} ({PVE_ROLE_LABELS.get(reg['role'], reg['role'])})"
            for i, reg in enumerate(waitlist)
        ]
        embed.add_field(
            name=f"Waitlist ({len(waitlist)})",
            value="\n".join(wl_lines),
            inline=False,
        )

    creator = event.get("creator_name") or f"user {event['creator_id']}"
    embed.set_footer(text=f"Created by {creator}")
    return embed
