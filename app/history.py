# app/history.py
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import quote

import httpx

from .config import CFG, require_config

API_BASE = "https://csfloat.com/api/v1"

# ------------------------ helpers ------------------------

def _headers() -> dict[str, str]:
    require_config()
    return {"Authorization": CFG["CSFLOAT_API_KEY"]}

def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    """Parse ISO timestamps including trailing 'Z' → UTC."""
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return None

_NON_FLOAT_KEYWORDS = {
    "music kit", "sticker", "patch", "agent", "graffiti",
    "case", "collectible", "pin", "key", "viewer pass", "souvenir package",
    "charm", "gift",
}

def _item_supports_float(name: str) -> bool:
    low = (name or "").lower()
    return not any(k in low for k in _NON_FLOAT_KEYWORDS)

def _as_int(x, default=0) -> int:
    try:
        return int(x)
    except Exception:
        return default

def _as_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

# ------------------------ API ------------------------

def fetch_sales_history(name: str, limit: int = 200, debug: bool = False) -> List[Dict[str, Any]]:
    """
    GET /history/<market_hash_name>/sales
    Returns a list of sale events (dicts). Prices are cents.
    """
    url = f"{API_BASE}/history/{quote(name, safe='')}/sales"
    params = {"limit": max(1, min(int(limit or 200), 400))}

    if debug:
        print("➡️  GET", url, params)

    # simple retry for 429/5xx once
    for attempt in (1, 2):
        r = httpx.get(url, headers=_headers(), params=params, timeout=30)
        if debug:
            print(f"⬅️  Status: {r.status_code} (attempt {attempt})")
        if r.status_code == 429 or 500 <= r.status_code < 600:
            if attempt == 1:
                time.sleep(1.5)
                continue
        r.raise_for_status()
        break

    data = r.json()
    # History API should return a list, but be defensive
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # sometimes wrapped
        for k in ("results", "data", "items", "events"):
            v = data.get(k)
            if isinstance(v, list):
                return v
    return []

def compute_sales_24h_metrics(
    name: str,
    wear_bucket: Optional[Tuple[float, float]],   # (min_float, max_float) or None
    category: Optional[int],                      # 1 normal, 2 stattrak, 3 souvenir, or None
    lookback_hours: int = 24,
    limit: int = 400,
    debug: bool = False,
) -> Tuple[int, float]:
    """
    Returns (vol24h, asp24h_usd) for the given item, optionally filtered by wear & category.
    Client-side filter uses event['item'] fields: float_value, is_stattrak, is_souvenir.
    - We automatically disable wear filtering for non-floatable families (Music Kits, Stickers, etc.).
    - We count only events whose state is 'sold'.
    """
    # Disable wear filter for non-floatables
    if not _item_supports_float(name):
        wear_bucket = None

    events = fetch_sales_history(name, limit=limit, debug=debug)
    if not events:
        if debug:
            print("🟡 No history events returned.")
        return 0, 0.0

    now = datetime.now(timezone.utc)
    lb_seconds = int(lookback_hours) * 3600

    def _cat_ok(item: Dict[str, Any]) -> bool:
        if category is None:
            return True
        is_st = bool(item.get("is_stattrak"))
        is_sv = bool(item.get("is_souvenir"))
        c = 3 if is_sv else (2 if is_st else 1)
        return c == category

    def _wear_ok(item: Dict[str, Any]) -> bool:
        if not wear_bucket:
            return True
        fv = item.get("float_value")
        if fv is None:
            return False
        try:
            fv = float(fv)
        except (TypeError, ValueError):
            return False
        lo, hi = wear_bucket
        return lo <= fv < hi

    vol = 0
    total_price_usd = 0.0

    for e in events:
        # Consider only sold events
        state = (e.get("state") or "").lower()
        if state and state != "sold":
            continue

        ts = _parse_iso(e.get("sold_at")) or _parse_iso(e.get("created_at"))
        if not ts or not ts.tzinfo:
            continue
        if (now - ts).total_seconds() > lb_seconds:
            continue

        item = e.get("item") or {}
        if not (_cat_ok(item) and _wear_ok(item)):
            continue

        price_cents = e.get("price")
        if price_cents is None:
            continue
        price_cents = _as_int(price_cents, 0)
        if price_cents <= 0:
            continue

        vol += 1
        total_price_usd += (price_cents / 100.0)

    asp = (total_price_usd / vol) if vol > 0 else 0.0

    if debug:
        print(f"📊 24h metrics for {name}: vol={vol}, asp=${asp:.2f}")

    return vol, asp