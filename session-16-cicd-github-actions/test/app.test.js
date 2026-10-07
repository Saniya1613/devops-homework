// Unit tests – Node.js built-in test runner (node --test), no extra test framework needed.
const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const { createApp } = require('../src/app');

let server;
let base;

before(async () => {
  server = createApp().listen(0);
  await new Promise((resolve) => server.once('listening', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});

after(() => server.close());

test('GET / returns app info', async () => {
  const res = await fetch(`${base}/`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.app, 'session16-cicd-demo');
});

test('GET /health returns ok', async () => {
  const res = await fetch(`${base}/health`);
  assert.equal(res.status, 200);
  assert.equal((await res.json()).status, 'ok');
});

test('GET /api/add adds two numbers', async () => {
  const res = await fetch(`${base}/api/add?a=10&b=32`);
  assert.equal((await res.json()).result, 42);
});

test('GET /api/add rejects non-numbers', async () => {
  const res = await fetch(`${base}/api/add?a=x&b=1`);
  assert.equal(res.status, 400);
});

test('POST /api/tasks creates a task', async () => {
  const res = await fetch(`${base}/api/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: 'Write CI pipeline' }),
  });
  assert.equal(res.status, 201);
  const task = await res.json();
  assert.equal(task.title, 'Write CI pipeline');
  assert.equal(task.done, false);
});

test('POST /api/tasks without title returns 400', async () => {
  const res = await fetch(`${base}/api/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  assert.equal(res.status, 400);
});

test('PATCH /api/tasks/:id/done marks a task done', async () => {
  const res = await fetch(`${base}/api/tasks/1/done`, { method: 'PATCH' });
  assert.equal(res.status, 200);
  assert.equal((await res.json()).done, true);
});

test('PATCH unknown task returns 404', async () => {
  const res = await fetch(`${base}/api/tasks/999/done`, { method: 'PATCH' });
  assert.equal(res.status, 404);
});
