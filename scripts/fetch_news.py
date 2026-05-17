import requests
import json
import time
from datetime import datetime, timezone

GNEWS_KEY = 'fee5ea73edbfa9379217510854ba9551'
BASE = 'https://gnews.io/api/v4/search'

QUERIES = {
    'hk': [
        {'q': 'Hong Kong stock market Hang Seng', 'badge': 'HK MKT', 'color': 'var(--gold)'},
        {'q': 'HSI Hang Seng Index finance', 'badge': 'HANG SENG', 'color': 'var(--blue)'},
    ],
    'us': [
        {'q': 'US stock market S&P 500 nasdaq', 'badge': 'US MKT', 'color': 'var(--accent)'},
        {'q': 'Wall Street earnings stocks today', 'badge': 'WALL ST', 'color': 'var(--up)'},
    ],
}

def fetch(query):
    try:
        url = f"{BASE}?q={requests.utils.quote(query['q'])}&lang=en&max=5&apikey={GNEWS_KEY}"
        r = requests.get(url, timeout=15)
        data = r.json()
        articles = data.get('articles', [])
        results = []
        for a in articles:
            results.append({
                'title': a.get('title', '').split(' - ')[0].strip(),
                'link':  a.get('url', '#'),
                'publishedAt': a.get('publishedAt', ''),
                'source': (a.get('source') or {}).get('name', ''),
                'desc': (a.get('description') or '')[:120],
                'badge': query['badge'],
                'color': query['color'],
            })
        return results
    except Exception as e:
        print(f"Error fetching {query['q']}: {e}")
        return []

cache = {'updated': datetime.now(timezone.utc).isoformat(), 'hk': [], 'us': []}

for region, queries in QUERIES.items():
    seen = set()
    for q in queries:
        articles = fetch(q)
        for a in articles:
            key = a['title'][:40]
            if key not in seen:
                seen.add(key)
                cache[region].append(a)
        time.sleep(1)  # be polite to API

    cache[region] = cache[region][:5]

with open('news-cache.json', 'w', encoding='utf-8') as f:
    json.dump(cache, f, ensure_ascii=False, indent=2)

print(f"Done. HK: {len(cache['hk'])} articles, US: {len(cache['us'])} articles")
