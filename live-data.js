// ===================== LIVE DATA FETCHERS =====================
// Fear & Greed — CNN Business API (free, no key)
async function fetchFearGreed(){
  var URLS=[
    'https://corsproxy.io/?'+encodeURIComponent('https://production.dataviz.cnn.io/index/fearandgreed/graphdata'),
    'https://api.allorigins.win/get?url='+encodeURIComponent('https://production.dataviz.cnn.io/index/fearandgreed/graphdata')
  ];
  for(var i=0;i<URLS.length;i++){
    try{
      var resp=await fetch(URLS[i],{signal:AbortSignal.timeout(7000)});
      var raw=await resp.json();
      var data=(raw&&raw.contents)?JSON.parse(raw.contents):raw;
      if(data&&data.fear_and_greed&&data.fear_and_greed.score!==undefined){
        var score=Math.round(data.fear_and_greed.score);
        var rating=data.fear_and_greed.rating||'';
        var h=data.fear_and_greed_historical&&data.fear_and_greed_historical.data;
        var w1=h&&h.length>=2?Math.round(h[h.length-2].y):null;
        var m1=h&&h.length>=5?Math.round(h[h.length-5].y):null;
        return {score:score,rating:rating,w1:w1,m1:m1,live:true};
      }
    }catch(e){}
  }
  return null;
}

function applyFearGreed(d){
  if(!d)return;
  var scoreEl=document.querySelector('#tab-sentiment .kpi-fg-score');
  var ratingEl=document.querySelector('#tab-sentiment .kpi-fg-rating');
  var barEl=document.querySelector('#tab-sentiment .fg-bar-fill');
  var w1El=document.querySelector('#fg-w1');
  var m1El=document.querySelector('#fg-m1');
  var srcEl=document.getElementById('fg-src');
  var color=d.score>=60?'var(--up)':d.score<=40?'var(--down)':'var(--warn)';
  if(scoreEl){scoreEl.textContent=d.score;scoreEl.style.color=color;}
  if(ratingEl){ratingEl.textContent=d.rating;ratingEl.style.color=color;}
  if(barEl){barEl.style.width=d.score+'%';barEl.style.background=color;}
  if(w1El&&d.w1!==null)w1El.textContent=d.w1;
  if(m1El&&d.m1!==null)m1El.textContent=d.m1;
  if(srcEl)srcEl.textContent=d.live?'CNN (live)':'Static';
}

// ===================== US TREASURY YIELDS =====================
async function fetchTreasuryYields(){
  var today=new Date();
  var year=today.getFullYear();
  var TURL='https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value='+year;
  var PROXIES=[
    'https://corsproxy.io/?'+encodeURIComponent(TURL),
    'https://api.allorigins.win/get?url='+encodeURIComponent(TURL)
  ];
  for(var i=0;i<PROXIES.length;i++){
    try{
      var resp=await fetch(PROXIES[i],{signal:AbortSignal.timeout(10000)});
      var raw=await resp.json();
      var text=(raw&&raw.contents)?raw.contents:null;
      if(!text&&typeof raw==='string')text=raw;
      if(!text)continue;
      var parser=new DOMParser();
      var xml=parser.parseFromString(text,'text/xml');
      var entries=xml.querySelectorAll('entry');
      if(!entries||!entries.length)continue;
      var last=entries[entries.length-1];
      function yv(tag){var el=last.querySelector(tag);return el?parseFloat(el.textContent):null;}
      var y2=yv('BC_2YEAR'),y5=yv('BC_5YEAR'),y10=yv('BC_10YEAR'),y30=yv('BC_30YEAR');
      if(y10&&y10>0){
        return [
          {label:'2Y',value:y2?y2.toFixed(2)+'%':'--',chg:'',up:false,live:true},
          {label:'5Y',value:y5?y5.toFixed(2)+'%':'--',chg:'',up:false,live:true},
          {label:'10Y',value:y10?y10.toFixed(2)+'%':'--',chg:'',up:false,live:true},
          {label:'30Y',value:y30?y30.toFixed(2)+'%':'--',chg:'',up:false,live:true}
        ];
      }
    }catch(e){}
  }
  return null;
}

function applyYields(yields){
  if(!yields)return;
  var yg=document.getElementById('yield-grid');
  if(!yg)return;
  yg.innerHTML=yields.map(function(y){
    return '<div class="macro-item"><div class="macro-label">'+y.label+'</div><div class="macro-value">'+y.value+'</div><div class="macro-chg" style="color:var(--text-muted)">'+y.chg+'</div></div>';
  }).join('');
  var srcEl=document.getElementById('yield-src');
  if(srcEl)srcEl.textContent=yields[0]&&yields[0].live?'US Treasury (live)':'Static';
}

