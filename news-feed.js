// ===================== NEWS FEED =====================
// RSS sources via CORS proxy
var NEWS_SOURCES = {
  hk: [
    { name: 'SCMP Markets', url: 'https://www.scmp.com/rss/91/feed', badge: 'SCMP', color: 'var(--gold)' },
    { name: 'RTHK Business', url: 'https://rthk.hk/rthk/news/rss/e_expressnews_business.xml', badge: 'RTHK', color: 'var(--blue)' }
  ],
  us: [
    { name: 'Yahoo Finance', url: 'https://finance.yahoo.com/news/rssindex', badge: 'YAHOO', color: 'var(--accent)' },
    { name: 'CNBC Markets', url: 'https://www.cnbc.com/id/10000664/device/rss/rss.html', badge: 'CNBC', color: 'var(--up)' }
  ]
};

var NEWS_PROXIES = [
  function(url) { return 'https://api.allorigins.win/get?url=' + encodeURIComponent(url); },
  function(url) { return 'https://corsproxy.io/?' + encodeURIComponent(url); }
];

async function fetchRSS(sourceUrl) {
  for (var i = 0; i < NEWS_PROXIES.length; i++) {
    try {
      var resp = await fetch(NEWS_PROXIES[i](sourceUrl), { signal: AbortSignal.timeout(8000) });
      var raw = await resp.json();
      var text = (raw && raw.contents) ? raw.contents : (typeof raw === 'string' ? raw : null);
      if (!text) continue;
      var parser = new DOMParser();
      var xml = parser.parseFromString(text, 'text/xml');
      var items = xml.querySelectorAll('item');
      if (!items || !items.length) continue;
      var results = [];
      for (var j = 0; j < Math.min(items.length, 5); j++) {
        var item = items[j];
        var title = item.querySelector('title');
        var link = item.querySelector('link');
        var pubDate = item.querySelector('pubDate');
        var desc = item.querySelector('description');
        if (title && title.textContent) {
          results.push({
            title: title.textContent.replace(/<!\[CDATA\[|\]\]>/g, '').trim(),
            link: link ? (link.textContent || link.getAttribute('href') || '#') : '#',
            time: pubDate ? formatNewsTime(pubDate.textContent) : 'Recent',
            desc: desc ? desc.textContent.replace(/<!\[CDATA\[|\]\]>/g, '').replace(/<[^>]+>/g, '').trim().substring(0, 120) : ''
          });
        }
      }
      if (results.length) return results;
    } catch (e) {}
  }
  return null;
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
  return '<div class="news-loading" style="color:var(--down)"><div style="font-size:1.5rem">&#9888;</div><div>Could not load ' + region + ' news</div><div style="font-size:0.6rem;margin-top:4px;color:var(--text-faint)">RSS proxy unavailable</div></div>';
}

async function loadNewsFeed() {
  var hkEl = document.getElementById('news-hk');
  var usEl = document.getElementById('news-us');
  var srcEl = document.getElementById('news-src');
  var lastEl = document.getElementById('news-last-update');

  if (hkEl) hkEl.innerHTML = renderNewsPlaceholder('HK');
  if (usEl) usEl.innerHTML = renderNewsPlaceholder('US');

  // Fetch all sources in parallel
  var hkPromises = NEWS_SOURCES.hk.map(function(s) { return fetchRSS(s.url).then(function(items) { return { items: items, source: s }; }); });
  var usPromises = NEWS_SOURCES.us.map(function(s) { return fetchRSS(s.url).then(function(items) { return { items: items, source: s }; }); });

  var hkResults = await Promise.allSettled(hkPromises);
  var usResults = await Promise.allSettled(usPromises);

  // Merge HK top 5
  var hkArticles = [];
  hkResults.forEach(function(r) {
    if (r.status === 'fulfilled' && r.value && r.value.items) {
      r.value.items.forEach(function(item) {
        hkArticles.push({ article: item, source: r.value.source });
      });
    }
  });

  // Merge US top 5
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

  // Auto-refresh every 10 minutes
  setTimeout(loadNewsFeed, 600000);
}
