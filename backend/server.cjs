'use strict';
// Public distribution API. Never accepts desktop credentials, session traffic,
// arbitrary fetch targets or project files. Desktop APIs stay on paired hosts.
const http = require('node:http');
const releases = require('../dist/releases.json');
function createServer() {
  return http.createServer((req, res) => {
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('X-Content-Type-Options', 'nosniff');
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
      code = 404; body = {error: 'Not found'};
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
