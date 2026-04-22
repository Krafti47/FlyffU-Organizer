# FlyffU Organizer

A Discord bot for Flyff Universe guilds to manage **Siege (PvP)** and **PvE** group events. Members sign up with their class, pick a role for PvE, and the bot keeps a live embed updated in your channel.

---

## Features

- **/pvp create** — Post a Siege event embed with Register / Bench / Leave buttons
- **/pve create** — Post a PvE event embed with configurable Tank / Support / DPS slots
- Live embed updates on every sign-up or leave
- **Bench** — players can voluntarily join as reserve; overflow registrations land here automatically
- **Auto-promote** — first bench player is promoted when a confirmed spot opens up
- **Class icons** — custom class emojis shown next to each player (set up once with the emoji script)
- **Auto-cleanup** — events older than 1 month are deleted automatically

---

## Requirements

- Python 3.12+
- A Discord application with a bot user ([Discord Developer Portal](https://discord.com/developers/applications))
- The bot needs **Send Messages**, **Embed Links**, **Attach Files**, and **Use Application Commands** permissions

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/FlyffU-Organizer.git
cd FlyffU-Organizer
pip install -r requirements.txt
```

### 2. Create your bot token

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Create a new application → go to **Bot** → click **Reset Token** and copy it
3. Enable **Server Members Intent** and **Message Content Intent** under Privileged Gateway Intents

### 3. Configure

Copy `.env.example` to `.env` and paste your token:

```
BOT_TOKEN=your_bot_token_here
```

Open `config.py` and adjust the role names to match your server:

```python
PVP_ROLE_NAME  = "Siege"   # Role allowed to create Siege events
MEMBER_ROLE_NAME = "Member"  # Role allowed to create PvE events
PVP_MAX_SLOTS  = 15        # Max confirmed participants per Siege event
```

### 4. Create the roles in your Discord server

Make sure roles named exactly as set above exist in your server and are assigned to the right members.

### 5. Set up class emojis *(optional but recommended)*

This uploads the class icons as **application emojis** — they belong to your bot and work in any server automatically.

```bash
python scripts/setup_emojis.py
```

Run this once. It creates `data/emojis.json` which the bot loads on startup. Without this step the bot falls back to Unicode emojis (⚔️ 🔮 etc.).

### 6. Invite the bot to your server

In the Developer Portal go to **OAuth2 → URL Generator**, select scopes `bot` and `applications.commands`, then select the permissions listed above. Open the generated URL to invite the bot.

### 7. Run the bot

```bash
python bot.py
```

---

## Configuration reference

All settings live in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `PVP_ROLE_NAME` | `"Siege"` | Discord role required to run `/pvp create` |
| `MEMBER_ROLE_NAME` | `"Member"` | Discord role required to run `/pve create` |
| `PVP_MAX_SLOTS` | `15` | Max confirmed slots per Siege event |

---

## Slash commands

| Command | Required role | Parameters |
|---------|--------------|------------|
| `/pvp create` | Siege | `title`, `date` (YYYY-MM-DD HH:MM), `description` *(optional)* |
| `/pve create` | Member | `title`, `date`, `description` *(optional)*, `tanks`, `supports`, `dps_1v1`, `aoe` |

---

## How events work

**Signing up (PvP/Siege)**
1. Click **Register** → choose your class → click **Sign Up** (confirmed) or **🪑 Bench** (reserve)
2. If all 15 slots are taken, Sign Up automatically goes to Bench
3. Click **Leave** to remove yourself; the first Bench player is promoted automatically

**Signing up (PvE)**
1. Click **Register** → choose your class → choose your role (Tank / Support / DPS)
2. Full roles are disabled; clicking an open role confirms you
3. Leave works the same as PvP

**Auto-cleanup**
Events whose date is more than 1 month in the past are deleted automatically every 24 hours (along with all registrations).

---

## License

MIT — see [LICENSE](LICENSE)
