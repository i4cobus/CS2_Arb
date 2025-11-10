# app/quick_probe.py
import httpx, os, json
from dotenv import load_dotenv
load_dotenv()

KEY = os.getenv("CSFLOAT_API_KEY", "").strip()
assert KEY, "Missing CSFLOAT_API_KEY in .env"

r = httpx.get(
    "https://csfloat.com/api/v1/listings",
    headers={"Authorization": KEY},   # no 'Bearer'
    params={"limit": 5, "sort_by": "most_recent"},  # no name filter
    timeout=20,
)

print("Status:", r.status_code)
print("X-Next-Cursor:", r.headers.get("X-Next-Cursor"))
try:
    data = r.json()
except Exception as e:
    print("JSON decode error:", e)
    print("Raw text (first 400):", r.text[:400])
    raise

print("Type:", type(data).__name__)
if isinstance(data, list):
    print("List length:", len(data))
    print("First item keys:", list(data[0].keys()) if data else [])
elif isinstance(data, dict):
    print("Dict keys:", list(data.keys()))
    # pretty-print a short preview
    print("Preview:", json.dumps(data, indent=2)[:600])
else:
    print("Unexpected JSON:", data)