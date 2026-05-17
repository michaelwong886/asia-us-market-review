// ===================== NEWS FEED (Google News via rss2json) =====================
// Google News RSS is public + rss2json converts to JSON = no CORS issues

var RSS2JSON_BASE = 'https://api.rss2json.com/v1/api.json?rss_url=';

var NEWS_SOURCES = {
  hk: [
    {
      name: 'Google News HK Markets',
      url: 'https://news.google.com/rss/search?q=hong+kong+stock+market+HSI&hl=en-HK&gl=HK&ceid=HK:en',
      badge: 'HK MKT',
      color: 'var(--gold)'
    },
    {
      name: 'Google News HK Finance',
      url: 'https://news.google.com/rss/search?q=hang+seng+index+finance&hl=en-HK&gl=HK&ceid=HK:en',
      badge: 'HANG SENG',
      color: 'var(--blue)'
    }
  ],
  us: [
    {
      name: 'Google News US Markets',
      url: 'https://news.google.com/rss/search?q=US+stock+market+SP500+nasdaq&hl=en-US&gl=US&ceid=US:en',
      badge: 'US MKT',
      color: 'var(--accent)'
    },
    {
      name: 'Google News Wall St',
      url: 'https://news.google.com/rss/search?q=wall+street+stocks+earnings&hl=en-US&gl=US&ceid=US:en',
      badge: 'WALL ST',
      color: 'var(--up)'
    }
  ]
};

async function fetchGoogleNews(sourceUrl) {
  try {
    var apiUrl = RSS2JSON_BASE + encodeURIComponent(sourceUrl) + '&count=5&api_key=';
    var resp = await fetch(apiUrl, { signal: AbortSignal.timeout(12000) });
    var data = await resp.json();
    if (!data || data.status !== 'ok' || !data.items || !data.items.length) return null;
    return data.items.slice(0, 5).map(function(item) {
      // Clean Google News redirect links
      var link = item.link || item.guid || '#';
      return {
        title: (item.title || '').replace(/<[^>]+>/g, '').replace(/\s+-\s+[\w\s]+$/, '').trim(),
        link: link,
        time: item.pubDate ? formatNewsTime(item.pubDate) : 'Recent',
        source: (item.author || item.source || '').replace(/<[^>]+>/g, '').trim().substring(0, 30),
        desc: (item.description || item.content || '').replace(/<[^>]+>/g, '').trim().substring(0, 100)
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
    + (article.source ? '<span class="news-time" style="margin-left:auto">' + article.source + '</span>' : '')
    + '</div>'
    + '<div class="news-title">' + article.title + '</div>'
    + (article.desc ? '<div class="news-desc">' + article.desc + '...</div>' : '')
    + '</a>';
}

function renderNewsPlaceholder(region) {
  return '<div class="news-loading"><div style="font-size:1.5rem">&#128240;</div><div>Fetching ' + region + ' headlines...</div></div>';
}

function renderNewsError(region) {
  return '<div class="news-loading" style="color:var(--down)"><div style="font-size:1.5rem">&#9888;</div><div>Could not load ' + region + ' news</div><div style="font-size:0.6rem;margin-top:4px;color:var(--text-faint)">Please try refreshing</div></div>';
}

async function loadNewsFeed() {
  var hkEl = document.getElementById('news-hk');
  var usEl = document.getElementById('news-us');
  var srcEl = document.getElementById('news-src');
  var lastEl = document.getElementById('news-last-update');

  if (hkEl) hkEl.innerHTML = renderNewsPlaceholder('HK');
  if (usEl) usEl.innerHTML = renderNewsPlaceholder('US');
  if (srcEl) srcEl.textContent = 'Loading...';

  var hkPromises = NEWS_SOURCES.hk.map(function(s) {
    return fetchGoogleNews(s.url).then(function(items) { return { items: items, source: s }; });
  });
  var usPromises = NEWS_SOURCES.us.map(function(s) {
    return fetchGoogleNews(s.url).then(function(items) { return { items: items, source: s }; });
  });

  var hkResults = await Promise.allSettled(hkPromises);
  var usResults = await Promise.allSettled(usPromises);

  // Deduplicate by title
  function dedupe(articles) {
    var seen = {};
    return articles.filter(function(a) {
      var key = a.article.title.substring(0, 40);
      if (seen[key]) return false;
      seen[key] = true;
      return true;
    });
  }

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

  hkArticles = dedupe(hkArticles);
  usArticles = dedupe(usArticles);

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
  if (srcEl) srcEl.textContent = anyLive ? 'Google News Live' : 'Unavailable';
  if (lastEl) lastEl.textContent = 'Updated ' + new Date().toLocaleTimeString('en-HK', { timeZone: 'Asia/Hong_Kong' }) + ' HKT';

  // Auto-refresh every 10 minutes
  setTimeout(loadNewsFeed, 600000);
}
