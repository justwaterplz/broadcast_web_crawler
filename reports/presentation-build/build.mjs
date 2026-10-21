import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Presentation, PresentationFile } from 'file:///C:/Users/moon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';

const root = 'D:/MMLAB/projects/broadcast_web_crawler';
const build = path.join(root, 'reports/presentation-build');
const output = path.join(root, 'presentations');
const skill = 'C:/Users/moon/.codex/plugins/cache/openai-primary-runtime/presentations/26.1007.11041/skills/presentations';
await fs.mkdir(build, { recursive: true });
await fs.mkdir(output, { recursive: true });
const read = async p => JSON.parse(await fs.readFile(path.join(root, p), 'utf8'));
const tvingPath = 'data/tving/20261008_155538_396845_TVING_작품상세/contents.json';
const wikiPath = 'data/namuwiki/20261008_144044_283930_나무위키_냉장고를 부탁해/contents.json';
const batchPath = 'data/tving/20261007_210908_251349_드라마_전체/collection-report.json';
const tv = (await read(tvingPath)).programs[0];
const wiki = (await read(wikiPath)).programs[0];
const summary = (await read(batchPath)).summary;
const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const C = { bg: '#FAF9FD', ink: '#303044', purple: '#716095', muted: '#797587', pale: '#EEEBF7', border: '#DED9EA' };
const FONT = 'Malgun Gothic';
function txt(s, content, x, y, w, h, size = 25, color = C.ink, bold = false) {
  const shape = s.shapes.add({ geometry: 'textbox', position: { left: x, top: y, width: w, height: h }, fill: 'none', line: { fill: 'none', width: 0 } });
  shape.text = content;
  shape.text.style = { typeface: FONT, fontSize: size, color, bold, insets: 0, verticalAlignment: 'top', autoFit: 'none', wrap: 'square' };
  return shape;
}
function slide(title, index, notes) {
  const s = deck.slides.add(); s.background.fill = C.bg;
  if (title) txt(s, title, 64, 46, 1152, 76, 43, C.ink, true);
  txt(s, String(index).padStart(2, '0'), 1170, 666, 45, 26, 17, C.muted);
  s.speakerNotes.text = notes;
  return s;
}
function table(s, values, x, y, w, h, widths, size = 24) {
  const t = s.tables.add({ rows: values.length, columns: values[0].length, left: x, top: y, width: w, height: h, values, columnWidths: widths });
  t.borders.assign({ fill: C.border, width: 1, style: 'solid' });
  for (let r = 0; r < values.length; r++) for (let c = 0; c < values[0].length; c++) {
    const cell = t.getCell(r, c); cell.fill = r === 0 ? C.pale : '#FFFFFF';
    cell.text.style = { typeface: FONT, fontSize: size, color: r === 0 ? C.purple : C.ink, bold: r === 0, verticalAlignment: 'middle', insets: 14 };
  }
  return t;
}

