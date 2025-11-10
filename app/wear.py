from typing import Tuple, Literal, Dict

WearKey = Literal["fn", "mw", "ft", "ww", "bs"]

WEAR_RANGES: Dict[WearKey, Tuple[float, float]] = {
    "fn": (0.00, 0.07),
    "mw": (0.07, 0.15),
    "ft": (0.15, 0.38),
    "ww": (0.38, 0.45),
    "bs": (0.45, 1.00),
}

def wear_bucket_range(key: WearKey) -> tuple[float, float]:
    return WEAR_RANGES[key]