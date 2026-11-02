const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const path=require('node:path');
const root=path.join(__dirname,'../dist');
const source=fs.readFileSync(root+'/install.js','utf8');
function fixture(agent='iPhone',standalone=false){
  const elements=new Map(),events={};
  const element=id=>{if(!elements.has(id))elements.set(id,{hidden:true,disabled:false,textContent:'',attrs:{},handlers:{},setAttribute(k,v){this.attrs[k]=v},addEventListener(k,f){this.handlers[k]=f},focus(){this.focused=true}});return elements.get(id)};
  const navigator={userAgent:agent,onLine:true,standalone};
  const context=vm.createContext({document:{getElementById:element},navigator,window:{isSecureContext:true,matchMedia:()=>({matches:standalone,addEventListener(){}}),addEventListener:(k,f)=>events[k]=f}});
  vm.runInContext(source,context);return {element,events,navigator};
}
(async()=>{
  const f=fixture();
  await f.element('install-app').handlers.click();
  assert.match(f.element('install-instructions').textContent,/Safari.*Share.*Add to Home Screen/);
  assert.equal(f.element('install-guide').hidden,false);
  f.element('close-install').handlers.click();
  assert.equal(f.element('install-app').attrs['aria-expanded'],'false');
  f.navigator.onLine=false;f.events.offline();assert.equal(f.element('connection-notice').hidden,false);
  f.navigator.onLine=true;f.events.online();assert.equal(f.element('connection-notice').hidden,true);
  let prompts=0;
  f.events.beforeinstallprompt({preventDefault(){},prompt:async()=>prompts++,userChoice:Promise.resolve({outcome:'dismissed'})});
  await f.element('install-app').handlers.click();await f.element('install-app').handlers.click();assert.equal(prompts,1);
  assert.equal(fixture('iPhone',true).element('install-app').hidden,true);
  const android=fixture('Android');await android.element('install-app').handlers.click();assert.match(android.element('install-instructions').textContent,/Chrome or Edge/);
  const handlers={},cached=[],self={location:{origin:'https://aterus.example'},addEventListener:(k,v)=>handlers[k]=v};
  vm.runInNewContext(fs.readFileSync(root+'/sw.js','utf8'),{self,URL,caches:{open:async()=>({addAll:async paths=>cached.push(...paths)})}});
  await new Promise((resolve,reject)=>handlers.install({waitUntil:p=>p.then(resolve,reject)}));
  assert(cached.includes('/index.html'));
  for(const url of ['https://aterus.example/api/sessions','https://host.example/','https://aterus.example/Aterus-mac-arm64.zip','https://aterus.example/?owner=private']){
    handlers.fetch({request:{url,method:'GET'},respondWith(){assert.fail('private or non-shell response intercepted')}});
  }
  const manifest=JSON.parse(fs.readFileSync(root+'/manifest.webmanifest'));
  assert.equal(manifest.display,'standalone');for(const icon of manifest.icons)assert(fs.existsSync(root+icon.src));
  const html=fs.readFileSync(root+'/index.html','utf8');assert.match(html,/viewport-fit=cover/);assert.match(html,/apple-touch-icon/);assert.match(html,/type="url"/);
  console.log('PASS: iPhone instructions, single-use Android install, standalone, offline/reconnect, public-only SW caching, manifest icons (fixtures)');
})().catch(e=>{console.error(e);process.exitCode=1});
