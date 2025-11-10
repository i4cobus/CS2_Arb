import os
from dotenv import load_dotenv

load_dotenv()

CFG = {
    "CSFLOAT_API_KEY": os.getenv("CSFLOAT_API_KEY", "").strip(),
    "DEFAULT_ITEM": os.getenv("DEFAULT_ITEM", "AK-47 | Redline (Field-Tested)").strip(),
    # optional buffer for future use; not used in snapshot mode
    "ANCHOR_BUFFER_PCT": float(os.getenv("ANCHOR_BUFFER_PCT", "0.00")),
}

def require_config() -> None:
    if not CFG["CSFLOAT_API_KEY"]:
        raise RuntimeError(
            "Missing CSFLOAT_API_KEY in .env\n"
            "Example:\nCSFLOAT_API_KEY=your_api_key_here\n"
            "DEFAULT_ITEM=AK-47 | Redline (Field-Tested)"
        )