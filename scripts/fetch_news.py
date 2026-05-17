import requests
import json
import time
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser

GNEWS_KEY = 'fee5ea73edbfa9379217510854ba9551'
GNEWS_BASE = 'https://gnews.io/api/v4/search'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36'}

# ── Helpers ────────────────────────────────────────────────────────────────
def strip_html(s):
    return re.sub(r'<[^>]+>', '', s or '').strip()

def safe_get(url, **kwargs):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, **kwargs)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f'  GET failed {url[:60]}: {e}')
        return None

def dedupe(articles, limit=5):
    seen, out = set(), []
    for a in articles:
        key = (a.get('title') or '')[:40]
        if key not in seen:
            seen.add(key)
            out.append(a)
        if len(out) >= limit:
            break
    return out

# ── News: HK RSS ────────────────────────────────────────────────────────────
HK_RSS_FEEDS = [
    {'url': 'https://www.reuters.com/rssFeed/asiaPacificNews', 'badge': 'REUTERS', 'color': 'var(--down)'},
    {'url': 'https://www.scmp.com/rss/2/feed', 'badge': 'SCMP', 'color': 'var(--gold)'},
    {'url': 'https://news.rthk.hk/rthk/en/component/k2/1456754-546.htm', 'badge': 'RTHK', 'color': 'var(--blue)'},
    {'url': 'https://www.investing.com/rss/news_301.rss', 'badge': 'INVESTING', 'color': 'var(--accent)'},
]

GNEWS_QUERIES = {
    'hk': [{'q': 'Hong Kong stock market Hang Seng HSI', 'badge': 'HK MKT', 'color': 'var(--gold)'}],
    'us': [
        {'q': 'US stock market S&P 500 nasdaq', 'badge': 'US MKT', 'color': 'var(--accent)'},
        {'q': 'Wall Street earnings stocks today', 'badge': 'WALL ST', 'color': 'var(--up)'},
    ],
}

def fetch_rss(feed):
    r = safe_get(feed['url'])
    if not r: return []
    try:
        root = ET.fromstring(r.content)
        results = []
        for item in root.findall('.//item')[:6]:
            title = strip_html(item.findtext('title') or '')
            title = re.sub(r'\s+-\s+[\w\s]+$', '', title).strip()
            link  = (item.findtext('link') or '').strip()
            pub   = (item.findtext('pubDate') or '').strip()
            desc  = strip_html(item.findtext('description') or '')[:120]
            if title:
                results.append({'title': title, 'link': link, 'publishedAt': pub,
                                'source': feed['badge'], 'desc': desc,
                                'badge': feed['badge'], 'color': feed['color']})
        print(f"  RSS {feed['badge']}: {len(results)}")
        return results
    except Exception as e:
        print(f"  RSS parse error {feed['badge']}: {e}")
        return []

def fetch_gnews(query):
    url = f"{GNEWS_BASE}?q={requests.utils.quote(query['q'])}&lang=en&max=5&apikey={GNEWS_KEY}"
    r = safe_get(url)
    if not r: return []
    try:
        data = r.json()
        results = []
        for a in data.get('articles', []):
            results.append({
                'title': (a.get('title') or '').split(' - ')[0].strip(),
                'link': a.get('url', '#'),
                'publishedAt': a.get('publishedAt', ''),
                'source': (a.get('source') or {}).get('name', ''),
                'desc': (a.get('description') or '')[:120],
                'badge': query['badge'], 'color': query['color'],
            })
        print(f"  GNews '{query['q'][:30]}': {len(results)}")
        return results
    except Exception as e:
        print(f"  GNews error: {e}")
        return []

# ── Earnings Calendar (Yahoo Finance) ───────────────────────────────────────
def fetch_earnings():
    print('Fetching earnings calendar...')
    results = []
    try:
        # Yahoo Finance earnings calendar
        url = 'https://finance.yahoo.com/calendar/earnings'
        r = safe_get(url)
        if not r:
            return fetch_earnings_gnews()
        # Parse JSON embedded in page
        match = re.search(r'"earnings":\{"rows":(\[.*?\])', r.text)
        if not match:
            # Try alternate scrape via Yahoo Finance API
            return fetch_earnings_api()
        rows = json.loads(match.group(1))
        for row in rows[:20]:
            ticker  = row.get('ticker') or row.get('symbol', '')
            company = row.get('companyshortName') or row.get('companyName', '')
            date    = row.get('startdatetime') or row.get('startDateTime', '')
            time_s  = 'Pre' if 'T' in date and int(date[11:13]) < 12 else 'AH'
            eps_est = row.get('epsestimate')
            rev_est = row.get('revenueestimate')
            results.append({
                'ticker':  ticker,
                'company': company,
                'date':    date[:10] if date else '',
                'time':    time_s,
                'epsEst':  f'${eps_est:.2f}' if eps_est else '--',
                'revEst':  format_large(rev_est) if rev_est else '--',
                'impact':  'HIGH' if ticker in HIGH_IMPACT else 'MED',
            })
        print(f'  Earnings: {len(results)} events')
        return results[:10]
    except Exception as e:
        print(f'  Earnings parse error: {e}')
        return fetch_earnings_api()

