const {test} = require('node:test');
const assert = require('node:assert/strict');
const {createServer} = require('../backend/server.cjs');
test('public API has health/release data, no private agent endpoints', async () => {
  const server = createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = 'http://127.0.0.1:' + server.address().port;
  try {
    const health = await fetch(origin + '/healthz');
    assert.equal(health.status, 200);
    assert.equal((await health.json()).relay, false);
    assert.equal(health.headers.get('cache-control'), 'no-store');
    const releases = await (await fetch(origin + '/v1/releases')).json();
    assert.equal(releases.stage, 'development');
    assert.equal((await fetch(origin + '/api/sessions')).status, 404);
    assert.equal((await fetch(origin + '/healthz', {method:'POST',body:'private'})).status,405);
    assert.equal((await fetch(origin + '/healthz?token=secret')).status,404);
  } finally { await new Promise(resolve => server.close(resolve)); }
});
test('Render serves the website, install assets and downloads without exposing private paths', async () => {
  const server = createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = 'http://127.0.0.1:' + server.address().port;
  try {
    const home = await fetch(origin + '/');
    assert.equal(home.status, 200);
    assert.match(home.headers.get('content-type'), /text\/html/);
    assert.match(home.headers.get('content-security-policy'), /script-src 'self'/);
    assert.match(await home.text(), /Your desk/);
    for (const file of ['index.html', 'style.css', 'connect.js', 'install.js', 'sw.js', 'manifest.webmanifest', 'icon.svg', 'icon-180.png', 'icon-192.png', 'icon-512.png', 'CONNECT.md', 'RELEASE-NOTES.md', 'releases.json']) {
      const response = await fetch(origin + '/' + file);
      assert.equal(response.status, 200, file);
      assert.ok((await response.arrayBuffer()).byteLength, file);
    }
    for (const file of ['Aterus-host.zip', 'Aterus-mac-arm64.zip']) {
      const head = await fetch(origin + '/' + file, {method: 'HEAD'});
      assert.equal(head.status, 200);
      assert.equal(head.headers.get('content-type'), 'application/zip');
      assert.ok(Number(head.headers.get('content-length')) > 0);
      assert.match(head.headers.get('content-disposition'), /attachment/);
      assert.equal(await head.text(), '');
      const download = await fetch(origin + '/' + file);
      const data = Buffer.from(await download.arrayBuffer());
      assert.equal(data.length, Number(head.headers.get('content-length')));
      assert.equal(data.subarray(0, 2).toString(), 'PK');
    }
    for (const target of ['/.git/config', '/host/aterus.py', '/backend/server.cjs', '/%2e%2e%2fpackage.json', '/missing.js', '/?token=private', '/style.css?token=private']) {
      assert.equal((await fetch(origin + target)).status, 404, target);
    }
    assert.equal((await fetch(origin + '/', {method: 'POST', body: 'private'})).status, 405);
  } finally { await new Promise(resolve => server.close(resolve)); }
});
