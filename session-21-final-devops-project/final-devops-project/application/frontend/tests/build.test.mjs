// Tiny smoke test (node --test): the built bundle must exist and reference the JS entry.
import { test } from 'node:test';
import assert from 'node:assert';
import { readFileSync, existsSync } from 'node:fs';
test('dist/index.html is produced by vite build', () => {
  assert.ok(existsSync('dist/index.html'));
  assert.match(readFileSync('dist/index.html', 'utf8'), /<script type="module"/);
});
