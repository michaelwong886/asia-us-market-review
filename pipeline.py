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

Weekend rule:
  If today is Saturday or Sunday (HKT), fetch_movers uses the last row
  with non-zero volume, which will be Friday's close. The output JSON
  includes is_friday_fallback=true so the dashboard can show a badge.
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


def is_weekend_hkt() -> bool:
    """Return True if current time in Hong Kong is Saturday or Sunday."""
    from zoneinfo import ZoneInfo
    hkt_now = datetime.now(ZoneInfo("Asia/Hong_Kong"))
    return hkt_now.weekday() >= 5  # 5=Saturday, 6=Sunday


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

    Weekend rule: Yahoo Finance sometimes returns a zero-volume row for
    the current weekend day. We always pick the LAST row with non-zero
    volume (= Friday close on Sat/Sun, today's close on weekdays).

    Returns:
        {
          "gainers": [...],
          "losers":  [...],
          "is_friday_fallback": bool,
          "screener_note": "..."
        }
    """
    weekend = is_weekend_hkt()
    print(f"  Downloading {len(tickers)} tickers (batch)... [weekend={weekend}]", flush=True)
    try:
        raw = yf.download(
            tickers,
            period="7d",   # extend to 7d to always capture Friday on weekends
            interval="1d",
            auto_adjust=True,
            group_by="ticker",
            threads=True,
            progress=False,
        )
    except Exception as e:
        print(f"  ERROR downloading batch: {e}")
        return {"gainers": [], "losers": [], "is_friday_fallback": weekend, "screener_note": f"error: {e}"}

    rows = []
    for tkr in tickers:
        try:
            if len(tickers) == 1:
                df = raw
            else:
                df = raw[tkr] if tkr in raw.columns.get_level_values(0) else pd.DataFrame()

            if df is None or df.empty:
                continue

            close_series  = df["Close"].dropna()
            volume_series = df["Volume"].dropna()

            if len(close_series) < 2:
                continue

            # ── WEEKEND FIX ──────────────────────────────────────────
            # On Sat/Sun Yahoo may append a partial row with Close=NaN
            # or Volume=0. Find the last row where Volume > 0 to get
            # the real last trading day (Friday).
            # On weekdays this still resolves to today's last row.
            nonzero_vol_idx = volume_series[volume_series > 0].index
            if nonzero_vol_idx.empty:
                continue

            last_idx = nonzero_vol_idx[-1]   # last date with real volume
            pos      = close_series.index.get_loc(last_idx)

            if pos < 1:
                continue  # need at least one prior row for pct_change

            close_val = float(close_series.iloc[pos])
            prev_val  = float(close_series.iloc[pos - 1])
            vol_val   = float(volume_series.loc[last_idx])
            chg       = pct_change(close_val, prev_val)
            # ─────────────────────────────────────────────────────────

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

    rows.sort(key=lambda x: x["pct_change"])
    losers  = rows[:top_n]
    gainers = list(reversed(rows[-top_n:]))

    return {
        "gainers":             gainers,
        "losers":              losers,
        "is_friday_fallback":  weekend,
        "screener_note":       f"Last trading day data{'  (Fri fallback)' if weekend else ''}",
    }


# ─────────────────────────────────────────────
# Index fetching
# ─────────────────────────────────────────────

def fetch_index_entry(market_key: str, cfg: dict) -> dict:
    entry = {
        "label":    cfg["label"],
        "flag":     cfg["flag"],
        "primary":  {},
        "secondary":{},
    }
    if "tertiary" in cfg:
        entry["tertiary"] = {}

    for role in ["primary", "secondary", "tertiary"]:
        if role not in cfg:
            continue
        sym  = cfg[role]["ticker"]
        name = cfg[role]["name"]
        q    = fetch_quote(sym)
        entry[role] = {
            "name":       name,
            "ticker":     sym,
            "close":      q.get("close"),
            "pct_change": q.get("pct_change"),
            "volume_fmt": format_volume(q.get("volume") or 0, market_key),
        }

    # Sparkline from primary ticker
    entry["sparkline"] = fetch_history_week(cfg["primary"]["ticker"])
    return entry


# ─────────────────────────────────────────────
# Sector fetching
# ─────────────────────────────────────────────

def fetch_sector_entry(name: str, cfg: dict) -> dict:
    anchor_tkr = cfg["tickers"][0]
    q = fetch_quote(anchor_tkr)
    return {
        "anchor":     anchor_tkr,
        "markets":    cfg.get("markets", ""),
        "close":      q.get("close"),
        "pct_change": q.get("pct_change"),
    }


# ─────────────────────────────────────────────
# FX fetching
# ─────────────────────────────────────────────

def fetch_fx_entry(pair: str, yf_sym: str) -> dict:
    q = fetch_quote(yf_sym)
    return {
        "rate":       q.get("close"),
        "pct_change": q.get("pct_change"),
    }


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def build_payload(verbose: bool = False) -> dict:
    now_utc = datetime.now(timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        now_hkt = datetime.now(ZoneInfo("Asia/Hong_Kong"))
        hkt_str = now_hkt.strftime("%Y-%m-%d %H:%M HKT")
    except Exception:
        hkt_str = now_utc.strftime("%Y-%m-%d %H:%MZ")

    payload = {
        "generated_at":     now_utc.isoformat(),
        "generated_at_hkt": hkt_str,
        "indices":  {},
        "sectors":  {},
        "fx":       {},
        "movers":   {},
    }

    # ── Indices
    print("[1/4] Fetching indices...", flush=True)
    for mkt, cfg in INDICES.items():
        if verbose:
            print(f"  {mkt}...", flush=True)
        payload["indices"][mkt] = fetch_index_entry(mkt, cfg)

    # ── Sectors
    print("[2/4] Fetching sectors...", flush=True)
    for name, cfg in SECTORS.items():
        payload["sectors"][name] = fetch_sector_entry(name, cfg)

    # ── FX
    print("[3/4] Fetching FX...", flush=True)
    for pair, sym in FX_PAIRS.items():
        payload["fx"][pair] = fetch_fx_entry(pair, sym)

    # ── Movers
    print("[4/4] Fetching movers...", flush=True)
    print("  HK universe...", flush=True)
    payload["movers"]["HK"] = fetch_movers(
        HK_UNIVERSE, min_volume=500_000, currency="HKD"
    )
    print("  US universe...", flush=True)
    payload["movers"]["US"] = fetch_movers(
        US_UNIVERSE, min_volume=500_000, currency="USD"
    )

    return payload


def main():
    parser = argparse.ArgumentParser(description="Asia-US Market Review pipeline")
    parser.add_argument("-o", "--output", default="data.json", help="Output file path")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    print(f"Starting pipeline → {args.output}", flush=True)
    payload = build_payload(verbose=args.verbose)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"\nDone. Written to {out_path} ({out_path.stat().st_size:,} bytes)", flush=True)
    print(f"Generated: {payload['generated_at_hkt']}", flush=True)


if __name__ == "__main__":
    main()
