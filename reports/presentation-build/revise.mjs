import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { FileBlob, PresentationFile } from 'file:///C:/Users/moon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
const root = 'D:/MMLAB/projects/broadcast_web_crawler';
const build = path.join(root, 'reports/presentation-revision');
await fs.mkdir(build, { recursive: true });
const skill = 'C:/Users/moon/.codex/plugins/cache/openai-primary-runtime/presentations/26.1007.11041/skills/presentations';
const source = path.join(root, 'presentations/방송콘텐츠_메타데이터_수집검토_예시_20261011.pptx');
const deck = await PresentationFile.importPptx(await FileBlob.load(source));
const C = { bg: '#FAF9FD', ink: '#303044', purple: '#716095', muted: '#797587', pale: '#EEEBF7', border: '#DED9EA' };
const FONT = 'Malgun Gothic';
function txt(s, content, x, y, w, h, size = 25, color = C.ink, bold = false) {
  const shape = s.shapes.add({ geometry: 'textbox', position: { left: x, top: y, width: w, height: h }, fill: 'none', line: { fill: 'none', width: 0 } });
  shape.text = content;
  shape.text.style = { typeface: FONT, fontSize: size, color, bold, insets: 0, verticalAlignment: 'top', autoFit: 'none', wrap: 'square' };
  return shape;
}
function clear(s) {
  for (const shape of [...s.shapes.items]) shape.delete();
}
function table(s, values, x, y, w, h, widths, size = 24) {
  const t = s.tables.add({ rows: values.length, columns: values[0].length, left: x, top: y, width: w, height: h, values, columnWidths: widths });
  t.borders.assign({ fill: C.border, width: 1, style: 'solid' });
  for (let r=0;r<values.length;r++) for (let c=0;c<values[0].length;c++) {
    const cell = t.getCell(r,c); cell.fill = r === 0 ? C.pale : '#FFFFFF';
    cell.text.style = { typeface: FONT, fontSize: size, color: r === 0 ? C.purple : C.ink, bold: r === 0, verticalAlignment: 'middle', insets: 12 };
  }
  return t;
}
const slides = [...deck.slides.items];
const inspected = await deck.inspect({ kind:'table', maxChars:10000 });
for (const record of inspected.ndjson.split('\n').filter(Boolean).map(line => JSON.parse(line))) {
  if (record.kind === 'table' && [1,4].includes(record.slideIndex)) deck.delete(record.id);
}
for (const index of [1,4]) {
  const blob = await deck.export({ slide: slides[index], format:'png', scale:1 });
  await fs.writeFile(path.join(build, `before-${index+1}.png`), new Uint8Array(await blob.arrayBuffer()));
}
{
  const s = slides[1]; clear(s);
  txt(s, '검토 대상과 확인 방법', 64,46,1152,76,43,C.ink,true);
  txt(s, '기본 검토 대상',64,145,1152,44,29,C.purple,true);
  table(s,[['대상 웹사이트','콘텐츠 범위'],['CJ ENM','드라마, 예능'],['컴투스 그룹(위지윅스튜디오)','드라마'],['MBC 충북','뉴스 (중앙 MBC와 별도)']],64,205,1152,250,[590,562],25);
  txt(s,'추가 수집원',64,491,200,44,28,C.purple,true);
  txt(s,'TVING: CJ ENM 콘텐츠의 실제 제공 경로에서 작품·회차 정보 확보\n나무위키: 프로그램 설명과 제작진·방송 정보 보완',64,546,1152,85,25);
  txt(s,'확인 방법: 직접 접속 및 구조 점검 / 자동 수집 가능성 확인 / 메타데이터 추출',64,655,1100,29,18,C.muted);
  s.speakerNotes.text = '기본 검토 대상 출처: C:/Users/moon/Documents/카카오톡 받은 파일/(260929)ETRI_용역과제_킥오프미팅_발표자료.pdf, PDF 6페이지(슬라이드 인쇄 번호 9), 검토 대상 웹사이트 리스트. 원문에는 CJ ENM: 드라마, 예능 / 컴투스 그룹(위지윅스튜디오): 드라마 / MBC 충북(중앙 MBC와 별개): 뉴스가 명시되어 있습니다. 또한 CJ ENM 콘텐츠는 TVING 등 실제 콘텐츠 제공 경로도 함께 검토하도록 제시합니다. 나무위키는 사용자와의 작업 과정에서 추가한 보완 수집원입니다. 유튜브 개인방송은 원문의 추가 검토 대상이나 이번 보고 범위에서는 다루지 않습니다.';
}
{
  const s = slides[4]; clear(s);
  txt(s,'기본 대상 직접 점검과 추가 수집원 선정',64,46,1152,76,43,C.ink,true);
  table(s,[['대상','직접 점검 결과','근거로 첨부할 자료'],['CJ ENM','크롤링 정책상 자동 수집 제한\nrobots.txt 제한 확인','[robots.txt 제한 규칙 캡처]\n[점검 URL·확인 일자]'],['컴투스 그룹','확인한 작품 상세 페이지에\n유튜브 영상 1개 게시\n텍스트 메타데이터 부족','[작품 상세 페이지 전체 캡처]\n[작품명·URL·확인 일자]'],['MBC 충북','뉴스 페이지 직접 접속·점검\n[세부 점검 결과 기입]','[뉴스 상세 페이지 캡처]\n[확보 가능 필드·URL·확인 일자]']],64,154,1152,411,[215,467,470],24);
  txt(s,'CJ ENM 콘텐츠는 TVING에서 확보하고, 나무위키로 프로그램 정보를 보완',64,606,1152,43,26,C.purple,true);
  txt(s,'직접 점검 결과 기준 / [ ] 표시는 후속 근거 첨부·작성 위치',64,662,1100,28,18,C.muted);
  s.speakerNotes.text = '사용자 직접 점검 결과와 이번 수정 요청을 근거로 작성. CJ ENM은 정책상 웹 크롤링이 제한된다는 사용자 확인 내용을 반영하며 robots.txt 근거 캡처를 첨부할 위치를 표시합니다. 컴투스 그룹(위지윅스튜디오) 검토 경로 중 https://com2usn.com/work/의 확인한 작품 상세 페이지에 유튜브 영상 1개만 있다는 사용자 관찰을 반영했습니다. 이를 모든 작품이나 그룹 전체 사이트의 데이터 부재로 일반화하지 않습니다. MBC 충북은 사용자가 직접 접속·점검했다고 했으나 구체적인 확보 필드 또는 한계가 대화에 없으므로 세부 점검 결과를 채울 자리를 남깁니다. URL·확인 일자 및 캡처는 사용자 후속 첨부 대상입니다.';
}
deck.slides.reorder([0,1,4,2,3,5].map(i => `sl/${slides[i].id}`));
for (const [i,s] of deck.slides.items.entries()) {
  const foot = s.shapes.items.find(shape => shape.position.left >= 1160 && shape.position.top >= 660);
  if (foot) foot.text = String(i+1).padStart(2,'0');
  else txt(s,String(i+1).padStart(2,'0'),1170,666,45,26,17,C.muted);
}
const candidate = path.join(build,'candidate.pptx');
await (await PresentationFile.exportPptx(deck)).save(candidate);
for (const [i,s] of deck.slides.items.entries()) {
  const blob = await deck.export({slide:s,format:'png',scale:1});
  await fs.writeFile(path.join(build,`slide-${i+1}.png`),new Uint8Array(await blob.arrayBuffer()));
}
const { finalizePresentation } = await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const result = await finalizePresentation({
  workspaceDir:root,candidatePath:candidate,
  finalPath:path.join(root,'presentations/방송콘텐츠_메타데이터_수집검토_수정본_20261011.pptx'),
  explicitTotalSlideCount:6,requiredNativeTableOwnerSlides:[2,3,4,5],
  pythonExecutable:'C:/Users/moon/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',
  integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit',
    ...[2,3,4,5].flatMap(n => ['--require-native-table-slide',String(n)])],
  fontPolicy:{basis:'design',families:[FONT]},verifyArtifactToolImport:true,
  receiptPath:path.join(build,'validation.json'),
});
console.log(result.finalPath);