// ===================== COMMODITIES =====================
var COMM_YF_MAP=[
  {icon:'&#129351;',name:'Gold',sym:'GC=F',unit:'USD/oz'},
  {icon:'&#129352;',name:'Silver',sym:'SI=F',unit:'USD/oz'},
  {icon:'&#9981;',name:'WTI Crude',sym:'CL=F',unit:'USD/bbl'},
  {icon:'&#9981;',name:'Brent Crude',sym:'BZ=F',unit:'USD/bbl'},
  {icon:'&#128992;',name:'Copper',sym:'HG=F',unit:'USD/lb'},
  {icon:'&#9898;',name:'Platinum',sym:'PL=F',unit:'USD/oz'},
  {icon:'&#128295;',name:'Palladium',sym:'PA=F',unit:'USD/oz'},
  {icon:'&#128295;',name:'Aluminum',sym:'ALI=F',unit:'USD/t'}
];

async function fetchLiveCommodities(){
  var syms=COMM_YF_MAP.map(function(c){return c.sym;});
  var results=await Promise.allSettled(syms.map(function(s){return yfQuote(s);}));
  var any=false,updated=[];
  for(var i=0;i<COMM_YF_MAP.length;i++){
    var r=results[i],base=COMM_YF_MAP[i];
    if(r.status==='fulfilled'&&r.value&&r.value.c>0){
      updated.push({icon:base.icon,name:base.name,price:r.value.c,pct:r.value.dp,unit:base.unit,live:true});
      any=true;
    } else {
      var fb=window.COMMODITIES?window.COMMODITIES.find(function(x){return x.name===base.name;}):null;
      updated.push(fb?{icon:base.icon,name:base.name,price:fb.price,pct:fb.pct,unit:base.unit,live:false}
        :{icon:base.icon,name:base.name,price:0,pct:0,unit:base.unit,live:false});
    }
  }
  if(any)window.COMMODITIES=updated;
  return any?updated:null;
}

// ===================== PIVOT POINT S/R LEVELS =====================
// All indices shown in the dashboard
var PIVOT_INSTRUMENTS=[
  {ticker:'SPY',   yfSym:'SPY',        flagCls:'flag-us', dec:2},
  {ticker:'QQQ',   yfSym:'QQQ',        flagCls:'flag-us', dec:2},
  {ticker:'DIA',   yfSym:'DIA',        flagCls:'flag-us', dec:2},
  {ticker:'IWM',   yfSym:'IWM',        flagCls:'flag-us', dec:2},
  {ticker:'HSI',   yfSym:'^HSI',       flagCls:'flag-hk', dec:0},
  {ticker:'HSTECH',yfSym:'^HSTECH',    flagCls:'flag-hk', dec:0},
  {ticker:'NI225', yfSym:'^N225',      flagCls:'flag-jp', dec:0},
  {ticker:'KOSPI', yfSym:'^KS11',      flagCls:'flag-kr', dec:2},
  {ticker:'FTSE',  yfSym:'^FTSE',      flagCls:'flag-gb', dec:2},
  {ticker:'CSI300',yfSym:'000300.SS',  flagCls:'flag-cn', dec:2}
];

// Fetch previous day OHLC using Yahoo Finance 5d/1d interval
async function fetchPivotData(inst){
  var YF_BASE='https://query1.finance.yahoo.com/v8/finance/chart/';
  var YF_PROXIES=[
    function(url){return 'https://corsproxy.io/?'+encodeURIComponent(url);},
    function(url){return 'https://api.allorigins.win/get?url='+encodeURIComponent(url);}
  ];
  var params='?interval=1d&range=5d';
  for(var i=0;i<YF_PROXIES.length;i++){
    try{
      var url=YF_BASE+encodeURIComponent(inst.yfSym)+params;
      var resp=await fetch(YF_PROXIES[i](url),{signal:AbortSignal.timeout(8000)});
      var raw=await resp.json();
      var data=(raw&&raw.contents)?JSON.parse(raw.contents):raw;
      var result=data&&data.chart&&data.chart.result&&data.chart.result[0];
      if(!result)continue;
      var q=result.indicators&&result.indicators.quote&&result.indicators.quote[0];
      if(!q)continue;
      var highs=q.high,lows=q.low,closes=q.close,opens=q.open;
      if(!highs||highs.length<2)continue;
      // Get last completed session (second to last, or last if market closed)
      var idx=highs.length-1;
      // walk back to find a valid complete candle
      while(idx>0&&(!closes[idx]||!highs[idx]||!lows[idx]))idx--;
      var H=highs[idx],L=lows[idx],C=closes[idx];
      if(!H||!L||!C)continue;
      // Floor Trader Pivot formulas
      var P=(H+L+C)/3;
      var R1=2*P-L;
      var R2=P+(H-L);
      var R3=H+2*(P-L);
      var S1=2*P-H;
      var S2=P-(H-L);
      var S3=L-2*(H-P);
      return {ticker:inst.ticker,flagCls:inst.flagCls,dec:inst.dec,H:H,L:L,C:C,P:P,R1:R1,R2:R2,R3:R3,S1:S1,S2:S2,S3:S3,live:true};
    }catch(e){}
  }
  return null;
}

