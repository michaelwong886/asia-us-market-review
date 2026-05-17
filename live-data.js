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
        // historical
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
  // main score
  var scoreEl=document.querySelector('#tab-sentiment .kpi-fg-score');
  var ratingEl=document.querySelector('#tab-sentiment .kpi-fg-rating');
  var barEl=document.querySelector('#tab-sentiment .fg-bar-fill');
  var w1El=document.querySelector('#fg-w1');
  var m1El=document.querySelector('#fg-m1');
  var srcEl=document.getElementById('fg-src');
  // color
  var color=d.score>=60?'var(--up)':d.score<=40?'var(--down)':'var(--warn)';
  if(scoreEl){scoreEl.textContent=d.score;scoreEl.style.color=color;}
  if(ratingEl){ratingEl.textContent=d.rating;ratingEl.style.color=color;}
  if(barEl){barEl.style.width=d.score+'%';barEl.style.background=color;}
  if(w1El&&d.w1!==null)w1El.textContent=d.w1;
  if(m1El&&d.m1!==null)m1El.textContent=d.m1;
  if(srcEl)srcEl.textContent=d.live?'CNN (live)':'Static';
}

// ===================== US TREASURY YIELDS — US Treasury XML feed =====================
async function fetchTreasuryYields(){
  // Treasury daily yield curve XML
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
      // parse XML
      var parser=new DOMParser();
      var xml=parser.parseFromString(text,'text/xml');
      var entries=xml.querySelectorAll('entry');
      if(!entries||!entries.length)continue;
      // get last entry
      var last=entries[entries.length-1];
      function yv(tag){var el=last.querySelector(tag);return el?parseFloat(el.textContent):null;}
      var y2=yv('BC_2YEAR');var y5=yv('BC_5YEAR');var y10=yv('BC_10YEAR');var y30=yv('BC_30YEAR');
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

// ===================== COMMODITIES — Yahoo Finance via proxy =====================
// Symbols: GC=F (Gold), SI=F (Silver), CL=F (WTI), BZ=F (Brent), HG=F (Copper), PL=F (Platinum), PA=F (Palladium)
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
  var any=false;
  var updated=[];
  for(var i=0;i<COMM_YF_MAP.length;i++){
    var r=results[i];
    var base=COMM_YF_MAP[i];
    if(r.status==='fulfilled'&&r.value&&r.value.c>0){
      updated.push({icon:base.icon,name:base.name,price:r.value.c,pct:r.value.dp,unit:base.unit,live:true});
      any=true;
    } else {
      // keep fallback
      var fb=window.COMMODITIES?window.COMMODITIES.find(function(x){return x.name===base.name;}):null;
      updated.push(fb?{icon:base.icon,name:base.name,price:fb.price,pct:fb.pct,unit:base.unit,live:false}
        :{icon:base.icon,name:base.name,price:0,pct:0,unit:base.unit,live:false});
    }
  }
  if(any)window.COMMODITIES=updated;
  return any?updated:null;
}

async function loadAllLiveExtras(){
  // Run all 3 in parallel
  var results=await Promise.allSettled([
    fetchFearGreed(),
    fetchTreasuryYields(),
    fetchLiveCommodities()
  ]);
  // Fear & Greed
  if(results[0].status==='fulfilled'&&results[0].value)applyFearGreed(results[0].value);
  // Yields
  if(results[1].status==='fulfilled'&&results[1].value)applyYields(results[1].value);
  // Commodities — re-render grids
  if(results[2].status==='fulfilled'&&results[2].value){
    renderCommGrid('comm-grid');
    renderCommGrid('comm-grid-macro');
  }
}
