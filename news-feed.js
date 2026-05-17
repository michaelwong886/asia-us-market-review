// ===================== NEWS FEED =====================
// Strategy: fetch Google News RSS via AllOrigins CORS proxy, parse XML in browser
// No API keys, no rate limits, no rss2json needed

var NEWS_FEEDS = {
  hk: [
    { url: 'https://news.google.com/rss/search?q=hong+kong+stock+market+HSI&hl=en&gl=HK&ceid=HK:en', badge: 'HK MKT', color: 'var(--gold)' },
    { url: 'https://news.google.com/rss/search?q=hang+seng+index&hl=en&gl=HK&ceid=HK:en', badge: 'HANG SENG', color: 'var(--blue)' }
  ],
  us: [
    { url: 'https://news.google.com/rss/search?q=US+stock+market+S%26P500+nasdaq&hl=en&gl=US&ceid=US:en', badge: 'US MKT', color: 'var(--accent)' },
    { url: 'https://news.google.com/rss/search?q=wall+street+stocks+earnings+today&hl=en&gl=US&ceid=US:en', badge: 'WALL ST', color: 'var(--up)' }
  ]
};

var CORS_PROXIES = [
  function(u){ return 'https://api.allorigins.win/get?url=' + encodeURIComponent(u); },
  function(u){ return 'https://corsproxy.io/?' + encodeURIComponent(u); },
  function(u){ return 'https://thingproxy.freeboard.io/fetch/' + u; }
];

async function fetchRSSXML(feedUrl) {
  for (var i = 0; i < CORS_PROXIES.length; i++) {
    try {
      var proxyUrl = CORS_PROXIES[i](feedUrl);
      var resp = await fetch(proxyUrl, { signal: AbortSignal.timeout(10000) });
      if (!resp.ok) continue;
      var raw = await resp.text();
      // allorigins wraps in JSON: {"contents":"...","status":{}}
      var xmlStr = raw;
      try {
        var json = JSON.parse(raw);
        if (json && json.contents) xmlStr = json.contents;
      } catch(e) {}
      if (!xmlStr || xmlStr.trim().length < 100) continue;
      var parser = new DOMParser();
      var doc = parser.parseFromString(xmlStr, 'text/xml');
      var items = doc.querySelectorAll('item');
      if (!items || items.length === 0) continue;
      var results = [];
      items.forEach(function(item) {
        var title = (item.querySelector('title') || {}).textContent || '';
        var link = (item.querySelector('link') || {}).textContent || '';
        // Google News uses <link> as text node after <title>, try guid too
        if (!link || link.length < 5) {
          var guid = item.querySelector('guid');
          if (guid) link = guid.textContent || '';
        }
        var pubDate = (item.querySelector('pubDate') || {}).textContent || '';
        var source = (item.querySelector('source') || {}).textContent || '';
        var desc = (item.querySelector('description') || {}).textContent || '';
        // Strip HTML from desc
        desc = desc.replace(/<[^>]+>/g, '').trim().substring(0, 100);
        // Clean title (remove trailing " - Source Name")
        title = title.replace(/<[^>]+>/g, '').replace(/\s+-\s+[\w\s]+$/, '').trim();
        if (title.length > 5) {
          results.push({ title: title, link: link, time: formatNewsTime(pubDate), source: source.trim().substring(0, 30), desc: desc });
        }
      });
      if (results.length > 0) return results.slice(0, 5);
    } catch(e) { continue; }
  }
  return null;
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

function renderNewsCard(article, feed) {
  var link = (article.link && article.link.startsWith('http')) ? article.link : '#';
  return '<a href="' + link + '" target="_blank" rel="noopener noreferrer" class="news-card">'
    + '<div class="news-meta">'
    + '<span class="news-badge" style="background:' + feed.color + '22;color:' + feed.color + ';border:1px solid ' + feed.color + '44">' + feed.badge + '</span>'
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
  if (srcEl) srcEl.textContent = 'Loading...';
  if (srcEl) srcEl.style.color = 'var(--text-muted)';

  var hkPromises = NEWS_FEEDS.hk.map(function(f) { return fetchRSSXML(f.url).then(function(items) { return { items: items, feed: f }; }); });
  var usPromises = NEWS_FEEDS.us.map(function(f) { return fetchRSSXML(f.url).then(function(items) { return { items: items, feed: f }; }); });

  var hkRes = await Promise.allSettled(hkPromises);
  var usRes = await Promise.allSettled(usPromises);

  function collectAndDedupe(results) {
    var seen = {}, all = [];
    results.forEach(function(r) {
      if (r.status === 'fulfilled' && r.value && r.value.items) {
        r.value.items.forEach(function(item) {
          var key = item.title.substring(0, 40);
          if (!seen[key]) { seen[key] = true; all.push({ article: item, feed: r.value.feed }); }
        });
      }
    });
    return all;
  }

  var hkArticles = collectAndDedupe(hkRes);
  var usArticles = collectAndDedupe(usRes);

  if (hkEl) {
    hkEl.innerHTML = hkArticles.length
      ? hkArticles.slice(0, 5).map(function(a) { return renderNewsCard(a.article, a.feed); }).join('')
      : '<div class="news-loading" style="color:var(--down)"><div style="font-size:1.5rem">&#9888;</div><div>Could not load HK news</div><div style="font-size:0.6rem;margin-top:4px;color:var(--text-faint)">Please try refreshing</div></div>';
  }
  if (usEl) {
    usEl.innerHTML = usArticles.length
      ? usArticles.slice(0, 5).map(function(a) { return renderNewsCard(a.article, a.feed); }).join('')
      : '<div class="news-loading" style="color:var(--down)"><div style="font-size:1.5rem">&#9888;</div><div>Could not load US news</div><div style="font-size:0.6rem;margin-top:4px;color:var(--text-faint)">Please try refreshing</div></div>';
  }

  var anyLive = hkArticles.length > 0 || usArticles.length > 0;
  if (srcEl) { srcEl.textContent = anyLive ? 'Google News Live' : 'Unavailable'; srcEl.style.color = anyLive ? 'var(--accent)' : 'var(--down)'; }
  if (lastEl) lastEl.textContent = 'Updated ' + new Date().toLocaleTimeString('en-HK', { timeZone: 'Asia/Hong_Kong' }) + ' HKT';

  // Auto-refresh every 10 minutes
  setTimeout(loadNewsFeed, 600000);
}
