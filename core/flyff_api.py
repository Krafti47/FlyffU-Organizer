from __future__ import annotations

import json
import logging

from config import CLASSES_JSON

log = logging.getLogger(__name__)

_CACHE: dict[int, dict] = {}
_ORDERED: list[dict] = []

_TIER_ORDER = {"professional": 0, "advanced": 1}


def get_all_classes() -> list[dict]:
    return _ORDERED


def get_class(class_id: int) -> dict | None:
    return _CACHE.get(class_id)


def _populate_from_list(classes: list[dict]) -> None:
    _CACHE.clear()
    for cls in classes:
        _CACHE[cls["id"]] = cls

    def sort_key(c: dict) -> tuple:
        tier = _TIER_ORDER.get(c.get("type", ""), 99)
        return (tier, c["name"]["en"])

    _ORDERED.clear()
    _ORDERED.extend(sorted(classes, key=sort_key))


async def load_classes() -> None:
    if not CLASSES_JSON.exists():
        raise FileNotFoundError(
            f"Class data not found at {CLASSES_JSON}. "
            "Make sure data/classes.json exists."
        )

    with CLASSES_JSON.open("r", encoding="utf-8") as f:
        classes = json.load(f)

    _populate_from_list(classes)
    log.info("Loaded %d classes from %s.", len(_ORDERED), CLASSES_JSON)
