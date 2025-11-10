

# CS2_Arb — CS2 Skin Arbitrage Tool

**Goal:**  
Identify cross-market opportunities by fetching for each CS2 skin (filtered by wear & type) the **current lowest ask**, **current highest bid**, and **24-hour sales metrics** (volume & ASP).  
The project is designed to later integrate with **UU** prices to calculate profit ratios.


---

## 🚀 Features

- **CSFloat snapshot per item**
  - Lowest ask (USD)
  - Highest bid (USD) + quantity at top of book
  - 24h sales volume and average selling price (ASP)
- **Wear/type filters**
  - Wear tiers: `fn`, `mw`, `ft`, `ww`, `bs`
  - Type: `normal`, `stattrak`, `souvenir`
- **Dual logging**
  - `logs/csfloat_snapshots.csv` → append mode (history)
  - `logs/csfloat_snapshot_latest.csv` → overwrite mode (latest snapshot)
- **Future-ready for UU integration**
  - Compare UU (CNY) prices vs CSFloat (USD) for arbitrage scoring

---

## 📁 Project Structure
```
CS2_Arb/
├─ app/
│  ├─ __init__.py
│  ├─ config.py
│  ├─ csfloat_client.py
│  ├─ history.py
│  ├─ wear.py
│  ├─ pricing.py
│  ├─ logger.py
│  ├─ main.py
│  ├─ quick_probe.py
│  └─ models.py
├─ .env                        
├─ pyproject.toml
├─ logs/                # auto-created for CSV outputs
└─ README.md
```
---

## 🧰 Requirements

- macOS or Linux  
- Python **3.11+**
- [CSFloat API key](https://csfloat.com)

---

## ⚙️ Setup

### 1. Create environment
```bash
conda create -n cs2arb python=3.11 -y
conda activate cs2arb
```

### 2. Install dependencies
```bash
pip install httpx python-dotenv tabulate pandas pydantic
# (optional) developer tools
pip install black ruff
```

### 3. Create .env (example below)

Create a file named .env (never commit it):
```bash
CSFLOAT_API_KEY=your_api_key_here
DEFAULT_ITEM=AK-47 | Redline (Field-Tested)

# optional tuning
CNY_USD=0.14
CSFLOAT_SELL_FEE=0.02
CSFLOAT_WITHDRAW_FEE=0.025
LOCKUP_DAYS=7
MIN_PROFIT_USD=1.0
MIN_ROI=0.02
MIN_BID_QTY=1
ANCHOR_BUFFER_PCT=0.00
```

---

## 🧩 Usage

### 1. Single snapshot
```bash
python -m app.main --snapshot "AK-47 | Redline (Field-Tested)" --wear ft --category normal
```
### 2. With debug info
```bash
python -m app.main --snapshot "AK-47 | Fire Serpent (Minimal Wear)" --wear mw --category normal --debug
```
### 3. Output example
```bash
Item: AK-47 | Fire Serpent (Minimal Wear)
Wear: mw  Category: normal  Source: strict(name+cat+wear)
Lowest ask:  $1637.32   (id: 906759820814715701)
Highest bid: $1612.00  (qty: 5)
Vol 24h:     23
ASP 24h:     $1625.87
Wrote logs → logs/csfloat_snapshots.csv (append), logs/csfloat_snapshot_latest.csv (overwrite)
```

---

## 🧾 Logging

|File |	Mode |	Purpose |
| --- | --- | --- | 
|logs/csfloat_snapshots.csv	|Append|	Keeps historical records for time-series analysis|
|logs/csfloat_snapshot_latest.csv	|Overwrite	|Contains only the most recent snapshot|

Each log row includes:
```
timestamp, item, wear, category, source, lowest_ask_usd, highest_bid_usd, highest_bid_qty, vol24h, asp24h_usd.
```
---

## 🪶 Wear tiers

|Key |	Tier	| Float range |
| --- | --- |  ---|
|fn | 	Factory New |	0.00–0.07 |
|mw	 | Minimal Wear	| 0.07–0.15 |
|ft	|Field-Tested	|0.15–0.38|
|ww	|Well-Worn|	0.38–0.45|
|bs	|Battle-Scarred	|0.45–1.00|


---


## 🧮 Config reference

|Variable |	Purpose |
| --- | --- |
|CSFLOAT_API_KEY	|required API key|
|DEFAULT_ITEM	|fallback item name|
|CNY_USD	|conversion rate|
|CSFLOAT_SELL_FEE	|fee when selling on CSFloat|
|CSFLOAT_WITHDRAW_FEE	|withdrawal fee|
|MIN_PROFIT_USD, MIN_ROI, MIN_BID_QTY	|filters|
|ANCHOR_BUFFER_PCT	|safety haircut on lowest ask|


---

## 🧭 Roadmap
	•	✅ CSFloat lowest ask / highest bid / vol24h / ASP24h
	•	🔄 Integrate UU fetcher
	•	🧮 ROI filtering & scoring dashboard
	•	📈 Time-series and alert automation

---

## 📜 License

Proprietary — all rights reserved.
For personal research and development use only.

---