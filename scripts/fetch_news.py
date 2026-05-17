import requests
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

GNEWS_KEY = 'fee5ea73edbfa9379217510854ba9551'
GNEWS_BASE = 'https://gnews.io/api/v4/search'
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; NewsBot/1.0)'}

# ── helpers ────────────────────────────────────────────────
def strip(html): return re.sub(r'<[^>]+>', '', html or '').strip()

def fetch_rss(feed):
    try:
        r = requests.get(feed['url'], headers=HEADERS, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        results = []
        for item in root.findall('.//item')[:6]:
            title = strip(item.findtext('title') or '')
            title = re.sub(r'\s+-\s+[\w\s]+$', '', title).strip()
            link  = strip(item.findtext('link') or '')
            pub   = strip(item.findtext('pubDate') or '')
            desc  = strip(item.findtext('description') or '')[:120]
            if title:
                results.append({'title':title,'link':link,'publishedAt':pub,
                                'source':feed['badge'],'desc':desc,
                                'badge':feed['badge'],'color':feed['color']})
        print(f"  RSS {feed['badge']}: {len(results)}")
        return results
    except Exception as e:
        print(f"  RSS {feed['badge']} failed: {e}")
        return []

def fetch_gnews(q, badge, color, n=5):
    try:
        url = f"{GNEWS_BASE}?q={requests.utils.quote(q)}&lang=en&max={n}&apikey={GNEWS_KEY}"
        r = requests.get(url, timeout=15)
        data = r.json()
        results = []
        for a in data.get('articles', []):
            results.append({
                'title': (a.get('title') or '').split(' - ')[0].strip(),
                'link':  a.get('url','#'),
                'publishedAt': a.get('publishedAt',''),
                'source': (a.get('source') or {}).get('name',''),
                'desc':   (a.get('description') or '')[:120],
                'badge':  badge, 'color': color
            })
        print(f"  GNews '{q[:35]}': {len(results)}")
        return results
    except Exception as e:
        print(f"  GNews failed: {e}")
        return []

def dedupe(articles, limit=5):
    seen, out = set(), []
    for a in articles:
        k = a['title'][:40]
        if k not in seen:
            seen.add(k); out.append(a)
        if len(out) >= limit: break
    return out

# ── NEWS ───────────────────────────────────────────────────
HK_RSS = [
    {'url':'https://www.reuters.com/rssFeed/asiaPacificNews','badge':'REUTERS','color':'var(--down)'},
    {'url':'https://www.scmp.com/rss/2/feed','badge':'SCMP','color':'var(--gold)'},
    {'url':'https://news.rthk.hk/rthk/en/component/k2/1456754-546.htm','badge':'RTHK','color':'var(--blue)'},
    {'url':'https://www.investing.com/rss/news_301.rss','badge':'INVESTING','color':'var(--accent)'},
]

# ── EARNINGS CALENDAR (Yahoo Finance) ──────────────────────
def fetch_earnings():
    earnings = []
    try:
        today = datetime.now(timezone.utc)
        for d in range(0, 7):
            dt = today + timedelta(days=d)
            date_str = dt.strftime('%Y-%m-%d')
            url = (f'https://query1.finance.yahoo.com/v1/finance/lookup/earn?'
                   f'date={date_str}&size=20')
            r = requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=15)
            if not r.ok: continue
            data = r.json()
            rows = (data.get('finance',{}).get('result',[None])[0] or {}).get('earningsData',[])
            for row in rows:
                sym = row.get('ticker','')
                name = row.get('companyshortname', sym)
                t = row.get('startdatetimetype','--')
                eps = row.get('epsestimate')
                rev = row.get('revenueestimate')
                earnings.append({
                    'date': dt.strftime('%b %d'),
                    'ticker': sym,
                    'company': name[:22],
                    'time': 'Pre' if 'BMO' in t else 'AH' if 'AMC' in t else t,
                    'eps': f'${eps:.2f}' if eps else '--',
                    'rev': f'${rev/1e9:.1f}B' if rev else '--',
                    'impact': 'HIGH' if sym in HIGH_IMPACT else 'MED'
                })
            time.sleep(0.3)
    except Exception as e:
        print(f'  Earnings fetch error: {e}')
    print(f'  Earnings: {len(earnings)} events')
    return earnings[:20]

HIGH_IMPACT = {'AAPL','MSFT','NVDA','AMZN','META','GOOGL','TSLA','AMD','NFLX','JPM',
               'GS','BAC','WMT','HD','COST','TGT','AMAT','PANW','CRM','ORCL'}

