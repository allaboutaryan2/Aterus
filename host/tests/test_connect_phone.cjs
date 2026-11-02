// Pairing UI fixture tests only. No tunnel, browser, camera or phone claims.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
class Element{
  constructor(tag='div'){this.tag=tag;this.children=[];this.value='';this.hidden=false;this.disabled=false;this.textContent='';this.attributes={};this.events={};this.classList={contains:()=>false};}
  append(...items){this.children.push(...items);}prepend(...items){this.children.unshift(...items);}replaceChildren(...items){this.children=items;}
  setAttribute(k,v){this.attributes[k]=v;}removeAttribute(k){delete this.attributes[k];delete this[k];}
  addEventListener(k,v){this.events[k]=v;}
  querySelector(s){if(s==='.device-panel')return this.legacy;if(s.startsWith('button'))return this.button;return null;}
}
function setup(){
  const nodes={};const $=id=>nodes[id] ||= new Element();
  $('pair-form').button=new Element('button');$('devices-page').legacy=new Element();
  $('device-name').value='My phone';
  const calls=[],timers=[],intervals=[],history=[];let handler=async()=>({});let boots=0;
  const context=vm.createContext({URL,URLSearchParams,Date,document:{createElement:t=>new Element(t)},location:{hash:'#pair=ABC123',pathname:'/',search:''},history:{replaceState:(...v)=>history.push(v)},navigator:{clipboard:{writeText:async()=>{}}},$,state:{owner:true},api:async(...args)=>{calls.push(args);return handler(...args);},boot:async()=>{boots++;},setTimeout:fn=>{timers.push(fn);return timers.length;},setInterval:fn=>{intervals.push(fn);return intervals.length;}});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../public/connect-phone.js'),'utf8'),context);
  const panel=$('devices-page').children[0];
  return {$,panel,calls,timers,intervals,history,context,setHandler:fn=>handler=fn,get boots(){return boots;}};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  const f=setup();
  assert.equal(f.$('pair-code').value,'ABC123');
  assert.equal(f.history[0][2],'/','remove pairing secret fragment immediately');
  assert.equal(f.$('devices-page').legacy.hidden,true);
  let statuses=0;
  f.setHandler(async(url,body)=>{
    if(url==='/api/pair-request'){assert.equal(body.code,'ABC123');return {id:'r1',secret:'private-poll-secret',verification:'green river',expires_in:600};}
    if(url==='/api/pair-status'){assert.equal(body.secret,'private-poll-secret');return {state:++statuses===1?'pending':'approved'};}
    throw new Error('unexpected endpoint '+url);
  });
  await f.$('pair-form').onsubmit({preventDefault(){}});
  assert.equal(f.$('pair-code').value,'');
  assert.equal(f.$('pair-form').button.disabled,true);
  const wait=f.$('pair-form').children[0];
  assert.match(wait.textContent,/green river/);
  assert.doesNotMatch(wait.textContent,/private-poll-secret/);
  f.timers.shift()();await tick();assert.equal(f.boots,0);
  f.timers.shift()();await tick();assert.equal(f.boots,1);
  assert.equal(f.$('pair-form').button.disabled,false);
  assert.equal(f.calls.filter(([url])=>url==='/api/pair').length,0,'approval gate cannot call legacy direct pairing');
  const owner=setup();let ready=true;
  owner.setHandler(async url=>{
    if(url==='/api/connect')return {connection:{state:ready?'ready':'stopped',installed:true},public_origin:ready?'https://example.trycloudflare.com':''};
    if(url==='/api/pair-requests')return [{id:'request',name:'Phone',verification:'amber hill'}];
    if(url==='/api/pairing')return {code:'ONE',expires_in:600,url:'https://example.trycloudflare.com/#pair=ONE'};
    return {};
  });
  owner.$('devices-nav').events.click();await tick();
  const pairing=owner.panel.children[6],requests=owner.panel.children[7];
  const [create,qr,code,address]=pairing.children;
  assert.equal(create.disabled,false);
  await create.onclick();assert.equal(qr.hidden,false);assert.match(qr.src,/code=ONE/);assert.equal(address.hidden,false);
  const request=requests.children[2],label=request.children[2],approve=request.children[3].children[0];
  assert.equal(approve.disabled,true,'approval requires comparison confirmation');
  label.children[0].checked=true;label.children[0].onchange();assert.equal(approve.disabled,false);
  ready=false;owner.intervals[0]();await tick();
  assert.equal(qr.hidden,true,'stale QR hidden after tunnel disconnect');
  assert.equal(qr.src,undefined,'stale QR URL removed');
  assert.equal(create.disabled,true);assert.equal(address.hidden,true);assert.equal(code.textContent,'');
  const raced=setup();let resolvePairing, tunnelReady=true;
  raced.setHandler(async url=>{
    if(url==='/api/connect')return {connection:{state:tunnelReady?'ready':'stopped',installed:true},public_origin:tunnelReady?'https://example.trycloudflare.com':''};
    if(url==='/api/pair-requests')return [];
    if(url==='/api/pairing')return new Promise(resolve=>{resolvePairing=resolve;});
    if(url==='/api/connect/stop'){tunnelReady=false;return {connection:{state:'stopped',installed:true},public_origin:''};}
    return {};
  });
  raced.$('devices-nav').events.click();await tick();
  const racedPairing=raced.panel.children[6];
  const creating=racedPairing.children[0].onclick();await tick();
  await raced.panel.children[4].children[1].onclick();
  resolvePairing({code:'STALE',expires_in:600,url:'https://example.trycloudflare.com/#pair=STALE'});await creating;
  assert.equal(racedPairing.children[1].hidden,true,'in-flight QR response cannot resurrect stopped connection');
  assert.equal(racedPairing.children[2].textContent,'');
  const rejected=setup();
  rejected.setHandler(async url=>url==='/api/pair-request'?{id:'r',secret:'s',verification:'phrase',expires_in:600}:{state:'rejected'});
  await rejected.$('pair-form').onsubmit({preventDefault(){}});rejected.timers.shift()();await tick();
  assert.match(rejected.$('pair-form').children[0].textContent,/rejected/);assert.equal(rejected.$('pair-form').button.disabled,false);
  const source=fs.readFileSync(path.join(__dirname,'../public/connect-phone.js'),'utf8');
  assert.doesNotMatch(source,/localStorage|sessionStorage|caches\./,'pair request secret stays in memory');
  console.log('PASS: immediate fragment stripping, memory-only pending pairing, owner comparison gate, approved/rejected flow, disconnected QR invalidation (fixtures only)');
})().catch(error=>{console.error(error);process.exitCode=1;});
