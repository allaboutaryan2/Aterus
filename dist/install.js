'use strict';
(() => {
  const byId = id => document.getElementById(id);
  const install = byId('install-app'), guide = byId('install-guide');
  const mode = window.matchMedia('(display-mode: standalone)');
  let prompt = null, registration = null, reload = false;
  function standalone() {
    if (mode.matches || navigator.standalone === true) {
      install.hidden = true; guide.hidden = true;
    }
  }
  function instructions() {
    const apple = /iPhone|iPad|iPod/.test(navigator.userAgent || '') ||
      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    byId('install-instructions').textContent = !window.isSecureContext
      ? 'Installation requires HTTPS. Open the published Aterus website in your browser.'
      : apple
        ? 'On iPhone or iPad: open this page in Safari, tap Share, choose Add to Home Screen, then Add. For terminal control, repeat on your paired computer’s HTTPS page. If opened inside another app, open in Safari first.'
        : 'In Chrome or Edge, open the browser menu and choose Install Aterus or Add to Home Screen if offered. For terminal control, install your paired computer’s HTTPS page too.';
    guide.hidden = false;
    install.setAttribute('aria-expanded', 'true');
  }
  install.addEventListener('click', async () => {
    if (!prompt) return instructions();
    const current = prompt; prompt = null; install.disabled = true;
    try {
      await current.prompt();
      if ((await current.userChoice).outcome !== 'accepted') instructions();
    } catch (_) { instructions(); }
    finally { install.disabled = false; }
  });
  byId('close-install').addEventListener('click', () => {
    guide.hidden = true; install.setAttribute('aria-expanded', 'false'); install.focus();
  });
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault(); prompt = event; standalone();
  });
  window.addEventListener('appinstalled', () => { prompt = null; install.hidden = true; guide.hidden = true; });
  mode.addEventListener?.('change', standalone);
  standalone();
  function connection() {
    const offline = navigator.onLine === false;
    byId('connection-notice').hidden = !offline;
    byId('connection-notice').textContent = offline
      ? 'You’re offline. Setup guidance is available; reconnect to open your computer or download the host.' : '';
  }
  window.addEventListener('offline', connection);
  window.addEventListener('online', connection);
  connection();
  function updateReady() {
    if (registration?.waiting && navigator.serviceWorker.controller) byId('update-notice').hidden = false;
  }
  byId('apply-update').addEventListener('click', () => {
    if (!registration?.waiting) return;
    reload = true; byId('apply-update').disabled = true;
    registration.waiting.postMessage({type:'ATERUS_PORTAL_UPDATE'});
  });
  if ('serviceWorker' in navigator && window.isSecureContext) {
    navigator.serviceWorker.addEventListener('controllerchange', () => { if (reload) window.location.reload(); });
    navigator.serviceWorker.register('/sw.js').then(result => {
      registration = result; updateReady();
      result.addEventListener('updatefound', () => {
        result.installing?.addEventListener('statechange', updateReady);
      });
    }).catch(() => { install.title = 'Offline installation is unavailable in this browser'; });
  }
})();
