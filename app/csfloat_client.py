import time
import httpx
from typing import Iterator, Dict, Any, Optional, List, Tuple
from .models import Listing
from .config import CFG, require_config
from .history import compute_sales_24h_metrics

API_BASE = "https://csfloat.com/api/v1"

class CSFloatError(RuntimeError): ...

def _headers() -> dict[str, str]:
    require_config()
    key = CFG["CSFLOAT_API_KEY"]
    return {"Authorization": key}  # raw key; no "Bearer"

def _extract_rows(payload) -> list[dict]:
    # raw list
    if isinstance(payload, list):
        return payload
    # common dict shapes
    if isinstance(payload, dict):
        for k in ("listings", "results", "data", "items"):
            v = payload.get(k)
            if isinstance(v, list):
                return v
    return []

def iter_listings(
    market_hash_name: Optional[str] = None,
    sort_by: str = "lowest_price",
    limit: int = 50,
    extra_params: Optional[Dict[str, Any]] = None,
    max_pages: int = 5,
    backoff_s: float = 1.5,
    debug: bool = False,
) -> Iterator[dict]:
    params: Dict[str, Any] = {"limit": min(limit, 50), "sort_by": sort_by}
    if market_hash_name:
        params["market_hash_name"] = market_hash_name
    if extra_params:
        params.update(extra_params)

    cursor = None
    pages = 0
    with httpx.Client(timeout=20) as client:
        while True:
            if cursor:
                params["cursor"] = cursor
            if debug:
                print("GET /listings", {"params": {k: v for k, v in params.items() if k != "cursor"}})
            r = client.get(f"{API_BASE}/listings", headers=_headers(), params=params)
            if debug:
                print("Status:", r.status_code, "X-Next-Cursor:", r.headers.get("X-Next-Cursor"))
            if r.status_code == 429:
                time.sleep(backoff_s)
                continue
            r.raise_for_status()
            payload = r.json()
            rows = _extract_rows(payload)
            if debug and not rows:
                print("No rows in this page. Raw keys:", list(payload.keys()) if isinstance(payload, dict) else "list/empty")
            if not rows:
                return
            for row in rows:
                yield row
            cursor = r.headers.get("X-Next-Cursor") or None
            pages += 1
            if not cursor or pages >= max_pages:
                return

def map_listing(row: dict) -> Listing:
    item = row.get("item", {})
    price_cents = row.get("price", 0)
    return Listing(
        id=str(row.get("id")) if row.get("id") is not None else None,
        market_hash_name=item.get("market_hash_name", ""),
        price_usd=float(price_cents) / 100.0,
        float_value=row.get("float_value"),
        state=row.get("state"),
        paint_seed=row.get("paint_seed"),
    )

def _first_listing(
    name: str,
    sort_by: str,
    category: int | None,
    wear_bucket: tuple[float, float] | None,
) -> Listing | None:
    params: Dict[str, Any] = {}
    if category is not None:
        params["category"] = category              # 1 normal, 2 stattrak, 3 souvenir
    if wear_bucket:
        params["min_float"], params["max_float"] = wear_bucket

    for row in iter_listings(
        market_hash_name=name,
        sort_by=sort_by,
        limit=50,
        extra_params=params,
        max_pages=1,
    ):
        return map_listing(row)
    return None

def fetch_buy_orders_for_listing(listing_id: str, limit: int = 10) -> list[dict]:
    r = httpx.get(
        f"{API_BASE}/listings/{listing_id}/buy-orders",
        headers=_headers(),
        params={"limit": limit},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []

def highest_bid_from_orders(orders: list[dict]) -> Tuple[float, int] | None:
    """
    Returns (highest_bid_usd, qty_at_top) or None if empty. Prices are cents.
    """
    if not orders:
        return None
    # Filter to orders that actually have numeric price
    clean = [o for o in orders if isinstance(o.get("price"), (int, float))]
    if not clean:
        return None
    top_cents = max(int(o["price"]) for o in clean)
    qty_top = sum(int(o.get("qty", 0)) for o in clean if int(o["price"]) == top_cents)
    return (top_cents / 100.0, qty_top)

def fetch_snapshot_metrics(
    name: str,
    category: int | None = None,                        # 1=normal, 2=stattrak, 3=souvenir
    wear_bucket: tuple[float, float] | None = None,     # (min_float, max_float)
    debug: bool = False,
) -> dict:
    """
    Snapshot for one item:
      - lowest ask (by filters)
      - highest bid (+ qty) via /listings/{id}/buy-orders
      - vol24h & asp24h via /history/<name>/sales (filtered client-side)
    """
    def try_first(sort_by: str, cat: int | None, wb: tuple[float, float] | None, label: str):
        lst = _first_listing(name, sort_by, cat, wb)
        return lst, label

    # Lowest ask with fallback cascade
    lowest, source = try_first("lowest_price", category, wear_bucket, "strict(name+cat+wear)")
    used_cat, used_wear = category, wear_bucket

    if lowest is None and wear_bucket is not None:
        lowest, source = try_first("lowest_price", category, None, "no_wear(name+cat)")
        if lowest:
            used_wear = None

    if lowest is None and category is not None:
        lowest, source = try_first("lowest_price", None, wear_bucket, "no_cat(name+wear)")
        if lowest:
            used_cat = None

    if lowest is None:
        lowest, source = try_first("lowest_price", None, None, "name_only")

    # Highest bid from lowest listing id
    highest_bid = None
    highest_bid_qty = None
    if lowest and lowest.id:
        orders = fetch_buy_orders_for_listing(lowest.id, limit=10)
        hb = highest_bid_from_orders(orders)
        if hb:
            highest_bid, highest_bid_qty = hb

    # Sales 24h (filtered by original requested filters, not the relaxed ones)
    vol24h, asp24h = compute_sales_24h_metrics(name, wear_bucket, category, lookback_hours=24, limit=400)

    return {
        "source": source,
        "lowest_ask": lowest.price_usd if lowest else 0.0,
        "lowest_ask_id": lowest.id if lowest else "",
        "highest_bid": highest_bid,
        "highest_bid_qty": highest_bid_qty,
        "vol24h": vol24h,
        "asp24h": asp24h,
        "used_category": used_cat,
        "used_wear": used_wear,
    }

# Extra utilities kept for future features (top-N, base price, etc.)
def fetch_top_n_for_item(
    name: str,
    n: int = 10,
    sort_by: str = "lowest_price",
    category: int | None = None,
    wear_bucket: tuple[float, float] | None = None,
) -> list[Listing]:
    params: Dict[str, Any] = {}
    if category is not None:
        params["category"] = category
    if wear_bucket:
        params["min_float"], params["max_float"] = wear_bucket

    listings: list[Listing] = []
    for row in iter_listings(
        market_hash_name=name,
        sort_by=sort_by,
        limit=50,
        extra_params=params,
        max_pages=5,
    ):
        listings.append(map_listing(row))
        if len(listings) >= n:
            break
    return listings