{
  const s = slide('', 1, '방송·미디어 콘텐츠 메타데이터 수집 가능성 검토의 예시 발표자료입니다. TVING과 나무위키는 프로젝트의 저장된 JSON을 근거로 작성했습니다. CJ ENM과 컴투스온은 사용자의 직접 점검 결과입니다. 자료 작성일 2026-10-11, 수집 예시 기준일 2026-10-07~08.');
  s.background.fill = '#EEEBF7';
  txt(s, '방송 콘텐츠\n메타데이터 수집 가능성 검토', 72, 160, 1100, 196, 59, C.ink, true);
  txt(s, 'TVING과 나무위키의 실제 수집 결과', 76, 406, 1040, 48, 31, C.purple);
  txt(s, '국가 용역과제 진행 보고 예시\n2026.10.11', 76, 542, 1000, 78, 24, C.muted);
}
{
  const s = slide('수집 대상과 확인 방법', 2, '수집 대상은 사용자가 지정한 사이트를 기준으로 작성했습니다. 입력은 콘텐츠 ID가 아니라 페이지 URL입니다. TVING 수집 로직은 tving.py 및 tving_batch.py, 나무위키 수집 로직은 namuwiki.py로 분리되어 있습니다. 콘텐츠 JSON과 진단 보고서를 별도로 저장합니다.');
  txt(s, '방송 프로그램에 관한 공개 텍스트를 구조화된 JSON으로 저장', 64, 140, 1152, 45, 28, C.purple);
  table(s, [['수집원', '검토하는 정보'], ['CJ ENM', '공식 프로그램 소개 및 제작 정보'], ['TVING', '작품 메타데이터와 회차별 시놉시스'], ['나무위키', '제작진, 출연·진행자, 방송 정보와 프로그램 설명'], ['컴투스온 Work', '작품 포트폴리오의 방송 콘텐츠 정보']], 64, 222, 1152, 322, [270, 882], 25);
  txt(s, '확인 방법', 64, 583, 200, 40, 25, C.purple, true);
  txt(s, 'URL 직접 입력 / 페이지·공개 응답 확인 / 필드 추출 / JSON 저장', 64, 628, 1152, 38, 24);
}
{
  const s = slide('TVING: 작품과 회차별 시놉시스 수집 확인', 3, `출처: ${path.join(root, batchPath)}\n${path.join(root, tvingPath)}\n원문: https://www.tving.com/more/genre/PCA 및 https://www.tving.com/contents/P001790587\n20개 작품·341개 회차·341개 시놉시스는 2026-10-07 저장 배치의 결과입니다. 단일 작품 8개 회차 예시는 2026-10-08 저장 결과입니다. 현재 사이트 전체 또는 다른 시즌의 완전성을 뜻하지 않습니다. 시놉시스는 회차 소개 텍스트이며 대본 원문이 아닙니다.`);
  txt(s, `${summary.successful_programs}개 작품   ${summary.collected_episodes}개 회차`, 64, 143, 1152, 62, 42, C.purple, true);
  txt(s, '드라마 전체 상위 20개 수집 예시에서 341개 회차 시놉시스 저장', 64, 213, 1152, 42, 25);
  txt(s, tv.title, 64, 295, 510, 51, 30, C.ink, true);
  table(s, [['항목', '수집 값'], ['장르', tv.genre], ['연출', tv.directors.join(', ')], ['출연', tv.cast.slice(0, 3).join(', ')], ['회차 정보', `${tv.episodes.length}개 회차 저장`]], 64, 355, 520, 252, [145, 375], 23);
  txt(s, '회차별 데이터 예시', 632, 295, 584, 45, 27, C.purple, true);
  for (let i = 0; i < 2; i++) {
    const e = tv.episodes[i]; const y = 358 + i * 133;
    txt(s, e.title, 632, y, 584, 38, 25, C.ink, true);
    txt(s, e.synopsis, 632, y + 44, 584, 89, 23);
  }
  txt(s, '저장 데이터 기준: 2026.10.07~08 / 시놉시스는 회차 소개이며 대본 원문은 아님', 64, 649, 1100, 28, 18, C.muted);
}
{
  const s = slide('나무위키: 프로그램 메타데이터 수집 확인', 4, `출처: ${path.join(root, wikiPath)}\n원문: https://namu.wiki/w/%EB%83%89%EC%9E%A5%EA%B3%A0%EB%A5%BC%20%EB%B6%80%ED%83%81%ED%95%B4\n2026-10-08에 저장한 문서 기준입니다. 방송 기간과 254회는 시즌 1 관련 원문 정보입니다. 문서에는 시즌 2도 언급되므로 이후 시즌이나 최신 편성 전체를 뜻하지 않습니다. episodes는 빈 배열입니다. 셰프 군단과 방영 목록 링크는 저장하지만 이 단일 문서 수집에서는 따라가지 않았습니다. 문서에 없는 값은 null이며 모든 방송 문서에 같은 필드가 있다고 보장하지 않습니다.`);
  txt(s, wiki.title, 64, 142, 1152, 54, 36, C.purple, true);
  table(s, [['항목', '수집 값'], ['방송사 / 제작사', `${wiki.channel} / ${wiki.production_company}`], ['연출', wiki.directors.join(', ')], ['작가 예시', wiki.writers.slice(0, 3).join(', ')], ['진행자', wiki.hosts.join(', ')], ['방송 기간', `${wiki.broadcast_start_date} ~ ${wiki.broadcast_end_date}`], ['총 회차 수', `${wiki.episode_count}회 (문서의 시즌 1 정보)`]], 64, 220, 670, 381, [210, 460], 23);
  txt(s, '프로그램 설명도 수집', 786, 226, 430, 44, 28, C.ink, true);
  txt(s, '게스트의 냉장고 속 재료를 이용해\n셰프들이 제한 시간 15분 안에\n요리를 만들어 대결하는 프로그램', 786, 295, 430, 143, 25);
  txt(s, '수집 범위', 786, 465, 430, 41, 25, C.purple, true);
  txt(s, '관련 문서 링크 저장\n현재 예시의 회차별 데이터는 없음', 786, 514, 430, 93, 23);
  txt(s, '저장 데이터 기준: 2026.10.08 / 총 회차 수와 회차별 시놉시스 확보는 구분', 64, 649, 1100, 28, 18, C.muted);
}
{
  const s = slide('CJ ENM과 컴투스온의 수집 제약', 5, '근거: 사용자가 이 대화에서 제공한 직접 점검 결과. CJ ENM은 robots.txt에서 자동 사이트 순회·접속이 제한된다는 사용자 확인 내용을 반영했습니다. robots.txt 제한을 법률상 금지와 동일하게 표현하지 않습니다. 컴투스온은 https://com2usn.com/work/ 직접 확인 시 필요한 데이터가 없었다는 사용자 관찰을 반영했습니다. 이번 웹 도구 재접속에서는 두 페이지의 내용을 확인하지 못했으므로 현재 정책 또는 사이트 전체의 데이터 부재를 독립 검증한 결과로 제시하지 않습니다.');
  table(s, [['대상', '확인된 제약', '진행 방향'], ['CJ ENM', 'robots.txt에 따른\n자동 수집 제한', '대체 수집원으로\nTVING 활용'], ['컴투스온 Work', '직접 점검한 페이지에서\n필요한 메타데이터 미확인', '추가 자료 제공 여부와\n다른 공개 출처 확인']], 64, 171, 1152, 323, [240, 465, 447], 27);
  txt(s, '수집 제한과 정보 부족을 구분', 64, 548, 1152, 43, 29, C.purple, true);
  txt(s, 'CJ ENM은 자동 수집 정책의 제약, 컴투스온은 점검한 페이지의 정보 부족', 64, 605, 1152, 53, 25);
  txt(s, '사용자 직접 점검 결과 기준 / 컴투스온 점검 URL: https://com2usn.com/work/', 64, 665, 1100, 28, 17, C.muted);
}
{
  const s = slide('수집 도구 구현과 다음 단계', 6, '앱 화면 출처: 프로젝트 reports/desktop/studio.png. 직접 구현한 Electron + React + Python 앱의 로컬 캡처입니다. 화면은 shadcn/ui와 라벤더 테마를 적용했습니다. URL 입력, 범위 설정, 수집 진행 확인, 과거 결과 조회, JSON 및 수집 보고서 표시 기능이 있습니다. 출처별 수집 로직은 분리하고 콘텐츠 메타데이터 스키마를 공유합니다. 향후 회차 누락·제작진 누락과 원문 근거를 확인하며 나무위키 관련 문서 확장은 별도 범위로 검토합니다.');
  const bytes = await fs.readFile(path.join(root, 'reports/desktop/studio.png'));
  s.images.add({ blob: bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), contentType: 'image/png', alt: '방송 메타데이터 수집 앱의 라벤더 테마 화면', fit: 'contain', position: { left: 64, top: 151, width: 760, height: 492 } });
  txt(s, '현재 구현', 870, 156, 346, 46, 28, C.purple, true);
  txt(s, 'URL 입력과 수집 범위 설정\n작품 정보·회차·JSON 조회\n실행별 폴더에 결과 저장', 870, 217, 346, 154, 24);
  txt(s, '다음 확인 사항', 870, 407, 346, 46, 28, C.purple, true);
  txt(s, '필드 누락 및 회차 완전성\n출처별 데이터 품질\n위키 관련 문서의 수집 범위', 870, 468, 346, 154, 24);
  txt(s, 'TVING과 나무위키의 수집 로직을 분리하고 공통 콘텐츠 스키마로 저장', 64, 663, 1100, 30, 19, C.muted);
}

