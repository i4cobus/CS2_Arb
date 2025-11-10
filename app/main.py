import sys, os, csv, time
from tabulate import tabulate
from .config import CFG, require_config
from .wear import wear_bucket_range
from .csfloat_client import fetch_snapshot_metrics
from .logger import log_snapshot_both

CATEGORY_MAP = {"normal": 1, "stattrak": 2, "souvenir": 3}

def parse_args(argv: list[str]):
    args = {"mode": "snapshot", "names": [], "wear": None, "category": None, "debug": False}
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == "--snapshot":
            args["mode"] = "snapshot"; args["names"] = [argv[i+1]]; i += 2
        elif tok == "--wear":
            args["wear"] = argv[i+1].lower(); i += 2
        elif tok == "--category":
            args["category"] = argv[i+1].lower(); i += 2
        elif tok == "--debug":
            args["debug"] = True; i += 1
        else:
            args["names"].append(tok); i += 1
    return args

def main():
    require_config()

    args = parse_args(sys.argv[1:])
    if not args["names"]:
        if CFG["DEFAULT_ITEM"]:
            args["names"] = [CFG["DEFAULT_ITEM"]]
        else:
            print('Usage: python -m app.main --snapshot "AK-47 | Redline (Field-Tested)" --wear ft --category normal')
            return

    if args["mode"] == "snapshot":
        name = args["names"][0]
        wear_bucket = wear_bucket_range(args["wear"]) if args.get("wear") else None
        category = CATEGORY_MAP.get(args.get("category")) if args.get("category") else None

        snap = fetch_snapshot_metrics(name, category=category, wear_bucket=wear_bucket, debug=args["debug"])

        print(f"Item: {name}")
        print(f"Wear: {args.get('wear','any')}  Category: {args.get('category','any')}  Source: {snap['source']}")
        print(f"Lowest ask:  ${snap['lowest_ask']:.2f}   (id: {snap['lowest_ask_id']})")
        hb_txt = "None" if snap["highest_bid"] is None else f"${snap['highest_bid']:.2f}"
        q_txt  = "" if snap["highest_bid_qty"] is None else f"  (qty: {snap['highest_bid_qty']})"
        print(f"Highest bid: {hb_txt}{q_txt}")
        print(f"Vol 24h:     {snap['vol24h']}")
        print(f"ASP 24h:     ${snap['asp24h']:.2f}")

        # dual write: history (append) + latest (overwrite)
        log_snapshot_both(
            name=name,
            wear=args.get("wear"),
            category=args.get("category"),
            snap=snap,
    )
        print("Wrote logs →",
            "logs/csfloat_snapshots.csv (append),",
            "logs/csfloat_snapshot_latest.csv (overwrite)")
        return

if __name__ == "__main__":
    main()