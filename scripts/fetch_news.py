import requests
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

GNEWS_KEY = 'fee5ea73edbfa9379217510854ba9551'
GNEWS_BASE = 'https://gnews.io/api/v4/search'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; NewsBot/1.0)',
    'Accept': 'application/rss+xml, application/xml, text/xml, */*'
}

# ── RSS sources for HK (fetched server-side, no CORS issue) ──────────────────
HK_RSS_FEEDS = [
    {
        'url': 'https://www.reuters.com/rssFeed/asiaPacificNews',
        'badge': 'REUTERS',
        'color': 'var(--down)',
    },
    {
        'url': 'https://www.scmp.com/rss/2/feed',   # SCMP HK Business
        'badge': 'SCMP',
        'color': 'var(--gold)',
    },
    {
        'url': 'https://news.rthk.hk/rthk/en/component/k2/1456754-546.htm',
        'badge': 'RTHK',
        'color': 'var(--blue)',
    },
    {
        'url': 'https://www.investing.com/rss/news_301.rss',  # Investing.com HK
        'badge': 'INVESTING',
        'color': 'var(--accent)',
    },
]

# ── GNews API queries ────────────────────────────────────────────────────────
GNEWS_QUERIES = {
    'hk': [
        {'q': 'Hong Kong stock market Hang Seng HSI', 'badge': 'HK MKT', 'color': 'var(--gold)'},
    ],
    'us': [
        {'q': 'US stock market S&P 500 nasdaq', 'badge': 'US MKT', 'color': 'var(--accent)'},
        {'q': 'Wall Street earnings stocks today', 'badge': 'WALL ST', 'color': 'var(--up)'},
    ],
}


def fetch_rss(feed):
    """Fetch and parse an RSS feed, return list of article dicts."""
    try:
        r = requests.get(feed['url'], headers=HEADERS, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        items = root.findall('.//item')
        results = []
        for item in items[:6]:
            title = (item.findtext('title') or '').strip()
            link  = (item.findtext('link')  or '').strip()
            pub   = (item.findtext('pubDate') or '').strip()
            desc  = (item.findtext('description') or '').strip()
            # strip HTML tags from desc
            import re
            desc = re.sub(r'<[^>]+>', '', desc)[:120]
            title = re.sub(r'\s+-\s+[\w\s]+$', '', title).strip()
            if title:
                results.append({
                    'title': title,
                    'link': link,
                    'publishedAt': pub,
                    'source': feed['badge'],
                    'desc': desc,
                    'badge': feed['badge'],
                    'color': feed['color'],
                })
        print(f"  RSS {feed['badge']}: {len(results)} articles")
        return results
    except Exception as e:
        print(f"  RSS {feed['badge']} failed: {e}")
        return []


def fetch_gnews(query):
    """Fetch from GNews API."""
    try:
        url = (f"{GNEWS_BASE}?q={requests.utils.quote(query['q'])}"
               f"&lang=en&max=5&apikey={GNEWS_KEY}")
        r = requests.get(url, timeout=15)
        data = r.json()
        articles = data.get('articles', [])
        results = []
        for a in articles:
            results.append({
                'title': (a.get('title') or '').split(' - ')[0].strip(),
                'link':  a.get('url', '#'),
                'publishedAt': a.get('publishedAt', ''),
                'source': (a.get('source') or {}).get('name', ''),
                'desc':   (a.get('description') or '')[:120],
                'badge':  query['badge'],
                'color':  query['color'],
            })
        print(f"  GNews '{query['q'][:30]}': {len(results)} articles")
        return results
    except Exception as e:
        print(f"  GNews failed: {e}")
        return []


def dedupe(articles, limit=5):
    seen, out = set(), []
    for a in articles:
        key = a['title'][:40]
        if key not in seen:
            seen.add(key)
            out.append(a)
        if len(out) >= limit:
            break
    return out


# ── Build cache ──────────────────────────────────────────────────────────────
cache = {'updated': datetime.now(timezone.utc).isoformat(), 'hk': [], 'us': []}

print("Fetching HK news (RSS)...")
hk_articles = []
for feed in HK_RSS_FEEDS:
    hk_articles += fetch_rss(feed)
    time.sleep(0.5)

# Fallback to GNews if RSS gave nothing
if len(hk_articles) < 3:
    print("RSS gave < 3 articles, trying GNews for HK...")
    for q in GNEWS_QUERIES['hk']:
        hk_articles += fetch_gnews(q)
        time.sleep(1)

cache['hk'] = dedupe(hk_articles, 5)

print("Fetching US news (GNews)...")
us_articles = []
for q in GNEWS_QUERIES['us']:
    us_articles += fetch_gnews(q)
    time.sleep(1)

cache['us'] = dedupe(us_articles, 5)

with open('news-cache.json', 'w', encoding='utf-8') as f:
    json.dump(cache, f, ensure_ascii=False, indent=2)

print(f"\nDone. HK: {len(cache['hk'])} | US: {len(cache['us'])} articles cached.")
