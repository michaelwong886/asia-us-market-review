// ===================== ALERT SYSTEM =====================
// Persists alerts in localStorage, checks on every price refresh

var ALERTS_KEY = 'trading_alerts';

function loadAlerts() {
  try { return JSON.parse(localStorage.getItem(ALERTS_KEY)) || []; } catch(e) { return []; }
}
function saveAlerts(arr) {
  try { localStorage.setItem(ALERTS_KEY, JSON.stringify(arr)); } catch(e) {}
}

// Request browser notification permission
function requestNotifPerm() {
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
  }
}

function fireNotif(title, body) {
  if ('Notification' in window && Notification.permission === 'granted') {
    try {
      new Notification(title, { body: body, icon: '' });
    } catch(e) {}
  }
  // Also show in-app toast
  showAlertToast(title + ' — ' + body);
}

function showAlertToast(msg) {
  var t = document.getElementById('alert-toast');
  if (!t) return;
  t.textContent = '🔔 ' + msg;
  t.style.display = 'block';
  t.style.opacity = '1';
  clearTimeout(t._tid);
  t._tid = setTimeout(function() {
    t.style.opacity = '0';
    setTimeout(function() { t.style.display = 'none'; }, 400);
  }, 5000);
}

// Called on every price refresh with latest mdc map
function checkAlerts(mdc) {
  var alerts = loadAlerts();
  var now = Date.now();
  var triggered = false;
  alerts.forEach(function(a) {
    if (a.triggered) return;
    var q = mdc[a.ticker];
    if (!q || !q.c || q.c <= 0) return;
    var price = q.c;
    var hit = false;
    if (a.condition === 'above' && price >= a.price) hit = true;
    if (a.condition === 'below' && price <= a.price) hit = true;
    if (hit) {
      a.triggered = true;
      a.triggeredAt = now;
      a.triggeredPrice = price;
      fireNotif(
        '🔔 ' + a.ticker + ' Alert',
        a.ticker + ' ' + (a.condition === 'above' ? '▲' : '▼') + ' ' +
        Number(a.price).toLocaleString('en-US', {minimumFractionDigits:2,maximumFractionDigits:2}) +
        ' (Current: ' + Number(price).toLocaleString('en-US', {minimumFractionDigits:2,maximumFractionDigits:2}) + ')'
      );
      triggered = true;
    }
  });
  if (triggered) { saveAlerts(alerts); renderAlertList(); }
}

function addAlert() {
  var ticker = document.getElementById('alert-ticker').value.trim().toUpperCase();
  var price = parseFloat(document.getElementById('alert-price').value);
  var cond = document.getElementById('alert-cond').value;
  var note = document.getElementById('alert-note').value.trim();
  if (!ticker || isNaN(price) || price <= 0) {
    showAlertToast('Please fill in ticker and a valid price.');
    return;
  }
  var alerts = loadAlerts();
  alerts.push({
    id: Date.now(),
    ticker: ticker,
    price: price,
    condition: cond,
    note: note,
    triggered: false,
    triggeredAt: null,
    triggeredPrice: null,
    createdAt: Date.now()
  });
  saveAlerts(alerts);
  document.getElementById('alert-ticker').value = '';
  document.getElementById('alert-price').value = '';
  document.getElementById('alert-note').value = '';
  renderAlertList();
  requestNotifPerm();
  showAlertToast('Alert set: ' + ticker + ' ' + cond + ' ' + price);
}

function removeAlert(id) {
  var alerts = loadAlerts().filter(function(a) { return a.id !== id; });
  saveAlerts(alerts);
  renderAlertList();
}

function clearTriggered() {
  var alerts = loadAlerts().filter(function(a) { return !a.triggered; });
  saveAlerts(alerts);
  renderAlertList();
}

// Auto-populate alert from S/R level click
function setAlertFromLevel(ticker, price, condition) {
  document.getElementById('alert-ticker').value = ticker;
  document.getElementById('alert-price').value = price;
  document.getElementById('alert-cond').value = condition;
  // Navigate to alerts tab
  showTab('alerts', document.querySelector('[data-tab="alerts"]'));
  showAlertToast('Pre-filled: ' + ticker + ' ' + condition + ' ' + price);
}

