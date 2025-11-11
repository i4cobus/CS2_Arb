# app/market_name.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Literal

WearKey = Optional[Literal["fn","mw","ft","ww","bs"]]
CategoryKey = Optional[Literal["normal","stattrak","souvenir"]]

WEAR_MAP = {
    "fn": "Factory New",
    "mw": "Minimal Wear",
    "ft": "Field-Tested",
    "ww": "Well-Worn",
    "bs": "Battle-Scared",  # Steam uses "Battle-Scarred"
}
WEAR_MAP["bs"] = "Battle-Scarred"  # fix typo safeguard

STAR = "★"
STATTRAK = "StatTrak™"
SOUVENIR = "Souvenir"

@dataclass(frozen=True)
class FamilyRules:
    name: str
    supports_wear: bool
    allows_stattrak: bool
    allows_souvenir: bool
    has_star_prefix: bool  # knives
    notes: str = ""


# Heuristics by leading tokens or patterns in the base name
FAMILIES = [
    FamilyRules("knife",      True,  True,  False, True,  ),
    FamilyRules("gloves",     True,  False, False, True ),
    FamilyRules("weapon",     True,  True,  True,  False ),   # rifles/pistols/SMGs/shotguns
    FamilyRules("music_kit",  False, True,  False, False ),
    FamilyRules("sticker",    False, False, False, False ),
    FamilyRules("patch",      False, False, False, False ),
    FamilyRules("agent",      False, False, False, False ),
    FamilyRules("graffiti",   False, False, False, False ),
    FamilyRules("charm",      False, False, False, False ),    # future-proof
    FamilyRules("collectible",False, False, False, False ),    # pins/collectibles
    FamilyRules("case",       False, False, False, False ),
    FamilyRules("souvenir_pkg",False,False, False, False ),
    FamilyRules("tool",       False, False, False, False ),    # Name Tag, etc.
    FamilyRules("pass",       False, False, False, False ),    # Viewer/Operation passes
    FamilyRules("gift",       False, False, False, False ),
]

KNIFE_NAMES = {
    "Karambit", "Bayonet", "M9 Bayonet", "Flip Knife", "Gut Knife", "Huntsman Knife",
    "Falchion Knife", "Shadow Daggers", "Bowie Knife", "Ursus Knife", "Navaja Knife",
    "Stiletto Knife", "Talon Knife", "Skeleton Knife", "Paracord Knife", "Survival Knife",
    "Nomad Knife", "Classic Knife", "Kukri Knife"
}

GLOVE_NAMES = {
    "Sport Gloves", "Moto Gloves", "Specialist Gloves", "Driver Gloves",
    "Hand Wraps", "Hydra Gloves", "Bloodhound Gloves"
}

def _lhs_item_name(base_name: str) -> str:
    """Left side of 'A | B' → 'A' (trimmed)."""
    if "|" in base_name:
        return base_name.split("|", 1)[0].strip()
    return base_name.strip()

def _infer_family(base_name: str) -> FamilyRules:
    n = (base_name or "").strip()
    low = n.lower()
    lhs = _lhs_item_name(n)

    # explicit patterns first
    if low.startswith("music kit |") or low.startswith("stattrak™ music kit |"):
        return _get("music_kit")
    if low.startswith("sticker |"):
        return _get("sticker")
    if low.startswith("patch |"):
        return _get("patch")
    if low.startswith("sealed graffiti |") or low.startswith("graffiti |"):
        return _get("graffiti")
    if low.startswith("charm |"):
        return _get("charm")
    if low.startswith("souvenir package") or "souvenir package" in low:
        return _get("souvenir_pkg")
    if low.endswith(" case") or low.endswith(" case (old)"):
        return _get("case")
    if " pin" in low or "collectible" in low:
        return _get("collectible")
    if " viewer pass" in low or low.endswith(" pass"):
        return _get("pass")
    if " gift" in low:
        return _get("gift")
    if n.startswith(STAR + " "):
        return _get("knife")

    # NEW: detect knives/gloves by LHS item name (even without the star)
    if lhs in KNIFE_NAMES or lhs.endswith(" Knife"):
        return _get("knife")
    if lhs in GLOVE_NAMES:
        return _get("gloves")

    # crude agent heuristic
    if " | " in n and any(x in low for x in ("swat", "fbi", "phoenix", "cmdr.", "marshal", "soldier", "the professionals")):
        return _get("agent")

    # default to weapon skins
    return _get("weapon")

def _get(key: str) -> FamilyRules:
    for f in FAMILIES:
        if f.name == key:
            return f
    # default to weapon
    return FamilyRules("weapon", True, True, True, False)


def _has_parentheses(name: str) -> bool:
    return "(" in name and ")" in name


def _already_prefixed(name: str) -> bool:
    low = name.lower().strip()
    return low.startswith("stattrak") or low.startswith("souvenir") or low.startswith(STAR.lower())


def build_market_hash_name(
    base_name: str,
    wear: WearKey = None,             # "fn","mw","ft","ww","bs" or None
    category: CategoryKey = None,     # "normal","stattrak","souvenir" or None
) -> str:
    """
    Build a proper Steam/CSFloat market_hash_name from normalized inputs.
    - Respects item family rules (wear/StatTrak/Souvenir applicability).
    - Places StatTrak correctly for knives (after star).
    - Avoids duplicating wear if base_name already includes parentheses.
    - If base_name already seems canonical (has prefix or suffix), we only add what's missing.
    """
    name = (base_name or "").strip()
    fam = _infer_family(name)

    # --- category normalization vs allowances ---
    cat = (category or "normal").lower()
    if cat == "stattrak" and not fam.allows_stattrak:
        cat = "normal"
    if cat == "souvenir" and not fam.allows_souvenir:
        cat = "normal"

    # --- prefix handling (StatTrak/Souvenir and star for knives) ---
    # If base_name is already fully qualified, don't double-prefix.
    already = _already_prefixed(name)
    if fam.has_star_prefix:
        # Guarantee the star at the very beginning for knives
        if not name.startswith(STAR + " "):
            name = f"{STAR} {name}"

        # Place StatTrak™ right after the star for knives
        if (cat == "stattrak") and (STATTRAK not in name):
            name = name.replace(STAR + " ", f"{STAR} {STATTRAK} ", 1)
        elif (cat != "stattrak") and (STATTRAK in name):
            # user asked for normal/souvenir but provided a name with StatTrak; strip it
            name = name.replace(f"{STAR} {STATTRAK} ", f"{STAR} ", 1)
    else:
        # Non-knives
        if not already:
            if cat == "stattrak":
                name = f"{STATTRAK} {name}"
            elif cat == "souvenir":
                name = f"{SOUVENIR} {name}"
        else:
            # If already prefixed but category suggests otherwise, resist double-prefixing
            if cat == "stattrak" and (STATTRAK not in name) and (SOUVENIR not in name):
                name = f"{STATTRAK} {name}"
            if cat == "souvenir" and (SOUVENIR not in name) and (STATTRAK not in name):
                name = f"{SOUVENIR} {name}"

    # --- wear suffix ---
    if fam.supports_wear and wear and not _has_parentheses(name):
        wear_text = WEAR_MAP.get(wear.lower())
        if wear_text:
            name = f"{name} ({wear_text})"

    return name