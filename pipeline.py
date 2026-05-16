#!/usr/bin/env python3
"""
Asia-US Market Review — Data Pipeline
Fetches live/latest market data from Yahoo Finance and outputs data.json

Markets covered:
  🇭🇰 Hong Kong  — ^HSI, ^HSCE
  🇨🇳 China A    — 000300.SS (CSI300), 000001.SS (SSE Composite)
  🇰🇷 Korea      — ^KS11 (KOSPI), ^KQ11 (KOSDAQ)
  🇯🇵 Japan      — ^N225 (Nikkei), ^TPX (TOPIX)
  🇺🇸 US         — ^GSPC (S&P500), ^IXIC (NASDAQ), ^DJI (Dow)

Screeners:
  HK Movers — market cap >= 200B HKD, volume >= 500k
  US Movers — market cap >= 1B USD,   volume >= 500k
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

# HK large-cap universe — >=200B HKD mkt cap, liquid names
# Approx 200B HKD threshold selects HSI constituents + major H-shares
HK_UNIVERSE = [
    "0700.HK",  # Tencent
    "9988.HK",  # Alibaba
    "0941.HK",  # China Mobile
    "1299.HK",  # AIA
    "0005.HK",  # HSBC
    "0939.HK",  # CCB
    "1398.HK",  # ICBC
    "3690.HK",  # Meituan
    "0388.HK",  # HKEx
    "2318.HK",  # Ping An
    "1810.HK",  # Xiaomi
    "9618.HK",  # JD.com
    "0883.HK",  # CNOOC
    "2628.HK",  # China Life
    "1211.HK",  # BYD
    "0857.HK",  # PetroChina
    "9999.HK",  # NetEase
    "0027.HK",  # Galaxy Entertainment
    "1177.HK",  # Sino Biopharm
    "0011.HK",  # Hang Seng Bank
    "2269.HK",  # Wuxi Biologics
    "0016.HK",  # SHK Properties
    "0688.HK",  # China Overseas Land
    "0003.HK",  # HK & China Gas
    "1038.HK",  # CK Infrastructure
    "0002.HK",  # CLP Holdings
    "6098.HK",  # Country Garden Services
    "0762.HK",  # China Unicom
    "2020.HK",  # ANTA Sports
    "9961.HK",  # Trip.com
]

# US large-cap universe — >=1B USD mkt cap, S&P500 + NASDAQ100 majors
US_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B",
    "UNH", "LLY", "JPM", "V", "XOM", "MA", "AVGO", "HD", "CVX", "MRK",
    "ABBV", "COST", "PEP", "KO", "WMT", "BAC", "PFE", "TMO", "CSCO",
    "ACN", "MCD", "CRM", "ADBE", "NFLX", "ABT", "AMD", "INTC", "QCOM",
    "DHR", "TXN", "NEE", "PM", "RTX", "HON", "AMGN", "IBM", "GE",
    "SPGI", "UPS", "CAT", "BA", "GS", "MS", "BLK", "AXP", "BKNG",
    "UBER", "ABNB", "SQ", "COIN", "PLTR", "SNOW", "ARM", "SMCI",
    "MU", "LRCX", "AMAT", "KLAC", "MRVL", "ORCL", "SAP", "NOW",
    "PANW", "CRWD", "ZS", "FTNT", "TSM", "ASML", "SHOP",
]

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


def fetch_movers(tickers: list, min_volume: int, currency: str, top_n: int = 5) -> dict:
    """
    Fetch batch quotes for a universe of tickers and return
    top N gainers and top N losers filtered by min_volume.

    Returns:
        {
          "gainers": [{ticker, name, close, pct_change, volume}, ...],
          "losers":  [{ticker, name, close, pct_change, volume}, ...],
          "screener_note": "..."
        }
    """
    print(f"  Downloading {len(tickers)} tickers (batch)...", flush=True)
    try:
        raw = yf.download(
            tickers,
            period="5d",
            interval="1d",
            auto_adjust=True,
            group_by="ticker",
            threads=True,
            progress=False,
        )
    except Exception as e:
        print(f"  ERROR downloading batch: {e}")
        return {"gainers": [], "losers": [], "screener_note": f"error: {e}"}

    rows = []
    for tkr in tickers:
        try:
            if len(tickers) == 1:
                df = raw
            else:
                df = raw[tkr] if tkr in raw.columns.get_level_values(0) else pd.DataFrame()

            if df is None or df.empty or len(df) < 2:
                continue

            close_series  = df["Close"].dropna()
            volume_series = df["Volume"].dropna()

            if len(close_series) < 2:
                continue

            close_val  = float(close_series.iloc[-1])
            prev_val   = float(close_series.iloc[-2])
            vol_val    = float(volume_series.iloc[-1]) if not volume_series.empty else 0
            chg        = pct_change(close_val, prev_val)

            if chg is None:
                continue
            if vol_val < min_volume:
                continue

            # Format volume
            if currency == "HKD":
                vol_fmt = f"HK${vol_val/1e6:.0f}M" if vol_val >= 1e6 else f"{int(vol_val):,}"
            else:
                vol_fmt = f"${vol_val/1e6:.0f}M" if vol_val >= 1e6 else f"{int(vol_val):,}"

            rows.append({
                "ticker":     tkr,
                "close":      safe_round(close_val, 2),
                "pct_change": chg,
                "volume":     int(vol_val),
                "volume_fmt": vol_fmt,
            })
        except Exception:
            continue

    rows.sort(key=lambda x: x["pct_change"], reverse=True)
    gainers = rows[:top_n]
    losers  = list(reversed(rows[-top_n:])) if len(rows) >= top_n else list(reversed(rows))

    return {
        "gainers": gainers,
        "losers":  losers,
        "count_passed_screen": len(rows),
    }


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
        "movers":   {},
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

    # ── 4. HK Movers ────────────────────────────
    # Screener: mkt cap >= 200B HKD (~25B USD), vol >= 500k shares
    print("\n🇭🇰 Fetching HK movers (>=200B HKD mktcap, vol>=500k)...")
    result["movers"]["HK"] = fetch_movers(
        tickers=HK_UNIVERSE,
        min_volume=500_000,
        currency="HKD",
        top_n=5,
    )
    hk_m = result["movers"]["HK"]
    print(f"  Passed screen: {hk_m.get('count_passed_screen', 0)} tickers")
    print(f"  Top gainer: {hk_m['gainers'][0]['ticker']} {hk_m['gainers'][0]['pct_change']:+.2f}%" if hk_m.get('gainers') else "  No gainers")

    # ── 5. US Movers ────────────────────────────
    # Screener: mkt cap >= 1B USD, vol >= 500k shares
    print("\n🇺🇸 Fetching US movers (>=1B USD mktcap, vol>=500k)...")
    result["movers"]["US"] = fetch_movers(
        tickers=US_UNIVERSE,
        min_volume=500_000,
        currency="USD",
        top_n=5,
    )
    us_m = result["movers"]["US"]
    print(f"  Passed screen: {us_m.get('count_passed_screen', 0)} tickers")
    print(f"  Top gainer: {us_m['gainers'][0]['ticker']} {us_m['gainers'][0]['pct_change']:+.2f}%" if us_m.get('gainers') else "  No gainers")

    # ── 6. Save output ───────────────────────────
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