# ── ECONOMIC CALENDAR (Investing.com RSS) ──────────────────
def fetch_eco_calendar():
    events = []
    try:
        url = 'https://www.investing.com/rss/news_285.rss'
        r = requests.get(url, headers=HEADERS, timeout=15)
        root = ET.fromstring(r.content)
        for item in root.findall('.//item')[:15]:
            title = strip(item.findtext('title') or '')
            link  = strip(item.findtext('link') or '')
            pub   = strip(item.findtext('pubDate') or '')
            desc  = strip(item.findtext('description') or '')[:100]
            if title:
                imp = 3 if any(w in title.upper() for w in ['CPI','GDP','FOMC','NFP','RATE DECISION','PAYROLL']) \
                      else 2 if any(w in title.upper() for w in ['PMI','RETAIL','INFLATION','JOBLESS','HOUSING']) \
                      else 1
                country = 'US'
                if any(w in title.upper() for w in ['CHINA','CHINESE','PBC','PBOC']): country = 'CN'
                elif any(w in title.upper() for w in ['JAPAN','BOJ','JAPAN']): country = 'JP'
                elif any(w in title.upper() for w in ['HONG KONG','HKMA']): country = 'HK'
                elif any(w in title.upper() for w in ['ECB','EURO','EU ']): country = 'EU'
                events.append({'time':pub[:16],'country':country,'event':title,'imp':imp,
                                'link':link,'desc':desc})
    except Exception as e:
        print(f'  Eco calendar error: {e}')
    print(f'  Eco events: {len(events)}')
    return events[:12]

# ── EARNINGS SURPRISES (GNews) ──────────────────────────────
def fetch_surprises():
    items = fetch_gnews('earnings beat miss surprise results today', 'EARNINGS', 'var(--warn)', 6)
    print(f'  Surprises: {len(items)}')
    return items[:5]

# ── PRE/AH MOVERS (Yahoo Finance) ──────────────────────────
def fetch_movers():
    movers = []
    try:
        for screen in ['most_actives','day_gainers','day_losers']:
            url = f'https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?formatted=false&scrIds={screen}&count=5'
            r = requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=15)
            if not r.ok: continue
            data = r.json()
            quotes = (data.get('finance',{}).get('result',[{}])[0]).get('quotes',[])
            label = 'ACTIVE' if screen=='most_actives' else 'GAINER' if screen=='day_gainers' else 'LOSER'
            color = 'var(--text-muted)' if screen=='most_actives' else 'var(--up)' if screen=='day_gainers' else 'var(--down)'
            for q in quotes[:3]:
                sym  = q.get('symbol','')
                name = q.get('shortName', sym)[:20]
                price= q.get('regularMarketPrice',0)
                chg  = q.get('regularMarketChangePercent',0)
                movers.append({
                    'symbol': sym, 'name': name,
                    'price': f'{price:.2f}',
                    'chg': f'{chg:+.2f}%',
                    'up': chg >= 0,
                    'label': label, 'color': color
                })
            time.sleep(0.3)
    except Exception as e:
        print(f'  Movers error: {e}')
    print(f'  Movers: {len(movers)}')
    return movers

# ── BUILD CACHE ─────────────────────────────────────────────
print('=== Building cache ===')
cache = {'updated': datetime.now(timezone.utc).isoformat(),
         'hk':[], 'us':[], 'earnings':[], 'eco':[], 'surprises':[], 'movers':[]}

print('News HK...')
hk = []
for feed in HK_RSS:
    hk += fetch_rss(feed); time.sleep(0.5)
if len(hk) < 3:
    hk += fetch_gnews('Hong Kong stock market Hang Seng HSI','HK MKT','var(--gold)')
cache['hk'] = dedupe(hk, 5)

print('News US...')
us = fetch_gnews('US stock market S&P 500 nasdaq','US MKT','var(--accent)')
us += fetch_gnews('Wall Street earnings stocks today','WALL ST','var(--up)')
cache['us'] = dedupe(us, 5)

print('Earnings calendar...')
cache['earnings'] = fetch_earnings()

print('Eco calendar...')
cache['eco'] = fetch_eco_calendar()

print('Earnings surprises...')
cache['surprises'] = fetch_surprises()

print('Movers...')
cache['movers'] = fetch_movers()

with open('news-cache.json','w',encoding='utf-8') as f:
    json.dump(cache, f, ensure_ascii=False, indent=2)

print(f"\n✅ Done. HK:{len(cache['hk'])} US:{len(cache['us'])} Earnings:{len(cache['earnings'])} Eco:{len(cache['eco'])} Surprises:{len(cache['surprises'])} Movers:{len(cache['movers'])}")
