// UI logic fixtures; no claims of browser installation, offline runtime or iPhone verification.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../public/pwa.js'), 'utf8');
class Events {
  constructor() { this.events = {}; }
  addEventListener(name, handler) { (this.events[name] ||= []).push(handler); }
  async fire(name, event = {}) { for (const handler of this.events[name] || []) await handler(event); }
}
class Element extends Events {
  constructor(tag) { super(); this.tag = tag; this.children = []; this.attributes = {}; this.hidden = false; this.disabled = false; this.classList = {toggle() {}}; }
  append(...nodes) { this.children.push(...nodes); }
  setAttribute(key, value) { this.attributes[key] = value; }
  focus() { this.focused = true; }
}
function fixture(options = {}) {
  const body = new Element('body'), window = new Events(), mode = new Events(), sw = new Events(), registration = new Events();
  let reloads = 0, registrations = 0;
  mode.matches = !!options.standalone;
  window.matchMedia = () => mode;
  window.isSecureContext = options.secure !== false;
  window.location = {reload() { reloads++; }};
  registration.waiting = options.waiting || null;
  sw.controller = options.controller === false ? null : {};
  sw.register = async url => { assert.equal(url, '/sw.js'); registrations++; return registration; };
  const navigator = {onLine: true, userAgent: options.ios ? 'iPhone' : 'Test browser', serviceWorker: sw};
  const viewportValues = {};
  window.visualViewport = new Events();
  window.visualViewport.height = 720;
  window.visualViewport.offsetTop = 0;
  const context = vm.createContext({document: {body, documentElement: {style:{setProperty(k,v){viewportValues[k]=v}}}, createElement: tag => new Element(tag)}, window, navigator,
    requestAnimationFrame:fn=>{fn();return 1;},cancelAnimationFrame(){}});
  vm.runInContext(source, context);
  const root = body.children[0];
  const [connection, install, guide, update] = root.children;
  return {window, mode, sw, registration, navigator, connection, install, guide, update, viewportValues, get reloads() {return reloads;}, get registrations() {return registrations;}};
}
const tick = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  const ios = fixture({ios: true});
  ios.window.visualViewport.height = 360;
  ios.window.visualViewport.offsetTop = 20;
  await ios.window.visualViewport.fire('resize');
  assert.equal(ios.viewportValues['--aterus-visible-height'],'360px');
  assert.equal(ios.viewportValues['--aterus-visible-top'],'20px');
  await ios.install.fire('click');
  assert.equal(ios.guide.hidden, false);
  assert.match(ios.guide.children[0].textContent, /Safari.*Add to Home Screen/);
  assert.equal(ios.install.attributes['aria-expanded'], 'true');
  await ios.guide.children[1].fire('click');
  assert.equal(ios.guide.hidden, true);
  assert.equal(ios.install.focused, true);
  const installed = fixture({standalone: true});
  assert.equal(installed.install.hidden, true);
  const insecure = fixture({secure: false});
  await insecure.install.fire('click');
  assert.match(insecure.guide.children[0].textContent, /HTTPS/);
  assert.equal(insecure.registrations, 0);

  const browser = fixture();
  let prevented = false, prompted = 0;
  await browser.window.fire('beforeinstallprompt', {preventDefault() { prevented = true; }, prompt: async () => {prompted++;}, userChoice: Promise.resolve({outcome: 'dismissed'})});
  assert.equal(prevented, true);
  await browser.install.fire('click');
  assert.equal(prompted, 1);
  await browser.install.fire('click');
  assert.equal(prompted, 1, 'a deferred install event can only be consumed once');
  assert.equal(browser.guide.hidden, false);
  browser.navigator.onLine = false;
  await browser.window.fire('offline');
  assert.equal(browser.connection.hidden, false);
  assert.match(browser.connection.textContent, /cannot be controlled/);
  browser.navigator.onLine = true;
  await browser.window.fire('online');
  assert.match(browser.connection.textContent, /retry the Mac connection/);

  const messages = [];
  const upgrade = fixture({waiting: {postMessage: message => messages.push(message)}});
  await tick();
  assert.equal(upgrade.update.hidden, false);
  await upgrade.sw.fire('controllerchange');
  assert.equal(upgrade.reloads, 0, 'an unsolicited controller change must never interrupt input');
  await upgrade.update.children[1].fire('click');
  assert.equal(messages.length, 1);
  assert.equal(messages[0].type, 'ATERUS_ACTIVATE_UPDATE');
  assert.equal(upgrade.reloads, 0, 'wait for the selected worker to activate before reloading');
  await upgrade.sw.fire('controllerchange');
  assert.equal(upgrade.reloads, 1);
  const firstInstall = fixture({waiting: {postMessage() {}}, controller: false});
  await tick();
  assert.equal(firstInstall.update.hidden, true, 'first install is not an update');
  console.log('PASS: PWA install guidance, deferred prompt single-use, standalone detection, offline/reconnect notice, intentional update reload (fixtures only)');
})().catch(error => {console.error(error); process.exitCode = 1;});
