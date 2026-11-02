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
