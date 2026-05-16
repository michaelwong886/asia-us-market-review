#!/usr/bin/env python3
"""
Asia-US Market Review — Data Pipeline
Fetches live/latest market data from Yahoo Finance and outputs data.json
for the market-review.html dashboard.

Markets covered:
  🇭🇰 Hong Kong  — ^HSI, ^HSCE
  🇨🇳 China A    — 000300.SS (CSI300), 000001.SS (SSE Composite)
  🇰🇷 Korea      — ^KS11 (KOSPI), ^KQ11 (KOSDAQ)
  🇯🇵 Japan      — ^N225 (Nikkei), ^TPX (TOPIX)
  🇺🇸 US         — ^GSPC (S&P500), ^IXIC (NASDAQ), ^DJI (Dow)

Sector ETFs (Yahoo Finance proxies):
  AI/Chips, EV/Battery, CN Tech, Robotics, Biotech, Energy, Financials

Usage:
  pip install yfinance pandas python-dotenv
  python pipeline.py
  python pipeline.py --output ./data.json
  python pipeline.py --pretty  (human-readable JSON)
"""

import json
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    print("ERROR: Missing dependencies. Run:")
    print("  pip install yfinance pandas")
    sys.exit(1)

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

INDICES = {
    "HK": {
        "label": "Hong Kong",
        "flag": "🇭🇰",
        "primary":   {"ticker": "^HSI",      "name": "HSI"},
        "secondary": {"ticker": "^HSCE",     "name": "HSCEI"},
    },
    "CN": {
        "label": "China A",
        "flag": "🇨🇳",
        "primary":   {"ticker": "000300.SS", "name": "CSI 300"},
        "secondary": {"ticker": "000001.SS", "name": "SSE Composite"},
    },
    "KR": {
        "label": "Korea",
        "flag": "🇰🇷",
        "primary":   {"ticker": "^KS11",     "name": "KOSPI"},
        "secondary": {"ticker": "^KQ11",     "name": "KOSDAQ"},
    },
    "JP": {
        "label": "Japan",
        "flag": "🇯🇵",
        "primary":   {"ticker": "^N225",     "name": "Nikkei 225"},
        "secondary": {"ticker": "^TPX",      "name": "TOPIX"},
    },
    "US": {
        "label": "US",
        "flag": "🇺🇸",
        "primary":   {"ticker": "^GSPC",     "name": "S&P 500"},
        "secondary": {"ticker": "^IXIC",     "name": "NASDAQ"},
        "tertiary":  {"ticker": "^DJI",      "name": "Dow Jones"},
    },
}

SECTORS = {
    "AI / Chips":    {"tickers": ["SOXX", "NVDA", "TSM", "AMD"],      "markets": "US/HK/KR"},
    "CN Internet":   {"tickers": ["KWEB", "9988.HK", "0700.HK"],      "markets": "HK/CN"},
    "EV / Battery":  {"tickers": ["LIT",  "002594.SZ", "NIO"],         "markets": "CN/US"},
    "Robotics":      {"tickers": ["ROBO", "6954.T",   "300024.SZ"],   "markets": "JP/CN"},
    "Clean Energy":  {"tickers": ["ICLN", "ENPH",     "600941.SS"],   "markets": "US/CN"},
    "Biotech":       {"tickers": ["XBI",  "2269.HK",  "068270.KS"],   "markets": "US/HK/KR"},
    "Financials":    {"tickers": ["XLF",  "0005.HK",  "105560.KS"],   "markets": "US/HK/KR"},
    "Defence":       {"tickers": ["ITA",  "LMT",      "047050.KS"],   "markets": "US/KR"},
}

FX_PAIRS = {
    "USD/HKD": "HKD=X",
    "USD/CNY": "CNY=X",
    "USD/KRW": "KRW=X",
    "USD/JPY": "JPY=X",
    "EUR/USD": "EURUSD=X",
    "DXY":     "DX-Y.NYB",
}

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def safe_round(val, decimals=2):
    try:
        return round(float(val), decimals)
    except (TypeError, ValueError):
        return None


def pct_change(current, previous):
    try:
        return safe_round((current - previous) / previous * 100)
    except (TypeError, ZeroDivisionError):
        return None


def fetch_quote(ticker_sym: str) -> dict:
    """Fetch latest quote for a single ticker."""
    try:
        t = yf.Ticker(ticker_sym)
        info = t.fast_info
        hist = t.history(period="5d", interval="1d", auto_adjust=True)

        if hist.empty:
            return {"ticker": ticker_sym, "error": "no_data"}

        close      = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else None
        volume     = float(hist["Volume"].iloc[-1]) if "Volume" in hist.columns else None
        chg        = pct_change(close, prev_close) if prev_close else None

        return {
            "ticker":     ticker_sym,
            "close":      safe_round(close, 2),
            "prev_close": safe_round(prev_close, 2),
            "pct_change": chg,
            "volume":     int(volume) if volume else None,
            "52w_high":   safe_round(getattr(info, "year_high", None)),
            "52w_low":    safe_round(getattr(info, "year_low", None)),
        }
    except Exception as e:
        return {"ticker": ticker_sym, "error": str(e)}


