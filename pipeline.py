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

News:
  Fetches up to 10 headlines each from Yahoo Finance RSS feeds for:
    - Global markets news (finance.yahoo.com/rss/2.0/headline?s=^GSPC)
    - Asia markets tag feed
    - HK/CN-specific feeds via HKEX + ^HSI query
  Stored in data.json under data.news = [{title, url, source, published_hkt}, ...]
"""

import json
import argparse
import sys
import re
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

# News RSS sources — Yahoo Finance headline feeds (public, no auth)
NEWS_SOURCES = [
    {
        "label": "US Markets",
        "url": "https://finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US",
        "max": 8,
    },
    {
        "label": "Asia Markets",
        "url": "https://finance.yahoo.com/rss/2.0/headline?s=%5EHSI&region=HK&lang=en-US",
        "max": 8,
    },
    {
        "label": "China Tech",
        "url": "https://finance.yahoo.com/rss/2.0/headline?s=9988.HK&region=HK&lang=en-US",
        "max": 6,
    },
    {
        "label": "Semiconductors",
        "url": "https://finance.yahoo.com/rss/2.0/headline?s=NVDA&region=US&lang=en-US",
        "max": 6,
    },
]

# HK large-cap universe
HK_UNIVERSE = [
    "0700.HK", "9988.HK", "0941.HK", "1299.HK", "0005.HK",
    "0939.HK", "1398.HK", "3690.HK", "0388.HK", "2318.HK",
    "1810.HK", "9618.HK", "0883.HK", "2628.HK", "1211.HK",
    "0857.HK", "9999.HK", "0027.HK", "1177.HK", "0011.HK",
    "2269.HK", "0016.HK", "0688.HK", "0003.HK", "1038.HK",
    "0002.HK", "6098.HK", "0762.HK", "2020.HK", "9961.HK",
]

# US large-cap universe
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

_META_CACHE: dict = {}

def fetch_ticker_meta(tkr: str) -> dict:
    if tkr in _META_CACHE:
        return _META_CACHE[tkr]
    try:
        info = yf.Ticker(tkr).info
        meta = {
            "longName": info.get("longName") or info.get("shortName") or tkr,
            "industry": info.get("industry") or info.get("sector") or "",
        }
    except Exception:
        meta = {"longName": tkr, "industry": ""}
    _META_CACHE[tkr] = meta
    return meta


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
    from zoneinfo import ZoneInfo
    hkt_now = datetime.now(ZoneInfo("Asia/Hong_Kong"))
    return hkt_now.weekday() >= 5


def fetch_quote(ticker_sym: str) -> dict:
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
    weekend = is_weekend_hkt()
    print(f"  Downloading {len(tickers)} tickers (batch)... [weekend={weekend}]", flush=True)
    try:
        raw = yf.download(
            tickers,
            period="7d",
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

            nonzero_vol_idx = volume_series[volume_series > 0].index
            if nonzero_vol_idx.empty:
                continue

            last_idx = nonzero_vol_idx[-1]
            pos      = close_series.index.get_loc(last_idx)

            if pos < 1:
                continue

            close_val = float(close_series.iloc[pos])
            prev_val  = float(close_series.iloc[pos - 1])
            vol_val   = float(volume_series.loc[last_idx])
            chg       = pct_change(close_val, prev_val)

            if chg is None:
                continue
            if vol_val < min_volume:
                continue

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

    print(f"  Enriching {len(gainers)+len(losers)} movers with name/industry...", flush=True)
    for row in gainers + losers:
        meta = fetch_ticker_meta(row["ticker"])
        row["longName"] = meta["longName"]
        row["industry"] = meta["industry"]

    return {
        "gainers":             gainers,
        "losers":              losers,
        "is_friday_fallback":  weekend,
        "screener_note":       f"Last trading day data{'  (Fri fallback)' if weekend else ''}",
    }


# ─────────────────────────────────────────────
# News fetcher
# ─────────────────────────────────────────────

def parse_rss_date(date_str: str) -> str:
    """Parse RFC 2822 date from RSS and convert to HKT string."""
    try:
        from email.utils import parsedate_to_datetime
        from zoneinfo import ZoneInfo
        dt = parsedate_to_datetime(date_str)
        hkt = dt.astimezone(ZoneInfo("Asia/Hong_Kong"))
        return hkt.strftime("%Y-%m-%d %H:%M HKT")
    except Exception:
        return date_str or ""


def fetch_news() -> list:
    """
    Fetch market news headlines from Yahoo Finance RSS feeds.
    Returns a deduplicated list of dicts:
      {title, url, source, published_hkt, label}
    sorted newest-first, max 30 total.
    """
    import urllib.request
    import xml.etree.ElementTree as ET

    seen_urls = set()
    all_items = []

    for src in NEWS_SOURCES:
        try:
            print(f"  Fetching news: {src['label']}...", flush=True)
            req = urllib.request.Request(
                src["url"],
                headers={"User-Agent": "Mozilla/5.0 (compatible; MarketBot/1.0)"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                xml_bytes = resp.read()

            root = ET.fromstring(xml_bytes)
            channel = root.find("channel")
            if channel is None:
                continue

            count = 0
            for item in channel.findall("item"):
                if count >= src["max"]:
                    break

                title = (item.findtext("title") or "").strip()
                link  = (item.findtext("link")  or "").strip()
                pub   = (item.findtext("pubDate") or "").strip()

                # Try <source> tag first, fallback to channel title
                src_el = item.find("source")
                source_name = ""
                if src_el is not None and src_el.text:
                    source_name = src_el.text.strip()
                if not source_name:
                    ch_title = channel.findtext("title") or ""
                    # Strip "Yahoo Finance" prefix if present
                    source_name = re.sub(r"^Yahoo Finance\s*[-–:]?\s*", "", ch_title).strip() or "Yahoo Finance"

                if not title or not link:
                    continue
                if link in seen_urls:
                    continue

                seen_urls.add(link)
                all_items.append({
                    "title":         title,
                    "url":           link,
                    "source":        source_name,
                    "published_hkt": parse_rss_date(pub),
                    "label":         src["label"],
                    "_pub_raw":      pub,
                })
                count += 1

        except Exception as e:
            print(f"  WARNING: news fetch failed for {src['label']}: {e}", flush=True)
            continue

    # Sort newest-first by parsed date, fallback to insertion order
    def sort_key(item):
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(item["_pub_raw"]).timestamp()
        except Exception:
            return 0

    all_items.sort(key=sort_key, reverse=True)

    # Remove internal sort key before saving
    for item in all_items:
        item.pop("_pub_raw", None)

    return all_items[:30]


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

    entry["sparkline"] = fetch_history_week(cfg["primary"]["ticker"])
    return entry


def fetch_sector_entry(name: str, cfg: dict) -> dict:
    anchor_tkr = cfg["tickers"][0]
    q = fetch_quote(anchor_tkr)
    return {
        "anchor":     anchor_tkr,
        "markets":    cfg.get("markets", ""),
        "close":      q.get("close"),
        "pct_change": q.get("pct_change"),
    }


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
        "news":     [],
    }

    print("[1/5] Fetching indices...", flush=True)
    for mkt, cfg in INDICES.items():
        if verbose:
            print(f"  {mkt}...", flush=True)
        payload["indices"][mkt] = fetch_index_entry(mkt, cfg)

    print("[2/5] Fetching sectors...", flush=True)
    for name, cfg in SECTORS.items():
        payload["sectors"][name] = fetch_sector_entry(name, cfg)

    print("[3/5] Fetching FX...", flush=True)
    for pair, sym in FX_PAIRS.items():
        payload["fx"][pair] = fetch_fx_entry(pair, sym)

    print("[4/5] Fetching movers...", flush=True)
    print("  HK universe...", flush=True)
    payload["movers"]["HK"] = fetch_movers(
        HK_UNIVERSE, min_volume=500_000, currency="HKD"
    )
    print("  US universe...", flush=True)
    payload["movers"]["US"] = fetch_movers(
        US_UNIVERSE, min_volume=500_000, currency="USD"
    )

    print("[5/5] Fetching news...", flush=True)
    payload["news"] = fetch_news()
    print(f"  {len(payload['news'])} headlines collected.", flush=True)

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
