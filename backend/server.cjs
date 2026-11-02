'use strict';
// Public website and distribution API. Never accepts desktop credentials, session traffic,
// arbitrary fetch targets or project files. Desktop APIs stay on paired hosts.
const http = require('node:http');
const fs = require('node:fs/promises');
const path = require('node:path');
const releases = require('../dist/releases.json');
const publicRoot = path.join(__dirname, '../dist');
// Only these published files are served; never expose repository or host files.
const assets = new Map([
  ['index.html', 'text/html; charset=utf-8'],
  ['style.css', 'text/css; charset=utf-8'],
  ...['connect.js', 'install.js', 'sw.js'].map(file => [file, 'text/javascript; charset=utf-8']),
  ['manifest.webmanifest', 'application/manifest+json'],
  ['icon.svg', 'image/svg+xml'],
  ...['icon-180.png', 'icon-192.png', 'icon-512.png'].map(file => [file, 'image/png']),
  ['releases.json', 'application/json; charset=utf-8'],
  ...['CONNECT.md', 'RELEASE-NOTES.md'].map(file => [file, 'text/plain; charset=utf-8']),
  ...['Aterus-mac-arm64.zip', 'Aterus-host.zip'].map(file => [file, 'application/zip'])
]);
function createServer() {
  return http.createServer(async (req, res) => {
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Referrer-Policy', 'no-referrer');
    res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
    // These responses contain public constants only; no cookie authentication.
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'");
    let code = 200, body;
    if (!['GET', 'HEAD'].includes(req.method)) {
      code = 405; res.setHeader('Allow', 'GET, HEAD'); body = {error: 'Method not allowed'};
    } else if (req.url === '/healthz') {
      body = {status: 'ok', service: 'aterus-public-api', relay: false};
    } else if (req.url === '/v1/releases') {
      body = releases;
    } else {
      const file = req.url === '/' ? 'index.html' : req.url.slice(1);
      if (req.url.startsWith('/') && assets.has(file)) {
        try {
          const handle = await fs.open(path.join(publicRoot, file), 'r');
          const stat = await handle.stat();
          res.setHeader('Content-Type', assets.get(file));
          res.setHeader('Content-Length', stat.size);
          res.setHeader('Cache-Control', 'no-cache');
          res.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; manifest-src 'self'; worker-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'; upgrade-insecure-requests");
          if (file.endsWith('.zip')) res.setHeader('Content-Disposition', `attachment; filename="${file}"`);
          if (req.method === 'HEAD') {
            await handle.close();
            res.writeHead(200); res.end();
          } else {
            handle.createReadStream().on('error', () => res.destroy()).pipe(res);
          }
          return;
        } catch (error) {
          code = error.code === 'ENOENT' ? 404 : 500;
          body = {error: code === 404 ? 'Not found' : 'File unavailable'};
        }
      } else {
        code = 404; body = {error: 'Not found'};
      }
    }
    res.writeHead(code);
    res.end(req.method === 'HEAD' ? undefined : JSON.stringify(body));
  });
}
if (require.main === module) {
  const server = createServer();
  server.requestTimeout = 15000;
  server.headersTimeout = 10000;
  server.listen(Number(process.env.PORT || 10000), '0.0.0.0', () => console.log('Aterus public API listening'));
  for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => server.close());
}
module.exports = {createServer};