function renderAlertList() {
  var tbody = document.getElementById('alert-body');
  var badge = document.getElementById('alert-nav-badge');
  if (!tbody) return;
  var alerts = loadAlerts();
  var active = alerts.filter(function(a) { return !a.triggered; });
  if (badge) badge.textContent = active.length > 0 ? active.length : '';
  if (!alerts.length) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:32px">No alerts set. Add one above.</td></tr>';
    return;
  }
  tbody.innerHTML = alerts.map(function(a) {
    var statusBadge = a.triggered
      ? '<span class="badge badge-bull">TRIGGERED</span>'
      : '<span class="badge badge-warn">ACTIVE</span>';
    var triggeredInfo = a.triggered && a.triggeredPrice
      ? '<div style="font-size:0.58rem;color:var(--text-muted)">@ ' + Number(a.triggeredPrice).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}) + '</div>'
      : '';
    var condIcon = a.condition === 'above' ? '&#9650;' : '&#9660;';
    var condColor = a.condition === 'above' ? 'var(--down)' : 'var(--up)';
    return '<tr style="opacity:'+(a.triggered?'0.55':'1')+'">' +
      '<td class="td-ticker">' + a.ticker + '</td>' +
      '<td style="color:'+condColor+';font-weight:700">' + condIcon + ' ' + a.condition.toUpperCase() + '</td>' +
      '<td style="font-family:var(--font-mono);font-weight:700">' + Number(a.price).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}) + '</td>' +
      '<td>' + statusBadge + triggeredInfo + '</td>' +
      '<td style="color:var(--text-muted);font-size:0.65rem">' + (a.note || '--') + '</td>' +
      '<td><button class="btn-sm" style="padding:2px 6px;font-size:0.58rem;color:var(--down)" onclick="removeAlert(' + a.id + ')">&#x2715;</button></td>' +
      '</tr>';
  }).join('');
}

// Preset S/R level alerts (called from S/R tab)
function loadSRPresets() {
  var cont = document.getElementById('sr-preset-list');
  if (!cont) return;
  // Pull from PIVOT_INSTRUMENTS if available
  var levelsGrid = document.getElementById('lvl-grid');
  if (!levelsGrid || !levelsGrid.children.length) {
    cont.innerHTML = '<div style="color:var(--text-muted);font-size:var(--text-xs)">Load S/R Levels tab first to see presets.</div>';
    return;
  }
  // Generate preset buttons for each card
  var cards = levelsGrid.querySelectorAll('.lvl-card');
  var html = '';
  cards.forEach(function(card) {
    var tickerEl = card.querySelector('.lvl-ticker');
    if (!tickerEl) return;
    var ticker = tickerEl.textContent.trim();
    var rows = card.querySelectorAll('.lvl-row');
    rows.forEach(function(row) {
      var typeEl = row.querySelector('.lvl-type');
      var priceEl = row.querySelector('.lvl-price');
      if (!typeEl || !priceEl) return;
      var lvlType = typeEl.textContent.replace('◀','').trim();
      var priceRaw = priceEl.textContent.replace(/,/g,'').trim();
      var price = parseFloat(priceRaw);
      if (!price || isNaN(price)) return;
      var isR = lvlType.startsWith('R');
      var cond = isR ? 'above' : 'below';
      var badgeClass = isR ? 'badge-bear' : 'badge-bull';
      html += '<button class="btn-sm" style="margin:2px" onclick="setAlertFromLevel(\''+ticker+'\','+price+',\''+cond+'\')">' +
        '<span class="badge '+badgeClass+'" style="margin-right:3px">'+lvlType+'</span>' +
        ticker + ' ' + Number(price).toLocaleString('en-US',{minimumFractionDigits:0,maximumFractionDigits:2}) +
        '</button>';
    });
  });
  cont.innerHTML = html || '<div style="color:var(--text-muted);font-size:var(--text-xs)">No levels found. Refresh S/R tab first.</div>';
}

// Init on page load
document.addEventListener('DOMContentLoaded', function() {
  renderAlertList();
  requestNotifPerm();
});