const candidate = path.join(build, 'candidate.pptx');
await (await PresentationFile.exportPptx(deck)).save(candidate);
for (const [i,s] of deck.slides.items.entries()) {
  const blob = await deck.export({ slide: s, format: 'png', scale: 1 });
  await fs.writeFile(path.join(build, `slide-${i + 1}.png`), new Uint8Array(await blob.arrayBuffer()));
}
const montage = await deck.export({ format: 'webp', montage: true });
await fs.writeFile(path.join(build, 'montage.webp'), new Uint8Array(await montage.arrayBuffer()));
const { finalizePresentation } = await import(pathToFileURL(path.join(skill, 'container_tools/artifact_tool_utils.mjs')).href);
const result = await finalizePresentation({
  explicitTotalSlideCount: 6, requiredNativeTableOwnerSlides: [2,3,4,5],
  workspaceDir: root, candidatePath: candidate,
  finalPath: path.join(output, '방송콘텐츠_메타데이터_수집검토_예시_20261011.pptx'),
  pythonExecutable: 'C:/Users/moon/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',
  integrityValidatorPath: path.join(skill, 'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath: path.join(skill, 'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs: ['--expected-slide-size-emu', '12192000,6858000', '--validate-heading-fit', '--require-native-table-slide','2', '--require-native-table-slide','3', '--require-native-table-slide','4', '--require-native-table-slide','5'],
  fontPolicy: { basis: 'design', families: [FONT] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(build, 'validation.json'),
});
console.log(JSON.stringify(result));
