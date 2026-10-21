const path = require('node:path');

function containedPath(root, candidate) {
  if (typeof candidate !== 'string') throw new Error('Invalid result path');
  const resolved = path.resolve(candidate);
  const relative = path.relative(path.resolve(root), resolved);
  if (relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new Error('결과 저장 폴더 밖의 경로는 열 수 없습니다.');
  }
  return resolved;
}

module.exports = { containedPath };
