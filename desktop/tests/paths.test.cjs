const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { containedPath } = require('../electron/paths.cjs');

test('only result paths inside the output root are accepted', () => {
  const root = path.resolve('data');
  assert.equal(containedPath(root, path.join(root, 'tving', 'contents.json')), path.join(root, 'tving', 'contents.json'));
  assert.throws(() => containedPath(root, path.join(root, '..', 'private.json')));
  assert.throws(() => containedPath(root, path.resolve('data-other', 'private.json')));
});
