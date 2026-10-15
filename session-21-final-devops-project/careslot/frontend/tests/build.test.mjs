// Smoke tests on the production build (run after `npm run build`).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync } from 'node:fs';

test('vite produced dist/index.html with a module script', () => {
  assert.ok(existsSync('dist/index.html'));
  const html = readFileSync('dist/index.html', 'utf8');
  assert.match(html, /<script type="module"/);
  assert.match(html, /CareSlot/);
});

test('bundle calls the relative /api paths (no hard-coded backend host)', () => {
  const js = readdirSync('dist/assets').filter((f) => f.endsWith('.js'))
    .map((f) => readFileSync(`dist/assets/${f}`, 'utf8')).join('\n');
  assert.match(js, /\/api/);
  assert.doesNotMatch(js, /localhost:8000/);
});
