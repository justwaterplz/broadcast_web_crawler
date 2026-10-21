const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { loadSelectedResponses } = require('../electron/cjenm-files.cjs');

test('CJ ENM file picker accepts BOM text and preserves original JSON values regardless of selection order', () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'broadcast-cjenm-files-'));
  const program = { resultCd: '0000', result: { data: { pgmSeq: 1, pgmNm: '작품', extra: [null, false, '001', 0] } } };
  const people = { resultCd: '0000', result: { data: { pgmSeq: 1, pgmNm: '작품', detailPrsnInfoList: [] } } };
  const p = path.join(folder, 'program.txt'), c = path.join(folder, 'people.json');
  fs.writeFileSync(p, '\ufeff' + JSON.stringify(program)); fs.writeFileSync(c, JSON.stringify(people));
  assert.deepEqual(loadSelectedResponses([c, p]), { program_response: program, characters_response: people });
  assert.deepEqual(loadSelectedResponses([p]), { program_response: program });
  assert.throws(() => loadSelectedResponses([c]), /기본 정보/);
  assert.throws(() => loadSelectedResponses([p, p]), /하나만/);
});
