# Asia-US Market Review 复盘大师

A daily short-term market review dashboard inspired by 复盘大师 style, covering **Hong Kong, China, Korea, Japan, and US** equity markets.

## Features

- 🌐 5-market KPI cards (HSI, CSI300, KOSPI, Nikkei, S&P500)
- 📊 Market breadth advance/decline per market
- 🔥 Sector & theme rotation grid
- 💰 Top inflow / outflow fund flow tables (North/South money)
- 📈 Chart.js bar charts: 1-week index performance & sector heatmap
- 🗺 Theme direction & position guidance table
- ⚠️ Risk alert banner
- 🌙 Dark / Light mode toggle
- 📱 Mobile responsive

## Stack

- Pure HTML / CSS / JavaScript (no build tools)
- [Chart.js 4.4](https://www.chartjs.org/) via CDN
- Google Fonts: Inter + JetBrains Mono

## Hosting (GitHub Pages)

1. Go to **Settings → Pages**
2. Source: `main` branch, `/ (root)` folder
3. Save → your site will be live at `https://michaelwong886.github.io/asia-us-market-review/`

## Data Integration Roadmap

| Market | Suggested API |
|---|---|
| HK (HSI/HSCEI) | HKEX Data API, Yahoo Finance |
| China A (CSI300/SSE) | Tushare Pro, AKShare |
| Korea (KOSPI) | KRX OpenAPI, Yahoo Finance |
| Japan (Nikkei) | JPX, Yahoo Finance |
| US (S&P500/NASDAQ) | Alpaca, Polygon.io, Yahoo Finance |

## License
MIT
