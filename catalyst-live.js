// ===================== CATALYST LIVE =====================
// Reads earnings, eco events, surprises, movers from news-cache.json
// Updated every 15 min by GitHub Actions

async function loadCatalystLive() {
  try {
    var resp = await fetch('news-cache.json?t=' + Date.now(), { signal: AbortSignal.timeout(10000) });
    if (!resp.ok) return;
    var data = await resp.json();
    renderEarnings(data.earnings || []);
    renderEcoCalendar(data.eco || []);
    renderSurprises(data.surprises || []);
    renderMovers(data.movers || []);
    var el = document.getElementById('catalyst-src');
    if (el) {
      var ago = data.updated ? formatCatTime(data.updated) : 'recently';
      el.textContent = 'Live · cached ' + ago;
      el.style.color = 'var(--accent)';
    }
  } catch(e) {
    console.warn('Catalyst cache not ready yet:', e);
  }
}

function formatCatTime(iso) {
  try {
    var diff = Math.floor((new Date() - new Date(iso)) / 60000);
    if (diff < 1) return 'just now';
    if (diff < 60) return diff + 'm ago';
    return Math.floor(diff/60) + 'h ago';
  } catch(e) { return ''; }
}

function renderEarnings(earnings) {
  var tbody = document.getElementById('earnings-body');
  if (!tbody) return;
  if (!earnings.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:20px">No upcoming earnings cached yet</td></tr>';
    return;
  }
  tbody.innerHTML = earnings.map(function(e) {
    var impClass = e.impact === 'HIGH' ? 'badge-bear' : 'badge-warn';
    return '<tr>'
      + '<td>' + e.date + '</td>'
      + '<td class="td-ticker">' + e.ticker + '</td>'
      + '<td>' + e.company + '</td>'
      + '<td class="td-neutral">' + e.time + '</td>'
      + '<td style="font-family:var(--font-mono)">' + e.eps + '</td>'
      + '<td style="font-family:var(--font-mono)">' + e.rev + '</td>'
      + '<td><span class="badge ' + impClass + '">' + e.impact + '</span></td>'
      + '</tr>';
  }).join('');
}

function renderEcoCalendar(events) {
  var el = document.getElementById('eco-cal');
  if (!el) return;
  if (!events.length) return; // keep static fallback
  el.innerHTML = events.map(function(e) {
    var dots = '';
    for (var i = 0; i < 3; i++) {
      var on = i < e.imp;
      var c = e.imp === 3 ? 'var(--down)' : e.imp === 2 ? 'var(--warn)' : 'var(--up)';
      dots += '<div class="cal-dot" style="background:' + (on ? c : 'var(--border)') + '"></div>';
    }
    var link = e.link ? ' href="' + e.link + '" target="_blank"' : '';
    return '<div class="cal-item">'
      + '<div class="cal-time">' + e.country + ' <span style="color:var(--text-faint)">' + (e.time || '') + '</span></div>'
      + '<div class="cal-dots">' + dots + '</div>'
      + '<div><a' + link + ' style="color:var(--text);text-decoration:none">' + e.event + '</a></div>'
      + '<div style="font-family:var(--font-mono);font-size:0.62rem;color:var(--text-muted)">' + (e.desc || '') + '</div>'
      + '</div>';
  }).join('');
}

function renderSurprises(items) {
  var el = document.getElementById('cat-surprises');
  if (!el) return;
  if (!items.length) {
    el.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:var(--text-xs)">No surprise data yet</div>';
    return;
  }
  el.innerHTML = items.map(function(a) {
    return '<div class="cat-item">'
      + '<div class="cat-dot" style="background:var(--warn)"></div>'
      + '<div class="cat-content">'
      + '<div class="cat-title"><a href="' + a.link + '" target="_blank" style="color:var(--text);text-decoration:none">' + a.title + '</a></div>'
      + '<div class="cat-sub">' + (a.source || '') + ' · ' + (a.desc || '') + '</div>'
      + '</div>'
      + '</div>';
  }).join('');
}

function renderMovers(movers) {
  var el = document.getElementById('cat-movers');
  if (!el) return;
  if (!movers.length) {
    el.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:var(--text-xs)">No mover data yet</div>';
    return;
  }
  el.innerHTML = movers.map(function(m) {
    var c = m.up ? 'var(--up)' : 'var(--down)';
    return '<div class="cat-item">'
      + '<div class="cat-dot" style="background:' + m.color + '"></div>'
      + '<div class="cat-content">'
      + '<div class="cat-title" style="display:flex;justify-content:space-between">'
      + '<span><span style="color:var(--accent);font-weight:700;font-family:var(--font-mono)">' + m.symbol + '</span> <span style="color:var(--text-muted)">' + m.name + '</span></span>'
      + '<span style="font-family:var(--font-mono);color:' + c + ';font-weight:700">' + m.chg + '</span>'
      + '</div>'
      + '<div class="cat-sub"><span class="badge badge-' + (m.label==='GAINER'?'bull':m.label==='LOSER'?'bear':'neutral') + '">' + m.label + '</span> $' + m.price + '</div>'
      + '</div></div>';
  }).join('');
}

// Auto-load when catalyst tab opened
window._catalystLoaded = false;
var _origShowTab = window.showTab;
if (typeof _origShowTab === 'function') {
  window.showTab = function(name, btn) {
    _origShowTab(name, btn);
    if (name === 'catalyst' && !window._catalystLoaded) {
      loadCatalystLive();
      window._catalystLoaded = true;
    }
  };
}
// Also try loading immediately in case catalyst is default tab
setTimeout(function() {
  if (!window._catalystLoaded) { loadCatalystLive(); window._catalystLoaded = true; }
}, 2000);
