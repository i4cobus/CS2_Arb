# app/logger.py
import os, csv, time
from typing import Optional, Dict, Any

HIST_PATH = os.path.join("logs", "csfloat_snapshots.csv")
LATEST_PATH = os.path.join("logs", "csfloat_snapshot_latest.csv")

COLUMNS = [
    "timestamp",
    "item",
    "wear",
    "category",
    "source",
    "used_category",
    "used_wear",
    "lowest_ask_usd",
    "lowest_ask_id",
    "highest_bid_usd",
    "highest_bid_qty",
    "vol24h",
    "asp24h_usd",
]

def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)

def _row_from_snapshot(
    name: str,
    wear: Optional[str],
    category: Optional[str],
    snap: Dict[str, Any],
) -> list:
    return [
        int(time.time()),
        name,
        wear or "",
        category or "",
        snap.get("source", ""),
        snap.get("used_category", ""),
        snap.get("used_wear", ""),
        f"{float(snap.get('lowest_ask', 0.0)):.2f}",
        snap.get("lowest_ask_id", ""),
        (f"{float(snap['highest_bid']):.2f}" if snap.get("highest_bid") is not None else ""),
        (str(int(snap["highest_bid_qty"])) if snap.get("highest_bid_qty") is not None else ""),
        (str(int(snap["vol24h"])) if snap.get("vol24h") is not None else ""),
        (f"{float(snap['asp24h']):.2f}" if snap.get("asp24h") is not None else ""),
    ]

def log_snapshot_both(
    name: str,
    wear: Optional[str],
    category: Optional[str],
    snap: Dict[str, Any],
    hist_path: str = HIST_PATH,
    latest_path: str = LATEST_PATH,
) -> None:
    """
    Writes one row to the historical CSV (append) and overwrites the 'latest' CSV.
    """
    _ensure_dir(hist_path)
    _ensure_dir(latest_path)

    row = _row_from_snapshot(name, wear, category, snap)

    # 1) Append to history (create header if file doesn't exist or is empty)
    need_header = not os.path.exists(hist_path) or os.path.getsize(hist_path) == 0
    with open(hist_path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if need_header:
            w.writerow(COLUMNS)
        w.writerow(row)

    # 2) Overwrite latest (always with header + single row)
    with open(latest_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        w.writerow(row)