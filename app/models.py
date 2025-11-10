from pydantic import BaseModel

class Listing(BaseModel):
    id: str | None = None
    market_hash_name: str
    price_usd: float             # USD (not cents)
    float_value: float | None = None
    state: str | None = None
    paint_seed: int | None = None