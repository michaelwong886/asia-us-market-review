// Live Data Loader
// Loads: Fear & Greed (CNN), Treasury Yields (US Treasury XML), Commodities (Yahoo Finance)

var COMM_SYMBOLS=[
  {sym:'CL=F',icon:'&#9981;',name:'WTI Crude',unit:'USD/bbl'},
  {sym:'BZ=F',icon:'&#9981;',name:'Brent Crude',unit:'USD/bbl'},
  {sym:'GC=F',icon:'&#129351;',name:'Gold',unit:'USD/oz'},
  {sym:'SI=F',icon:'&#129352;',name:'Silver',unit:'USD/oz'},
  {sym:'HG=F',icon:'&#128992;',name:'Copper',unit:'USD/lb'},
  {sym:'PL=F',icon:'&#9898;',name:'Platinum',unit:'USD/oz'},
  {sym:'PA=F',icon:'&#128295;',name:'Palladium',unit:'USD/oz'},
  {sym:'ALI=F',icon:'&#128295;',name:'Aluminum',unit:'USD/t'}
];

var LD_PROXIES=[
  function(u){return 'https://corsproxy.io/?'+encodeURIComponent(u);},
  function(u){return 'https://api.allorigins.win/get?url='+encodeURIComponent(u);}
];

async function ldFetch(url){
  for(var i=0;i<LD_PROXIES.length;i++){
    try{
      var r=await fetch(LD_PROXIES[i](url),{signal:AbortSignal.timeout(8000)});
      var j=await r.json();
      return (j&&j.contents)?JSON.parse(j.contents):j;
    }catch(e){}
  }
  return null;
}

async function loadFearGreed(){
  var data=await ldFetch('https://production.dataviz.cnn.io/index/fearandgreed/graphdata');
  if(!data||!data.fear_and_greed)return;
  var fg=data.fear_and_greed;
  var score=parseFloat(fg.score);
  if(isNaN(score))return;
  var label=score>=75?'Extreme Greed':score>=55?'Greed':score>=45?'Neutral':score>=25?'Fear':'Extreme Fear';
  var color=score>=55?'var(--warn)':score>=45?'var(--text-muted)':'var(--down)';
  var cards=document.querySelectorAll('#tab-sentiment .card');
  for(var c=0;c<cards.length;c++){
    var big=cards[c].querySelector('[style*="3rem"]');
    if(!big)continue;
    big.textContent=Math.round(score);
    big.style.color=color;
    var lbl=big.nextElementSibling;
    if(lbl){lbl.textContent=label;lbl.style.color=color;}
    var bar=cards[c].querySelector('[style*="height:100%"]');
    if(bar)bar.style.width=Math.round(score)+'%';
    var hw=cards[c].querySelectorAll('[style*="font-weight:700"]');
    var hist=[fg.previous_close,fg.previous_1_week,fg.previous_1_month,fg.previous_1_year];
    for(var h=0;h<hw.length&&h<hist.length;h++){
      if(hist[h]!=null)hw[h].textContent=Math.round(parseFloat(hist[h]));
    }
    break;
  }
  console.log('[LiveData] F&G: '+score+' '+label);
}

async function loadTreasuryYields(){
  var ym=new Date().toISOString().slice(0,7).replace('-','');
  var url='https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value='+ym;
  for(var i=0;i<LD_PROXIES.length;i++){
    try{
      var r=await fetch(LD_PROXIES[i](url),{signal:AbortSignal.timeout(10000)});
      var j=await r.json();
      var xmlStr=(j&&j.contents)?j.contents:null;
      if(!xmlStr)continue;
      var xml=new DOMParser().parseFromString(xmlStr,'application/xml');
      var entries=xml.querySelectorAll('entry');
      if(!entries.length)continue;
      var latest=entries[entries.length-1];
      var g=function(t){var e=latest.querySelector(t);return e?parseFloat(e.textContent):null;};
      var y2=g('BC_2YEAR'),y5=g('BC_5YEAR'),y10=g('BC_10YEAR'),y30=g('BC_30YEAR');
      if(!y10)continue;
      var yg=document.getElementById('yield-grid');
      if(yg){
        var items=[{l:'2Y',v:y2},{l:'5Y',v:y5},{l:'10Y',v:y10},{l:'30Y',v:y30}];
        yg.innerHTML=items.map(function(m){
          if(!m.v)return '';
          return '<div class="macro-item"><div class="macro-label">'+m.l+'</div><div class="macro-value">'+m.v.toFixed(2)+'%</div><div class="macro-chg" style="color:var(--accent)">Live</div></div>';
        }).join('');
      }
      console.log('[LiveData] Yields: 2Y='+y2+' 10Y='+y10+' 30Y='+y30);
      return;
    }catch(e){}
  }
}

async function ldYFQuote(sym){
  var url='https://query1.finance.yahoo.com/v8/finance/chart/'+encodeURIComponent(sym)+'?interval=1d&range=2d';
  var proxies=[
    'https://corsproxy.io/?'+encodeURIComponent(url),
    'https://api.allorigins.win/get?url='+encodeURIComponent(url),
    'https://thingproxy.freeboard.io/fetch/'+url
  ];
  for(var i=0;i<proxies.length;i++){
    try{
      var r=await fetch(proxies[i],{signal:AbortSignal.timeout(7000)});
      var j=await r.json();
      var d=(j&&j.contents)?JSON.parse(j.contents):j;
      var res=d&&d.chart&&d.chart.result&&d.chart.result[0];
      if(!res)continue;
      var m=res.meta;
      var c=m.regularMarketPrice||0;
      var prev=m.chartPreviousClose||m.previousClose||0;
      if(c<=0)continue;
      return {c:c,dp:prev>0?(c-prev)/prev*100:0};
    }catch(e){}
  }
  return null;
}

async function loadCommoditiesLive(){
  var results=await Promise.allSettled(COMM_SYMBOLS.map(function(c){return ldYFQuote(c.sym);}));
  var anyLive=false;
  for(var i=0;i<COMM_SYMBOLS.length;i++){
    var r=results[i];
    if(r.status==='fulfilled'&&r.value&&r.value.c>0){
      anyLive=true;
      if(typeof COMMODITIES!=='undefined'&&COMMODITIES[i]){
        COMMODITIES[i].price=r.value.c;
        COMMODITIES[i].pct=r.value.dp;
      }
    }
  }
  if(!anyLive)return;
  if(typeof renderCommGrid==='function'){renderCommGrid('comm-grid');renderCommGrid('comm-grid-macro');}
  if(typeof buildTicker==='function')buildTicker();
  console.log('[LiveData] Commodities updated live');
}

window.addEventListener('load',function(){
  setTimeout(function(){
    loadFearGreed();
    loadTreasuryYields();
    loadCommoditiesLive();
  },2500);
});