HIGH_IMPACT = {'NVDA','AAPL','MSFT','AMZN','META','GOOGL','TSLA','AMD','NFLX',
               'BABA','TSM','WMT','HD','JPM','BAC','GS','MS','V','MA'}

def format_large(n):
    try:
        n = float(n)
        if n >= 1e9: return f'${n/1e9:.1f}B'
        if n >= 1e6: return f'${n/1e6:.1f}M'
        return f'${n:.0f}'
    except: return '--'

def fetch_earnings_api():
    """Yahoo Finance v1 earnings API fallback."""
    try:
        now = datetime.now(timezone.utc)
        start = int(now.timestamp())
        end   = int((now + timedelta(days=7)).timestamp())
        url = (f'https://query1.finance.yahoo.com/v1/finance/trending/US'
               f'?count=20&start={start}&end={end}')
        # Try the calendar endpoint
        url2 = 'https://query2.finance.yahoo.com/v1/finance/earningsCalendar?startDate='
        url2 += now.strftime('%Y-%m-%d') + '&endDate=' + (now + timedelta(days=7)).strftime('%Y-%m-%d')
        r = safe_get(url2)
        if not r: return fetch_earnings_gnews()
        data = r.json()
        events = (data.get('earningsCalendar') or {}).get('earnings') or []
        results = []
        for e in events[:10]:
            ticker = e.get('ticker', '')
            date   = e.get('startdatetime', '')[:10]
            eps    = e.get('epsestimate')
            rev    = e.get('revenueestimate')
            call   = e.get('startdatetime', '')
            time_s = 'Pre' if 'T' in call and int(call[11:13]) < 12 else 'AH'
            results.append({
                'ticker':  ticker,
                'company': e.get('companyshortName', ticker),
                'date':    date,
                'time':    time_s,
                'epsEst':  f'${eps:.2f}' if eps else '--',
                'revEst':  format_large(rev) if rev else '--',
                'impact':  'HIGH' if ticker in HIGH_IMPACT else 'MED',
            })
        print(f'  Earnings API: {len(results)}')
        return results
    except Exception as e:
        print(f'  Earnings API error: {e}')
        return fetch_earnings_gnews()

def fetch_earnings_gnews():
    """Last resort: pull earnings mentions from GNews."""
    print('  Earnings fallback: GNews')
    r = safe_get(f"{GNEWS_BASE}?q=earnings+results+beats+estimates&lang=en&max=5&apikey={GNEWS_KEY}")
    if not r: return []
    results = []
    for a in r.json().get('articles', []):
        results.append({
            'ticker': '', 'company': (a.get('title') or '').split(' - ')[0][:40],
            'date': (a.get('publishedAt') or '')[:10], 'time': '--',
            'epsEst': '--', 'revEst': '--', 'impact': 'MED',
            'link': a.get('url', '#'),
        })
    return results

# ── Economic Calendar (Investing.com scrape) ─────────────────────────────────
def fetch_eco_calendar():
    print('Fetching economic calendar...')
    try:
        url = 'https://www.investing.com/economic-calendar/'
        r = safe_get(url, headers={**HEADERS, 'X-Requested-With': 'XMLHttpRequest'})
        if not r: return fetch_eco_gnews()
        # Try to extract JSON data
        match = re.search(r'calendarTableBody.*?<tr[^>]*data-event-datetime="([^"]+)"', r.text, re.DOTALL)
        # Parse table rows
        rows = re.findall(
            r'<tr[^>]*data-event-datetime="([^"]+)"[^>]*>.*?<td[^>]*class="[^"]*time[^"]*"[^>]*>([^<]*)</td>.*?<td[^>]*class="[^"]*flagCur[^"]*"[^>]*>.*?<span[^>]*title="([^"]+)".*?<td[^>]*class="[^"]*event[^"]*"[^>]*>.*?<a[^>]*>([^<]+)</a>.*?<td[^>]*class="[^"]*act[^"]*"[^>]*>([^<]*)</td>.*?<td[^>]*class="[^"]*fore[^"]*"[^>]*>([^<]*)</td>.*?<td[^>]*class="[^"]*prev[^"]*"[^>]*>([^<]*)</td>',
            r.text, re.DOTALL
        )
        events = []
        for row in rows[:8]:
            events.append({
                'datetime': row[0], 'time': row[1].strip(),
                'country': row[2].strip()[:2].upper(),
                'event': strip_html(row[3]).strip(),
                'actual': strip_html(row[4]).strip(),
                'forecast': strip_html(row[5]).strip(),
                'previous': strip_html(row[6]).strip(),
                'impact': 3,
            })
        if events:
            print(f'  Eco calendar: {len(events)}')
            return events
        return fetch_eco_gnews()
    except Exception as e:
        print(f'  Eco calendar error: {e}')
        return fetch_eco_gnews()

