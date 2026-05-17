// ===================== NEWS FEED (rss2json) =====================
// Uses rss2json.com free API - no CORS issues, works from any browser

var RSS2JSON = 'https://api.rss2json.com/v1/api.json?rss_url=';

var NEWS_SOURCES = {
  hk: [
    { name: 'RTHK Business', url: 'https://rthk.hk/rthk/news/rss/e_expressnews_business.xml', badge: 'RTHK', color: 'var(--blue)' },
    { name: 'The Standard HK', url: 'https://www.thestandard.com.hk/newsfeed/rss/section/3', badge: 'STD', color: 'var(--gold)' }
  ],
  us: [
    { name: 'MarketWatch', url: 'https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines', badge: 'MKT', color: 'var(--accent)' },
    { name: 'Seeking Alpha', url: 'https://seekingalpha.com/market_currents.xml', badge: 'SA', color: 'var(--up)' }
  ]
};

async function fetchRSS2JSON(sourceUrl) {
  try {
    var apiUrl = RSS2JSON + encodeURIComponent(sourceUrl) + '&count=5';
    var resp = await fetch(apiUrl, { signal: AbortSignal.timeout(10000) });
    var data = await resp.json();
    if (!data || data.status !== 'ok' || !data.items || !data.items.length) return null;
    return data.items.slice(0, 5).map(function(item) {
      return {
        title: (item.title || '').replace(/<[^>]+>/g, '').trim(),
        link: item.link || item.guid || '#',
        time: item.pubDate ? formatNewsTime(item.pubDate) : 'Recent',
        desc: (item.description || item.content || '').replace(/<[^>]+>/g, '').trim().substring(0, 120)
      };
    });
  } catch (e) {
    return null;
  }
}

function formatNewsTime(dateStr) {
  try {
    var d = new Date(dateStr);
    if (isNaN(d.getTime())) return 'Recent';
    var now = new Date();
    var diff = Math.floor((now - d) / 60000);
    if (diff < 1) return 'Just now';
    if (diff < 60) return diff + 'm ago';
    if (diff < 1440) return Math.floor(diff / 60) + 'h ago';
    return Math.floor(diff / 1440) + 'd ago';
  } catch (e) { return 'Recent'; }
}

function renderNewsCard(article, source) {
  var linkUrl = article.link && article.link.startsWith('http') ? article.link : '#';
  return '<a href="' + linkUrl + '" target="_blank" rel="noopener noreferrer" class="news-card">'
    + '<div class="news-meta">'
    + '<span class="news-badge" style="background:' + source.color + '22;color:' + source.color + ';border:1px solid ' + source.color + '44">' + source.badge + '</span>'
    + '<span class="news-time">' + article.time + '</span>'
    + '</div>'
    + '<div class="news-title">' + article.title + '</div>'
    + (article.desc ? '<div class="news-desc">' + article.desc + '...</div>' : '')
    + '</a>';
}

function renderNewsPlaceholder(region) {
  return '<div class="news-loading"><div style="font-size:1.5rem">&#128240;</div><div>Fetching ' + region + ' headlines...</div></div>';
}

function renderNewsError(region) {
  return '<div class="news-loading" style="color:var(--down)"><div style="font-size:1.5rem">&#9888;</div><div>Could not load ' + region + ' news</div><div style="font-size:0.6rem;margin-top:4px;color:var(--text-faint)">Check back shortly</div></div>';
}

async function loadNewsFeed() {
  var hkEl = document.getElementById('news-hk');
  var usEl = document.getElementById('news-us');
  var srcEl = document.getElementById('news-src');
  var lastEl = document.getElementById('news-last-update');

  if (hkEl) hkEl.innerHTML = renderNewsPlaceholder('HK');
  if (usEl) usEl.innerHTML = renderNewsPlaceholder('US');

  var hkPromises = NEWS_SOURCES.hk.map(function(s) {
    return fetchRSS2JSON(s.url).then(function(items) { return { items: items, source: s }; });
  });
  var usPromises = NEWS_SOURCES.us.map(function(s) {
    return fetchRSS2JSON(s.url).then(function(items) { return { items: items, source: s }; });
  });

  var hkResults = await Promise.allSettled(hkPromises);
  var usResults = await Promise.allSettled(usPromises);

  var hkArticles = [];
  hkResults.forEach(function(r) {
    if (r.status === 'fulfilled' && r.value && r.value.items) {
      r.value.items.forEach(function(item) {
        hkArticles.push({ article: item, source: r.value.source });
      });
    }
  });

  var usArticles = [];
  usResults.forEach(function(r) {
    if (r.status === 'fulfilled' && r.value && r.value.items) {
      r.value.items.forEach(function(item) {
        usArticles.push({ article: item, source: r.value.source });
      });
    }
  });

  if (hkEl) {
    if (hkArticles.length) {
      hkEl.innerHTML = hkArticles.slice(0, 5).map(function(a) { return renderNewsCard(a.article, a.source); }).join('');
    } else {
      hkEl.innerHTML = renderNewsError('HK');
    }
  }

  if (usEl) {
    if (usArticles.length) {
      usEl.innerHTML = usArticles.slice(0, 5).map(function(a) { return renderNewsCard(a.article, a.source); }).join('');
    } else {
      usEl.innerHTML = renderNewsError('US');
    }
  }

  var anyLive = hkArticles.length > 0 || usArticles.length > 0;
  if (srcEl) srcEl.textContent = anyLive ? 'RSS Live' : 'Unavailable';
  if (lastEl) lastEl.textContent = 'Updated ' + new Date().toLocaleTimeString('en-HK', { timeZone: 'Asia/Hong_Kong' }) + ' HKT';

  setTimeout(loadNewsFeed, 600000);
}
