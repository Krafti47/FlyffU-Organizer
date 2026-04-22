from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
ICONS_DIR = DATA_DIR / "icons"
DB_PATH = DATA_DIR / "flyff.db"
CLASSES_JSON = DATA_DIR / "classes.json"

# Discord role names (must match server exactly)
PVP_ROLE_NAME = "Siege"
MEMBER_ROLE_NAME = "Member"

# PVP settings
PVP_MAX_SLOTS = 15

# Flyff API
FLYFF_API_BASE = "https://api.flyff.com"

# Only 2nd-tier (professional) and 3rd-tier classes
CLASS_IDS = [
    20311, # Harlequin
    21680, # Seraph
    22213, # Mentalist
    23509, # Slayer
    23623, # Forcemaster
    25863, # Arcanist
    28125, # Templar
    28695, # Crackshooter
]

# PVE roles: internal key -> display label
PVE_ROLE_LABELS = {
    "Tank":    "Tank",
    "Support": "Support",
    "1v1":     "DPS: 1v1",
    "AOE":     "DPS: AOE",
}

PVE_ROLE_EMOJIS = {
    "Tank":    "🛡️",
    "Support": "💖",
    "1v1":     "⚔️",
    "AOE":     "💥",
}

_EMOJIS_FILE = DATA_DIR / "emojis.json"
if _EMOJIS_FILE.exists():
    import json as _json
    with _EMOJIS_FILE.open(encoding="utf-8") as _f:
        CLASS_EMOJIS: dict[str, str] = _json.load(_f)
else:
    # Unicode fallbacks — run scripts/setup_emojis.py to get custom class icons
    CLASS_EMOJIS = {
        "Arcanist":     "🌀",
        "Crackshooter": "🏹",
        "Forcemaster":  "💪",
        "Harlequin":    "🃏",
        "Mentalist":    "🔮",
        "Seraph":       "✨",
        "Slayer":       "⚔️",
        "Templar":      "🛡️",
    }
            
# Embed colours
COLOR_PVP = 0x3498DB    # blue
COLOR_PVE = 0x2ECC71    # green
COLOR_CLOSED = 0x95A5A6  # grey
