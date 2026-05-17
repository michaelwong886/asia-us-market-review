// ===================== LIVE CATALYST FEED =====================
// Reads from news-cache.json built by GitHub Actions every 15 min

function formatCatTime(dateStr) {
  if (!dateStr || dateStr === '--') return dateStr || '--';
  try {
    var d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'America/New_York' });
  } catch(e) { return dateStr; }
}

function impactClass(imp) {
  if (imp === 'HIGH' || imp === 3) return 'badge-bear';
  if (imp === 'MED'  || imp === 2) return 'badge-warn';
  return 'badge-neutral';
}
function impactLabel(imp) {
  if (imp === 3) return 'HIGH';
  if (imp === 2) return 'MED';
  if (imp === 1) return 'LOW';
  return imp || 'MED';
}

async function loadCatalystData() {
  try {
    var resp = await fetch('news-cache.json?t=' + Date.now(), { signal: AbortSignal.timeout(8000) });
    if (!resp.ok) throw new Error('no cache');
    var data = await resp.json();
    renderEarnings(data.earnings || []);
    renderEcoCalendar(data.eco || []);
    renderMovers(data.movers || { pre: [], ah: [] });
    renderCatMini(data.earnings || [], data.eco || []);
  } catch(e) {
    console.warn('Catalyst cache not ready:', e);
  }
}

function renderEarnings(earnings) {
  var tbody = document.getElementById('earnings-body');
  if (!tbody) return;
  if (!earnings.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:20px">No earnings data cached yet</td></tr>';
    return;
  }
  tbody.innerHTML = earnings.map(function(e) {
    var link = e.link ? ' onclick="window.open(\'' + e.link + '\',\'_blank\')"' : '';
    return '<tr style="cursor:' + (e.link ? 'pointer' : 'default') + '"' + link + '>'
      + '<td>' + formatCatTime(e.date) + '</td>'
      + '<td class="td-ticker">' + (e.ticker || '--') + '</td>'
      + '<td style="max-width:120px;overflow:hidden;text-overflow:ellipsis">' + (e.company || '--') + '</td>'
      + '<td class="td-neutral">' + (e.time || '--') + '</td>'
      + '<td style="font-family:var(--font-mono)">' + (e.epsEst || '--') + '</td>'
      + '<td style="font-family:var(--font-mono)">' + (e.revEst || '--') + '</td>'
      + '<td><span class="badge ' + impactClass(e.impact) + '">' + (e.impact || 'MED') + '</span></td>'
      + '</tr>';
  }).join('');
}

function renderEcoCalendar(eco) {
  var el = document.getElementById('eco-cal');
  if (!el) return;
  if (!eco.length) {
    el.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-muted)">No economic events cached yet</div>';
    return;
  }
  el.innerHTML = eco.map(function(e) {
    var imp = e.impact || 2;
    var dots = '';
    for (var i = 0; i < 3; i++) {
      var on = i < imp;
      var c = imp === 3 ? 'var(--down)' : imp === 2 ? 'var(--warn)' : 'var(--up)';
      dots += '<div class="cal-dot" style="background:' + (on ? c : 'var(--border)') + '"></div>';
    }
    var link = e.link ? 'onclick="window.open(\'' + e.link + '\',\'_blank\')" style="cursor:pointer"' : '';
    return '<div class="cal-item" ' + link + '>'
      + '<div class="cal-time">' + (e.country || '') + ' ' + (e.time || '') + '</div>'
      + '<div class="cal-dots">' + dots + '</div>'
      + '<div>' + (e.event || '') + '</div>'
      + '<div style="font-family:var(--font-mono);font-size:0.62rem;color:var(--text-muted)">'
      + 'Est:' + (e.forecast || '--') + ' Prev:' + (e.previous || '--') + '</div>'
      + '</div>';
  }).join('');
}

function renderMovers(movers) {
  var preEl = document.getElementById('cat-pre');
  var ahEl  = document.getElementById('cat-ah');

  function moverHTML(m) {
    var up = m.changePct >= 0;
    var color = up ? 'var(--up)' : 'var(--down)';
    var sign  = up ? '+' : '';
    return '<div class="cat-item">'
      + '<div class="cat-time">' + (m.session === 'pre' ? 'Pre-Mkt' : 'After-Hrs') + '</div>'
      + '<div class="cat-dot" style="background:' + color + '"></div>'
      + '<div class="cat-content">'
      + '<div class="cat-title">' + m.ticker + ' <span style="font-weight:400;color:var(--text-muted)">' + (m.name || '') + '</span></div>'
      + '<div class="cat-sub">$' + (m.price || '--') + ' &nbsp;<span style="color:' + color + ';font-weight:700">' + sign + (m.changePct || 0).toFixed(2) + '%</span> &middot; ' + m.type + '</div>'
      + '</div>'
      + '<div class="cat-impact" style="color:' + color + '">' + (up ? '&#9650;' : '&#9660;') + '</div>'
      + '</div>';
  }

  // Pre-market
  if (preEl) {
    var preItems = (movers.pre || []);
    preEl.innerHTML = preItems.length
      ? preItems.map(moverHTML).join('')
      : '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:var(--text-xs)">&#9203; Pre-market data updates before 9:30 ET</div>';
  }

  // After-hours
  if (ahEl) {
    var ahItems = (movers.ah || []);
    ahEl.innerHTML = ahItems.length
      ? ahItems.map(moverHTML).join('')
      : '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:var(--text-xs)">&#9203; After-hours data updates after 16:00 ET</div>';
  }
}

function renderCatMini(earnings, eco) {
  var mini = document.getElementById('cat-mini');
  if (!mini) return;
  var items = [];
  // Top 3 earnings
  earnings.slice(0, 2).forEach(function(e) {
    items.push('<div class="cat-item">'
      + '<div class="cat-dot" style="background:var(--down)"></div>'
      + '<div class="cat-content"><div class="cat-title">' + (e.ticker || e.company || '--') + ' Earnings</div>'
      + '<div class="cat-sub">' + formatCatTime(e.date) + ' &middot; ' + (e.time || '') + ' &middot; EPS Est ' + (e.epsEst || '--') + '</div></div>'
      + '</div>');
  });
  // Top 1 eco event
  eco.slice(0, 1).forEach(function(e) {
    items.push('<div class="cat-item">'
      + '<div class="cat-dot" style="background:var(--warn)"></div>'
      + '<div class="cat-content"><div class="cat-title">' + (e.event || 'Economic Event') + '</div>'
      + '<div class="cat-sub">' + (e.country || '') + ' &middot; ' + (e.time || '') + ' &middot; Est: ' + (e.forecast || '--') + '</div></div>'
      + '</div>');
  });
  mini.innerHTML = items.length ? items.join('') : '<div style="padding:20px;text-align:center;color:var(--text-muted)">Loading catalysts...</div>';
}

// Auto-load on page ready
setTimeout(loadCatalystData, 1500);
