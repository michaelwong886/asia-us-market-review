# Data Pipeline

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Fetch data once (writes data.json)
python pipeline.py --pretty

# 3. Run on a schedule (auto-refresh every 15 min during market hours)
python scheduler.py
```

## Output: data.json structure

```json
{
  "generated_at": "2026-05-17T...",
  "indices": {
    "HK": {
      "label": "Hong Kong", "flag": "🇭🇰",
      "primary":   { "ticker": "^HSI", "close": 23847, "pct_change": 1.18, "volume": 142000000000 },
      "secondary": { "ticker": "^HSCE", "close": 8420, "pct_change": 1.05 },
      "sparkline": [23200, 23450, 23600, 23700, 23847]
    },
    "CN": {},
    "KR": {},
    "JP": {},
    "US": {}
  },
  "sectors": {
    "AI / Chips": { "markets": "US/HK/KR", "anchor": "SOXX", "pct_change": 2.4, "close": 248.5 }
  },
  "fx": {
    "USD/HKD": { "rate": 7.785, "pct_change": 0.01 },
    "USD/JPY": { "rate": 155.4, "pct_change": -0.3 }
  }
}
```

## Connecting to the HTML Dashboard

In `market-review.html`, add this JS snippet to load live data:

```javascript
async function loadData() {
  const res = await fetch('./data.json');
  const d = await res.json();

  for (const [mkt, info] of Object.entries(d.indices)) {
    const card = document.querySelector(`[data-market="${mkt}"]`);
    if (!card) continue;
    card.querySelector('.kpi-value').textContent =
      info.primary.close?.toLocaleString() ?? '—';
    const chg = info.primary.pct_change ?? 0;
    const el = card.querySelector('.kpi-change');
    el.textContent = (chg >= 0 ? '+' : '') + chg.toFixed(2) + '%';
    el.className = 'kpi-change ' + (chg >= 0 ? 'up' : 'down');
    if (info.primary.volume_fmt)
      card.querySelector('.kpi-vol').textContent = 'Vol: ' + info.primary.volume_fmt;
  }

  document.getElementById('lastUpdate').textContent = d.generated_at_hkt;
}

loadData();
setInterval(loadData, 5 * 60 * 1000);  // re-fetch every 5 min
```

## Deployment Options

| Option | Cost | How |
|---|---|---|
| **GitHub Actions** | Free | See `.github/workflows/fetch-data.yml` |
| **Railway.app** | Free tier | `python scheduler.py` as start command |
| **Local cron** | Free | `*/15 9-16 * * 1-5 cd /path && python pipeline.py` |
| **Render.com** | Free tier | Background worker with scheduler.py |

## Data Limitations

- **Yahoo Finance** does not provide real A-share tick data — CSI300/SSE may have 15-min delay
- Market breadth (advance/decline) requires **HKEX API** or **Tushare Pro**
- Northbound 北向资金 flow requires **Tushare Pro** token (free tier at tushare.pro)
