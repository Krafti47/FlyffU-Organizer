"""
Run this script once after creating your Discord bot application.
It uploads the class icons as Discord application emojis (they belong to the
bot itself, so they work in every server without any server-level setup).
The resulting emoji IDs are saved to data/emojis.json and loaded automatically
by the bot on next start.

Usage:
    python scripts/setup_emojis.py
"""
from __future__ import annotations

import asyncio
import base64
import json
import sys
from pathlib import Path

import aiohttp
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
ICONS_DIR = DATA_DIR / "icons"
CLASSES_JSON = DATA_DIR / "classes.json"
EMOJIS_OUT = DATA_DIR / "emojis.json"

API = "https://discord.com/api/v10"


async def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("ERROR: BOT_TOKEN not found. Make sure .env exists with your token.")
        sys.exit(1)

    headers = {"Authorization": f"Bot {token}"}

    async with aiohttp.ClientSession(headers=headers) as session:
        # Resolve application ID
        async with session.get(f"{API}/users/@me") as resp:
            if resp.status != 200:
                print(f"ERROR: Could not authenticate ({resp.status}). Check your BOT_TOKEN.")
                sys.exit(1)
            me = await resp.json()
            app_id = me["id"]
            print(f"Logged in as {me['username']} (app id: {app_id})")

        # Fetch existing application emojis to avoid uploading duplicates
        async with session.get(f"{API}/applications/{app_id}/emojis") as resp:
            data = await resp.json()
            existing = {e["name"]: e for e in data.get("items", [])}
            print(f"Found {len(existing)} existing application emoji(s).")

        # Load class list
        with CLASSES_JSON.open(encoding="utf-8") as f:
            classes = json.load(f)

        result: dict[str, str] = {}

        for cls in classes:
            cls_name: str = cls["name"]["en"]
            icon_file: str = cls.get("icon", "")
            icon_path = ICONS_DIR / icon_file

            if not icon_path.exists():
                print(f"  SKIP {cls_name}: icon file not found ({icon_path.name})")
                continue

            # Use lowercase alphanumeric name as Discord emoji name (max 32 chars, no spaces)
            emoji_name = cls_name.lower().replace(" ", "_")[:32]

            if emoji_name in existing:
                emoji = existing[emoji_name]
                print(f"  SKIP {cls_name}: already exists as :{emoji_name}:")
                result[cls_name] = f"<:{emoji_name}:{emoji['id']}>"
                continue

            # Encode image as base64 data URI
            image_data = base64.b64encode(icon_path.read_bytes()).decode()
            payload = {"name": emoji_name, "image": f"data:image/png;base64,{image_data}"}

            async with session.post(f"{API}/applications/{app_id}/emojis", json=payload) as resp:
                if resp.status == 201:
                    emoji = await resp.json()
                    result[cls_name] = f"<:{emoji_name}:{emoji['id']}>"
                    print(f"  OK  {cls_name} → :{emoji_name}:")
                else:
                    body = await resp.text()
                    print(f"  FAIL {cls_name}: {resp.status} {body}")

            # Small delay to avoid rate limits
            await asyncio.sleep(0.5)

        # Write emojis.json
        with EMOJIS_OUT.open("w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"\nDone! {len(result)} emoji(s) saved to {EMOJIS_OUT}")
        print("Restart the bot to apply the new emojis.")


if __name__ == "__main__":
    asyncio.run(main())
