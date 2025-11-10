# app/history.py
import httpx
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import quote
from .config import CFG, require_config

API_BASE = "https://csfloat.com/api/v1"

def _headers() -> dict[str, str]:
    require_config()
    return {"Authorization": CFG["CSFLOAT_API_KEY"]}

def fetch_sales_history(name: str, limit: int = 200) -> List[Dict[str, Any]]:
    """
    GET /history/<market_hash_name>/sales
    Returns a list of sale events (dicts).
    Prices are in cents; timestamps are ISO8601 with Z.
    """
    url = f"{API_BASE}/history/{quote(name, safe='')}/sales"
    r = httpx.get(url, headers=_headers(), params={"limit": limit}, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []

def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        # Handle ...Z by replacing with +00:00
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return None

def compute_sales_24h_metrics(
    name: str,
    wear_bucket: Optional[Tuple[float, float]],   # (min_float, max_float) or None
    category: Optional[int],                      # 1 normal, 2 stattrak, 3 souvenir, or None
    lookback_hours: int = 24,
    limit: int = 400,
) -> Tuple[int, float]:
    """
    Returns (vol24h, asp24h_usd) for the given item, optionally filtered by wear & category.
    We filter client-side using 'item.float_value', 'item.is_stattrak', 'item.is_souvenir'.
    """
    events = fetch_sales_history(name, limit=limit)
    if not events:
        return 0, 0.0

    now = datetime.now(timezone.utc)
    lb_seconds = lookback_hours * 3600

    def _cat_ok(item: Dict[str, Any]) -> bool:
        if category is None:
            return True
        is_st = bool(item.get("is_stattrak"))
        is_sv = bool(item.get("is_souvenir"))
        # map to 1/2/3
        c = 3 if is_sv else (2 if is_st else 1)
        return c == category

    def _wear_ok(item: Dict[str, Any]) -> bool:
        if not wear_bucket:
            return True
        fv = item.get("float_value")
        if fv is None:
            return False
        return (wear_bucket[0] <= float(fv) < wear_bucket[1])

    vol = 0
    total_price_usd = 0.0

    for e in events:
        # Prefer 'sold_at'; fall back to 'created_at'
        ts = _parse_iso(e.get("sold_at")) or _parse_iso(e.get("created_at"))
        if not ts or not ts.tzinfo:
            continue
        if (now - ts).total_seconds() > lb_seconds:
            continue
        item = e.get("item") or {}
        if not (_cat_ok(item) and _wear_ok(item)):
            continue
        price_cents = e.get("price")
        if not isinstance(price_cents, (int, float)):
            continue
        vol += 1
        total_price_usd += (float(price_cents) / 100.0)

    asp = (total_price_usd / vol) if vol > 0 else 0.0
    return vol, asp