// ===================== NEWS FEED (GNews API) =====================
// GNews returns JSON with proper CORS headers — works on all browsers including Safari iOS

var GNEWS_KEY = 'fee5ea73edbfa9379217510854ba9551';
var GNEWS_BASE = 'https://gnews.io/api/v4/search';

var GNEWS_QUERIES = {
  hk: [
    { q: 'Hong Kong stock market Hang Seng', badge: 'HK MKT', color: 'var(--gold)' },
    { q: 'HSI Hang Seng Index finance', badge: 'HANG SENG', color: 'var(--blue)' }
  ],
  us: [
    { q: 'US stock market S&P 500 nasdaq', badge: 'US MKT', color: 'var(--accent)' },
    { q: 'Wall Street earnings stocks today', badge: 'WALL ST', color: 'var(--up)' }
  ]
};

async function fetchGNews(query) {
  try {
    var url = GNEWS_BASE
      + '?q=' + encodeURIComponent(query.q)
      + '&lang=en&max=5'
      + '&apikey=' + GNEWS_KEY;
    var resp = await fetch(url, { signal: AbortSignal.timeout(10000) });
    if (!resp.ok) return null;
    var data = await resp.json();
    if (!data || !data.articles || !data.articles.length) return null;
    return data.articles.map(function(a) {
      return {
        title: (a.title || '').replace(/\s+-\s+[\w\s]+$/, '').trim(),
        link: a.url || '#',
        time: formatNewsTime(a.publishedAt),
        source: a.source ? (a.source.name || '').substring(0, 30) : '',
        desc: (a.description || '').replace(/<[^>]+>/g, '').trim().substring(0, 100)
      };
    });
  } catch(e) {
    return null;
  }
}

function formatNewsTime(dateStr) {
  try {
    var d = new Date(dateStr);
    if (isNaN(d.getTime())) return 'Recent';
    var diff = Math.floor((new Date() - d) / 60000);
    if (diff < 1) return 'Just now';
    if (diff < 60) return diff + 'm ago';
    if (diff < 1440) return Math.floor(diff/60) + 'h ago';
    return Math.floor(diff/1440) + 'd ago';
  } catch(e) { return 'Recent'; }
}

function renderNewsCard(article, query) {
  var link = (article.link && article.link.startsWith('http')) ? article.link : '#';
  return '<a href="' + link + '" target="_blank" rel="noopener noreferrer" class="news-card">'
    + '<div class="news-meta">'
    + '<span class="news-badge" style="background:' + query.color + '22;color:' + query.color + ';border:1px solid ' + query.color + '44">' + query.badge + '</span>'
    + '<span class="news-time">' + article.time + '</span>'
    + (article.source ? '<span class="news-time" style="margin-left:auto">' + article.source + '</span>' : '')
    + '</div>'
    + '<div class="news-title">' + article.title + '</div>'
    + (article.desc ? '<div class="news-desc">' + article.desc + '...</div>' : '')
    + '</a>';
}

async function loadNewsFeed() {
  var hkEl = document.getElementById('news-hk');
  var usEl = document.getElementById('news-us');
  var srcEl = document.getElementById('news-src');
  var lastEl = document.getElementById('news-last-update');

  if (hkEl) hkEl.innerHTML = '<div class="news-loading"><div style="font-size:1.5rem">&#128240;</div><div>Fetching HK headlines...</div></div>';
  if (usEl) usEl.innerHTML = '<div class="news-loading"><div style="font-size:1.5rem">&#128240;</div><div>Fetching US headlines...</div></div>';
  if (srcEl) { srcEl.textContent = 'Loading...'; srcEl.style.color = 'var(--text-muted)'; }

  var hkPromises = GNEWS_QUERIES.hk.map(function(q) { return fetchGNews(q).then(function(items) { return { items: items, query: q }; }); });
  var usPromises = GNEWS_QUERIES.us.map(function(q) { return fetchGNews(q).then(function(items) { return { items: items, query: q }; }); });

  var hkRes = await Promise.allSettled(hkPromises);
  var usRes = await Promise.allSettled(usPromises);

  function collectAndDedupe(results) {
    var seen = {}, all = [];
    results.forEach(function(r) {
      if (r.status === 'fulfilled' && r.value && r.value.items) {
        r.value.items.forEach(function(item) {
          var key = item.title.substring(0, 40);
          if (!seen[key]) { seen[key] = true; all.push({ article: item, query: r.value.query }); }
        });
      }
    });
    return all;
  }

  var hkArticles = collectAndDedupe(hkRes);
  var usArticles = collectAndDedupe(usRes);

  if (hkEl) {
    hkEl.innerHTML = hkArticles.length
      ? hkArticles.slice(0, 5).map(function(a) { return renderNewsCard(a.article, a.query); }).join('')
      : '<div class="news-loading" style="color:var(--down)"><div style="font-size:1.5rem">&#9888;</div><div>Could not load HK news</div><div style="font-size:0.6rem;margin-top:4px;color:var(--text-faint)">Please try refreshing</div></div>';
  }
  if (usEl) {
    usEl.innerHTML = usArticles.length
      ? usArticles.slice(0, 5).map(function(a) { return renderNewsCard(a.article, a.query); }).join('')
      : '<div class="news-loading" style="color:var(--down)"><div style="font-size:1.5rem">&#9888;</div><div>Could not load US news</div><div style="font-size:0.6rem;margin-top:4px;color:var(--text-faint)">Please try refreshing</div></div>';
  }

  var anyLive = hkArticles.length > 0 || usArticles.length > 0;
  if (srcEl) { srcEl.textContent = anyLive ? 'GNews Live' : 'Unavailable'; srcEl.style.color = anyLive ? 'var(--accent)' : 'var(--down)'; }
  if (lastEl) lastEl.textContent = 'Updated ' + new Date().toLocaleTimeString('en-HK', { timeZone: 'Asia/Hong_Kong' }) + ' HKT';

  // Auto-refresh every 10 minutes
  setTimeout(loadNewsFeed, 600000);
}
