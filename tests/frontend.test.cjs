const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../frontend/js/api.js'), 'utf8');
function api(fetch) {
  const context = vm.createContext({ fetch, AbortSignal, TypeError });
  vm.runInContext(source, context);
  return context;
}
const json = (value, status = 200) => new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': 'application/json' },
});

test('edits use stable NIM and the displayed version', async () => {
  let request;
  const client = api(async (url, options) => {
    request = { url, options };
    return json({ name: 'Updated' });
  });
  await client.apiUpdateMember({ nim: '123', _version: 'version-before-edit' }, { name: 'Updated' });
  assert.equal(request.url, '/api/members?nim=123');
  assert.equal(request.options.headers['If-Match'], '"version-before-edit"');
  assert.equal(request.options.method, 'PUT');
  assert.equal(JSON.parse(request.options.body).name, 'Updated');
  assert.ok(request.options.signal instanceof AbortSignal);
});

test('delete uses stable identity and stale-version protection', async () => {
  let request;
  const client = api(async (url, options) => {
    request = { url, options };
    return json({ message: 'Deleted' });
  });
  await client.apiDeleteMember({ nim: '456', _version: 'original' });
  assert.equal(request.url, '/api/members?nim=456');
  assert.equal(request.options.headers['If-Match'], '"original"');
  assert.equal(request.options.method, 'DELETE');
});

test('a missing version cannot send an unguarded update', async () => {
  let called = false;
  const client = api(async () => { called = true; return json({}); });
  await assert.rejects(client.apiUpdateMember({ nim: '123' }, {}), /muat ulang/);
  assert.equal(called, false);
});

test('conflict and storage messages reach the user', async () => {
  for (const status of [409, 502, 503, 504]) {
    const client = api(async () => json({ error: 'Specific recovery instructions' }, status));
    await assert.rejects(client.apiDeleteMember({ nim: '123', _version: 'old' }), /Specific recovery instructions/);
  }
});

test('proxy HTML failures use a fallback without hiding backend JSON errors', async () => {
  const client = api(async () => new Response('<html>Bad Gateway</html>', {
    status: 502, headers: { 'Content-Type': 'text/html' },
  }));
  await assert.rejects(client.apiGetGithubRepos('demo'), /melalui proxy \(HTTP 502\)/);
});

test('malformed member responses do not look like an empty team', async () => {
  const client = api(async () => json({ unexpected: true }));
  await assert.rejects(client.apiGetMembers(), /format daftar anggota/);
});

test('timeouts have a useful error and the next request can recover', async () => {
  let first = true;
  const client = api(async () => {
    if (first) { first = false; throw { name: 'TimeoutError' }; }
    return json([]);
  });
  await assert.rejects(client.apiGetMembers(), /terlalu lama/);
  assert.equal((await client.apiGetMembers()).length, 0);
});

test('dialog padding keeps the form open; backdrop closes it; busy forms stay open', () => {
  const client = api(async () => json([]));
  const events = {};
  const controls = [{ disabled: false }, { disabled: false }];
  let closes = 0;
  const dialog = {
    dataset: {},
    addEventListener: (type, handler) => { events[type] = handler; },
    getBoundingClientRect: () => ({ left: 100, right: 400, top: 100, bottom: 400 }),
    close: () => { closes++; },
    setAttribute: () => {},
    querySelectorAll: () => controls,
  };
  client.configureDialog(dialog);
  events.click({ target: dialog, clientX: 110, clientY: 110 });
  assert.equal(closes, 0);
  events.click({ target: dialog, clientX: 10, clientY: 10 });
  assert.equal(closes, 1);
  client.setDialogBusy(dialog, true);
  assert.ok(controls.every(control => control.disabled));
  events.click({ target: dialog, clientX: 10, clientY: 10 });
  assert.equal(closes, 1);
  let prevented = false;
  events.cancel({ preventDefault() { prevented = true; } });
  assert.ok(prevented);
  client.setDialogBusy(dialog, false);
  assert.ok(controls.every(control => !control.disabled));
});
