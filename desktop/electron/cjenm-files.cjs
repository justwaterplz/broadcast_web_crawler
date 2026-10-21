const fs = require('node:fs');

function loadSelectedResponses(filePaths) {
  if (!Array.isArray(filePaths) || !filePaths.length || filePaths.length > 2) {
    throw new Error('작품 응답 1개와 선택적으로 등장인물 응답 1개를 선택해 주세요.');
  }
  let program, characters;
  for (const filename of filePaths) {
    if (fs.statSync(filename).size > 10_000_000) throw new Error('각 응답 파일은 10MB 이하로 선택해 주세요.');
    const value = JSON.parse(fs.readFileSync(filename, 'utf8').replace(/^\uFEFF/, ''));
    const data = value?.result?.data;
    if (data?.pgmSeq && data?.pgmNm && !('detailPrsnInfoList' in data) && !('simplePrsnInfoList' in data)) {
      if (program) throw new Error('작품 응답은 하나만 선택해 주세요.');
      program = value;
    } else if (data && ('detailPrsnInfoList' in data || 'simplePrsnInfoList' in data)) {
      if (characters) throw new Error('등장인물 응답은 하나만 선택해 주세요.');
      characters = value;
    } else throw new Error('CJ ENM 작품·등장인물 JSON 응답인지 확인해 주세요.');
  }
  if (!program) throw new Error('작품 기본 정보 응답이 필요합니다.');
  return { program_response: program, ...(characters ? { characters_response: characters } : {}) };
}

module.exports = { loadSelectedResponses };
