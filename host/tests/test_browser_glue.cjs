// Browser glue fixtures only: no DOM rendering, real xterm, network or agent claims.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
class Element {
  constructor(){this.value='';this.textContent='';this.disabled=false;this.open=false;this.children=[];this.classList={add(){},remove(){},toggle(){},contains(){return false}};}
  addEventListener(){} append(...items){this.children.push(...items);} replaceChildren(...items){this.children=items;}
  showModal(){this.open=true;} close(){this.open=false;} querySelector(){return null;}
}
const elements={};
const context=vm.createContext({console,Uint8Array,TextDecoder,AbortController,URLSearchParams,
  document:{getElementById:id=>elements[id] ||= new Element(),createElement:()=>new Element(),querySelectorAll:()=>[]},
  location:{hash:'',pathname:'/'},history:{replaceState(){}},navigator:{},window:{isSecureContext:false},
  setInterval:()=>1,clearInterval(){},setTimeout:()=>1,clearTimeout(){},requestAnimationFrame(){},
  atob:s=>Buffer.from(s,'base64').toString('binary'),btoa:s=>Buffer.from(s,'binary').toString('base64'),
  fetch:()=>new Promise(()=>{})});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../public/app.js'),'utf8'),context);
const run=code=>vm.runInContext(code,context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  run("selected={agent:'opencode',controls:{variant:'legacy-go',submit:'\\x13'}};");
  assert.equal(context.promptInput('hello'),'hello\x13');
  run("selected={agent:'opencode',controls:{variant:'modern',submit:'\\r'}};");
  assert.equal(context.promptInput('hello'),'hello\r');
  run("selected={agent:'claude'};");
  assert.equal(context.promptInput('hello'),'hello\r');
  const requests=[];
  context.fetch=(url,options)=>new Promise(resolve=>requests.push({url,options,resolve}));
  run("selected={id:'first',state:'running'}; generation=1;");
  const first=context.send('a'), second=context.send('b');
  await tick();assert.equal(requests.length,1,'input must serialize');
  assert.equal(JSON.parse(requests[0].options.body).text,'a');
  requests[0].resolve({ok:true,json:async()=>({ok:true})}); await first; await tick();
  assert.equal(requests.length,2);
  assert.equal(JSON.parse(requests[1].options.body).text,'b');
  requests[1].resolve({ok:true,json:async()=>({ok:true})});await second;

  const third=context.send('c');const stale=context.send('do not deliver');stale.catch(()=>{});
  await tick();run("generation++; selected={id:'second',state:'running'};");
  requests[2].resolve({ok:true,json:async()=>({ok:true})});await third;
  await assert.rejects(stale,/input discarded/);assert.equal(requests.length,3);

  let written, finish;
  context.testTerminal={options:{},write:(bytes,callback)=>{written=bytes;finish=callback;}};
  run("terminal=testTerminal;offset=0;polling=false;");
  const raw=Buffer.from('\x1b[2J\x1b[Hred\x1b[31m\xe2','binary');
  context.fetch=async()=>({ok:true,json:async()=>({data:raw.toString('base64'),offset:raw.length,state:'running'})});
  const output=context.pollOutput();await tick();
  assert.deepEqual(Buffer.from(written),raw,'ANSI bytes must reach xterm unchanged');
  assert.equal(run('offset'),0,'commit offset only after renderer consumes bytes');
  finish();await output;assert.equal(run('offset'),raw.length);
  const full=Buffer.alloc(131072);for(let i=0;i<full.length;i++)full[i]=i%256;
  context.fetch=async()=>({ok:true,json:async()=>({data:full.toString('base64'),offset:raw.length+full.length,state:'running'})});
  const large=context.pollOutput();await tick();
  assert.deepEqual(Buffer.from(written),full,'all byte values and a full output chunk must reach xterm unchanged');
  finish();await large;
  const consumed=raw.length+full.length;
  assert.equal(run('offset'),consumed);
  context.fetch=async()=>{throw new Error('offline')};await context.pollOutput();
  assert.equal(run('offset'),consumed,'reconnect keeps last consumed offset');
  assert.match(elements['terminal-error'].textContent,/reconnecting/);
  context.fetch=async()=>({ok:true,json:async()=>({data:'',offset:consumed,state:'stopped'})});
  await context.pollOutput();
  assert.equal(elements['terminal-input'].disabled,true);
  assert.equal(elements['send-input'].disabled,true);
  assert.equal(elements['stop-session'].disabled,true);
  await assert.rejects(context.send('after exit'),/no longer running/);
  console.log('PASS: ordered input, stale-session input rejection, raw VT byte delivery, consumed offsets, reconnect offset preservation (fixtures only)');
})().catch(error=>{console.error(error);process.exitCode=1;});