def fetch_eco_gnews():
    print('  Eco fallback: GNews')
    try:
        r = safe_get(f"{GNEWS_BASE}?q=Federal+Reserve+CPI+GDP+economic+data&lang=en&max=5&apikey={GNEWS_KEY}")
        if not r: return []
        events = []
        for a in r.json().get('articles', []):
            events.append({
                'time': (a.get('publishedAt') or '')[11:16] + ' ET',
                'country': 'US',
                'event': (a.get('title') or '').split(' - ')[0][:60],
                'actual': '--', 'forecast': '--', 'previous': '--',
                'impact': 2,
                'link': a.get('url', '#'),
            })
        return events
    except: return []

# ── Pre-Market / After-Hours Movers (Yahoo Finance) ──────────────────────────
def fetch_movers():
    print('Fetching pre/AH movers...')
    movers = {'pre': [], 'ah': []}
    try:
        now_et = datetime.now(timezone(timedelta(hours=-4)))  # ET
        hour_et = now_et.hour
        # During pre-market (4-9:30 ET) or after-hours (16-20 ET)
        # Use Yahoo Finance screener for gainers/losers
        for screen_type in ['gainers', 'losers']:
            url = f'https://finance.yahoo.com/screener/predefined/{screen_type}?offset=0&count=5'
            r = safe_get(url)
            if not r: continue
            # Extract quotes from embedded JSON
            match = re.search(r'"quotes":\[(.*?)\]', r.text, re.DOTALL)
            if not match: continue
            try:
                quotes_str = '[' + match.group(1) + ']'
                quotes = json.loads(quotes_str)
                for q in quotes[:3]:
                    sym = q.get('symbol', '')
                    price = q.get('regularMarketPrice') or q.get('preMarketPrice') or 0
                    chg   = q.get('regularMarketChangePercent') or q.get('preMarketChangePercent') or 0
                    name  = q.get('shortName') or q.get('longName') or sym
                    is_pre = hour_et < 10
                    entry = {
                        'ticker': sym, 'name': name[:25],
                        'price': round(float(price), 2),
                        'changePct': round(float(chg), 2),
                        'type': screen_type,
                        'session': 'pre' if is_pre else 'ah',
                    }
                    key = 'pre' if is_pre else 'ah'
                    movers[key].append(entry)
            except: continue
        # Also try Yahoo Finance pre-market movers directly
        r2 = safe_get('https://finance.yahoo.com/markets/stocks/most-active/')
        if r2:
            match2 = re.search(r'"finance":\{.*?"result":\[(.*?)\]', r2.text, re.DOTALL)
        print(f"  Movers - Pre: {len(movers['pre'])}, AH: {len(movers['ah'])}")
    except Exception as e:
        print(f'  Movers error: {e}')
    return movers

# ── Build full cache ─────────────────────────────────────────────────────────
print('=' * 55)
print('News & Catalyst Cache Builder')
print('=' * 55)

cache = {
    'updated': datetime.now(timezone.utc).isoformat(),
    'hk': [], 'us': [],
    'earnings': [], 'eco': [],
    'movers': {'pre': [], 'ah': []},
}

# News
print('\n[1/4] HK News...')
hk_articles = []
for feed in HK_RSS_FEEDS:
    hk_articles += fetch_rss(feed)
    time.sleep(0.5)
if len(hk_articles) < 3:
    for q in GNEWS_QUERIES['hk']:
        hk_articles += fetch_gnews(q)
        time.sleep(1)
cache['hk'] = dedupe(hk_articles, 5)

print('\n[2/4] US News...')
us_articles = []
for q in GNEWS_QUERIES['us']:
    us_articles += fetch_gnews(q)
    time.sleep(1)
cache['us'] = dedupe(us_articles, 5)

print('\n[3/4] Earnings & Eco Calendar...')
cache['earnings'] = fetch_earnings()
time.sleep(1)
cache['eco'] = fetch_eco_calendar()

print('\n[4/4] Pre/AH Movers...')
cache['movers'] = fetch_movers()

with open('news-cache.json', 'w', encoding='utf-8') as f:
    json.dump(cache, f, ensure_ascii=False, indent=2)

print(f"""
{'='*55}
Cache saved:
  HK news:  {len(cache['hk'])}
  US news:  {len(cache['us'])}
  Earnings: {len(cache['earnings'])}
  Eco:      {len(cache['eco'])}
  Movers Pre:{len(cache['movers']['pre'])} AH:{len(cache['movers']['ah'])}
{'='*55}""")