def fetch_history_week(ticker_sym: str) -> list:
    """Return list of 5 daily closes for sparkline."""
    try:
        hist = yf.Ticker(ticker_sym).history(period="5d", interval="1d", auto_adjust=True)
        return [safe_round(v) for v in hist["Close"].tolist()]
    except Exception:
        return []


def format_volume(vol: int, market: str) -> str:
    """Format volume with appropriate currency/unit."""
    currency_map = {
        "HK": ("HK$", "B", 1e9),
        "CN": ("¥",   "T", 1e12),
        "KR": ("₩",   "T", 1e12),
        "JP": ("¥",   "T", 1e12),
        "US": ("$",   "B", 1e9),
    }
    sym, unit, divisor = currency_map.get(market, ("", "B", 1e9))
    try:
        val = vol / divisor
        return f"{sym}{val:.1f}{unit}"
    except Exception:
        return "—"


# ─────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────

def run_pipeline(output_path: str = "data.json", pretty: bool = False) -> dict:
    print("\n🚀 Asia-US Market Review — Data Pipeline")
    print("=" * 50)

    result = {
        "generated_at":     datetime.now(timezone.utc).isoformat(),
        "generated_at_hkt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M HKT"),
        "indices":  {},
        "sectors":  {},
        "fx":       {},
        "breadth":  {},
        "errors":   [],
    }

    # ── 1. Indices ──────────────────────────────
    print("\n📊 Fetching indices...")
    for mkt_code, mkt in INDICES.items():
        print(f"  {mkt['flag']} {mkt['label']}...", end=" ", flush=True)
        entry = {
            "label":     mkt["label"],
            "flag":      mkt["flag"],
            "primary":   None,
            "secondary": None,
        }
        for slot in ["primary", "secondary", "tertiary"]:
            cfg = mkt.get(slot)
            if not cfg:
                continue
            data = fetch_quote(cfg["ticker"])
            data["name"] = cfg["name"]
            entry[slot] = data

        entry["sparkline"] = fetch_history_week(mkt["primary"]["ticker"])

        if entry.get("primary") and entry["primary"].get("volume"):
            entry["primary"]["volume_fmt"] = format_volume(
                entry["primary"]["volume"], mkt_code
            )

        result["indices"][mkt_code] = entry
        close = entry["primary"].get("close") if entry.get("primary") else "?"
        chg   = entry["primary"].get("pct_change") if entry.get("primary") else None
        chg_str = (f"+{chg}%" if (chg or 0) >= 0 else f"{chg}%") if chg is not None else "N/A"
        print(f"{close:,.0f}  {chg_str}" if isinstance(close, (int, float)) else "ERROR")

    # ── 2. Sectors ──────────────────────────────
    print("\n🏭 Fetching sector ETFs...")
    for sector_name, cfg in SECTORS.items():
        print(f"  {sector_name}...", end=" ", flush=True)
        anchor = cfg["tickers"][0]
        data   = fetch_quote(anchor)
        result["sectors"][sector_name] = {
            "markets":    cfg["markets"],
            "anchor":     anchor,
            "pct_change": data.get("pct_change"),
            "close":      data.get("close"),
            "error":      data.get("error"),
        }
        chg = data.get("pct_change")
        print(f"{chg:+.2f}%" if chg is not None else "ERROR")

    # ── 3. FX pairs ─────────────────────────────
    print("\n💱 Fetching FX rates...")
    for pair_name, ticker_sym in FX_PAIRS.items():
        print(f"  {pair_name}...", end=" ", flush=True)
        data = fetch_quote(ticker_sym)
        result["fx"][pair_name] = {
            "rate":       data.get("close"),
            "pct_change": data.get("pct_change"),
            "error":      data.get("error"),
        }
        print(f"{data.get('close')}" if data.get("close") else "ERROR")

    # ── 4. Save output ───────────────────────────
    indent = 2 if pretty else None
    out    = json.dumps(result, ensure_ascii=False, indent=indent)
    Path(output_path).write_text(out, encoding="utf-8")
    print(f"\n✅ Saved → {output_path}  ({len(out):,} bytes)")
    print(f"   Timestamp: {result['generated_at']}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch Asia-US market data and write data.json"
    )
    parser.add_argument("--output", "-o", default="data.json",
                        help="Output file path (default: data.json)")
    parser.add_argument("--pretty", "-p", action="store_true",
                        help="Pretty-print JSON with indentation")
    args = parser.parse_args()
    run_pipeline(output_path=args.output, pretty=args.pretty)
