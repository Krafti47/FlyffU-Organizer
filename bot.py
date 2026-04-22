from __future__ import annotations

import logging
import os

import discord
from discord.ext import tasks
from dotenv import load_dotenv

from config import DATA_DIR, ICONS_DIR
from core import database as db
from core import flyff_api
from core.views import make_event_view

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("flyff-bot")


class FlyffBot(discord.Bot):
    async def on_ready(self) -> None:
        # Ensure data directories exist
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        ICONS_DIR.mkdir(parents=True, exist_ok=True)

        await db.init_db()
        await flyff_api.load_classes()

        # Re-register persistent views for all open events
        open_events = await db.get_all_open_events()
        for event in open_events:
            view = make_event_view(event, self)
            self.add_view(view, message_id=event["message_id"])

        log.info(
            "Logged in as %s | %d open event(s) re-registered.",
            self.user,
            len(open_events),
        )

        if not self._cleanup_task.is_running():
            self._cleanup_task.start()

    @tasks.loop(hours=24)
    async def _cleanup_task(self) -> None:
        count = await db.delete_events_older_than_one_month()
        if count:
            log.info("Deleted %d event(s) older than 1 month.", count)


def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set. Create a .env file from .env.example.")

    bot = FlyffBot(intents=discord.Intents.default())
    bot.load_extension("cogs.pvp_events")
    bot.load_extension("cogs.pve_events")
    bot.run(token)


if __name__ == "__main__":
    main()
