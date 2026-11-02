'use strict';
(() => {
  // iOS keyboards shrink the visual viewport before layout viewport units.
  // Keep the terminal controls inside the visible area, without forcing focus.
  let viewportFrame = 0;
  function resizeViewport() {
    cancelAnimationFrame(viewportFrame);
    viewportFrame = requestAnimationFrame(() => {
      const viewport = window.visualViewport;
      document.documentElement.style.setProperty('--aterus-visible-height', `${viewport?.height || window.innerHeight}px`);
      document.documentElement.style.setProperty('--aterus-visible-top', `${viewport?.offsetTop || 0}px`);
    });
  }
  window.visualViewport?.addEventListener('resize', resizeViewport);
  window.visualViewport?.addEventListener('scroll', resizeViewport);
  window.addEventListener('orientationchange', resizeViewport);
  resizeViewport();
  const make = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const root = make('section', '', 'pwa-tools');
  root.setAttribute('aria-label', 'App installation and connection');
  const connection = make('p', '', 'pwa-connection');
  connection.setAttribute('role', 'status');
  connection.setAttribute('aria-live', 'polite');
  const install = make('button', 'Install Aterus', 'pwa-install');
  install.type = 'button';
  install.setAttribute('aria-expanded', 'false');
  const guidance = make('div', '', 'pwa-guidance');
  guidance.id = 'pwa-install-guide';
  guidance.hidden = true;
  install.setAttribute('aria-controls', guidance.id);
  const instructions = make('p');
  const closeGuide = make('button', 'Close instructions');
  closeGuide.type = 'button';
  guidance.append(instructions, closeGuide);
  const update = make('div', '', 'pwa-update');
  update.hidden = true;
  const updateText = make('p', 'An Aterus update is ready. Reload after finishing any unsent input. Running agents stay on your Mac.');
  const reload = make('button', 'Reload to update');
  reload.type = 'button';
  update.append(updateText, reload);
  root.append(connection, install, guidance, update);
  document.body.append(root);

  let installPrompt = null;
  let registration = null;
  let reloadRequested = false;
  const displayMode = window.matchMedia('(display-mode: standalone)');
  const isStandalone = () => displayMode.matches || navigator.standalone === true;
  const isAppleMobile = () => /iPhone|iPad|iPod/.test(navigator.userAgent || '') || ((navigator.platform === 'MacIntel') && navigator.maxTouchPoints > 1);
  function showGuide() {
    instructions.textContent = !window.isSecureContext
      ? 'To install on your phone, open the authenticated HTTPS address configured for your Mac, then pair this device. A local HTTP address cannot provide phone installation.'
      : isAppleMobile()
        ? 'On iPhone or iPad, open Aterus in Safari. Tap Share, then Add to Home Screen (or More → Add to Home Screen), and tap Add. Open the new Aterus icon and pair it with your Mac if requested. Keep your Mac awake and connected.'
        : 'Open your browser menu and choose Install Aterus or Add to Home Screen if offered. Installation support varies by browser. You can also bookmark this address. Keep your Mac awake and connected.';
    guidance.hidden = false;
    install.setAttribute('aria-expanded', 'true');
  }
  function installedState() {
    install.hidden = isStandalone();
    if (isStandalone()) {
      guidance.hidden = true;
      install.setAttribute('aria-expanded', 'false');
    }
  }
  install.addEventListener('click', async () => {
    if (!installPrompt) return showGuide();
    const prompt = installPrompt;
    installPrompt = null;
    install.disabled = true;
    try {
      await prompt.prompt();
      const result = await prompt.userChoice;
      if (result.outcome !== 'accepted') showGuide();
    } catch (_) {
      showGuide();
    } finally {
      install.disabled = false;
    }
  });
  closeGuide.addEventListener('click', () => {
    guidance.hidden = true;
    install.setAttribute('aria-expanded', 'false');
    install.focus();
  });
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault();
    installPrompt = event;
    installedState();
  });
  window.addEventListener('appinstalled', () => {
    installPrompt = null;
    install.hidden = true;
    guidance.hidden = true;
  });
  if (displayMode.addEventListener) displayMode.addEventListener('change', installedState);
  installedState();

  function connectionState(restored = false) {
    connection.hidden = navigator.onLine !== false && !restored;
    connection.textContent = navigator.onLine === false
      ? 'Offline. Your Mac sessions cannot be controlled until this device reconnects.'
      : 'Network connection restored. Open sessions will retry the Mac connection.';
    root.classList.toggle('pwa-offline', navigator.onLine === false);
  }
  window.addEventListener('offline', () => connectionState());
  window.addEventListener('online', () => connectionState(true));
  connectionState();

  function updateReady() {
    if (registration && registration.waiting && navigator.serviceWorker.controller) update.hidden = false;
  }
  reload.addEventListener('click', () => {
    if (!registration || !registration.waiting) return;
    reloadRequested = true;
    reload.disabled = true;
    reload.textContent = 'Applying update…';
    registration.waiting.postMessage({type: 'ATERUS_ACTIVATE_UPDATE'});
  });
  if ('serviceWorker' in navigator && window.isSecureContext) {
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (reloadRequested) window.location.reload();
    });
    navigator.serviceWorker.register('/sw.js').then(result => {
      registration = result;
      updateReady();
      registration.addEventListener('updatefound', () => {
        const worker = registration.installing;
        if (worker) worker.addEventListener('statechange', updateReady);
      });
    }).catch(() => {
      // Agent access remains usable when installation/offline shell is unavailable.
      install.title = 'Offline installation is unavailable in this browser';
    });
  }
})();