function fmtLvl(n,dec){
  if(!n&&n!==0)return '--';
  return Number(n).toLocaleString('en-US',{minimumFractionDigits:dec,maximumFractionDigits:dec});
}

function renderLiveLevels(pivots){
  var g=document.getElementById('lvl-grid');
  if(!g)return;
  if(!pivots||!pivots.length)return;

  g.innerHTML=pivots.map(function(p){
    if(!p)return '';
    var dec=p.dec||2;
    var rows=[
      {t:'R3',v:p.R3,cls:'lvl-r',op:0.5},
      {t:'R2',v:p.R2,cls:'lvl-r',op:0.75},
      {t:'R1',v:p.R1,cls:'lvl-r',op:1},
      {t:'Pivot',v:p.P,cls:'',op:1},
      {t:'S1',v:p.S1,cls:'lvl-s',op:1},
      {t:'S2',v:p.S2,cls:'lvl-s',op:0.75},
      {t:'S3',v:p.S3,cls:'lvl-s',op:0.5}
    ];
    var current=p.C;
    return '<div class="lvl-card">'
      +'<div style="display:flex;align-items:center;gap:6px;margin-bottom:var(--space-2)">'
      +'<span class="flag-badge '+p.flagCls+'" style="font-size:0.45rem">'+p.flagCls.replace('flag-','').toUpperCase()+'</span>'
      +'<span class="lvl-ticker">'+p.ticker+'</span>'
      +'<span style="font-family:var(--font-mono);font-size:0.6rem;color:var(--text-muted);margin-left:auto">Last: '+fmtLvl(current,dec)+'</span>'
      +'</div>'
      +rows.map(function(r){
        var isCurrent=current&&current>=r.v*0.999&&current<=r.v*1.001;
        var style='opacity:'+r.op+(isCurrent?';background:rgba(251,191,36,0.1);border-radius:4px':'');
        return '<div class="lvl-row" style="'+style+'">'
          +'<span class="lvl-type">'+r.t+(isCurrent?' ◀':'')+'</span>'
          +'<span class="lvl-price '+r.cls+'">'+fmtLvl(r.v,dec)+'</span>'
          +'</div>';
      }).join('')
      +'<div style="font-size:0.55rem;color:var(--text-faint);margin-top:6px">Floor Pivot · Prev H:'+fmtLvl(p.H,dec)+' L:'+fmtLvl(p.L,dec)+' C:'+fmtLvl(p.C,dec)+'</div>'
      +'</div>';
  }).join('');
}

async function loadPivotLevels(){
  var srcLabel=document.getElementById('lvl-src');
  if(srcLabel)srcLabel.textContent='Calculating...';

  var results=await Promise.allSettled(
    PIVOT_INSTRUMENTS.map(function(inst){return fetchPivotData(inst);})
  );

  var pivots=results.map(function(r){
    return (r.status==='fulfilled'&&r.value)?r.value:null;
  });

  var anyLive=pivots.some(function(p){return p&&p.live;});

  if(anyLive){
    renderLiveLevels(pivots.filter(function(p){return p;}));
    if(srcLabel)srcLabel.textContent='Yahoo Finance (live)';
  } else {
    // keep existing static levels
    if(srcLabel)srcLabel.textContent='Static fallback';
  }
}

// ===================== MASTER LOADER =====================
async function loadAllLiveExtras(){
  var results=await Promise.allSettled([
    fetchFearGreed(),
    fetchTreasuryYields(),
    fetchLiveCommodities(),
    loadPivotLevels()       // <-- pivot levels now auto-calculated
  ]);
  if(results[0].status==='fulfilled'&&results[0].value)applyFearGreed(results[0].value);
  if(results[1].status==='fulfilled'&&results[1].value)applyYields(results[1].value);
  if(results[2].status==='fulfilled'&&results[2].value){
    renderCommGrid('comm-grid');
    renderCommGrid('comm-grid-macro');
  }
}
