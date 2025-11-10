from statistics import median
from typing import List

def base_price_from_depth(prices_usd: List[float], method: str = "median", trim: float = 0.1) -> float:
    if not prices_usd:
        return 0.0
    xs = sorted(prices_usd)
    if method == "median":
        return float(median(xs))
    if method == "trimmed_mean":
        k = int(len(xs) * trim)
        core = xs[k: len(xs)-k] if len(xs) > 2*k else xs
        return float(sum(core) / len(core))
    return xs[0]