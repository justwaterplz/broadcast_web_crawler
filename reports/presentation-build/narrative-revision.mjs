import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { FileBlob, PresentationFile } from 'file:///C:/Users/moon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
const root='D:/MMLAB/projects/broadcast_web_crawler';
const build=path.join(root,'reports/presentation-narrative-20261012');
const skill='C:/Users/moon/.codex/plugins/cache/openai-primary-runtime/presentations/26.1007.11041/skills/presentations';
await fs.mkdir(build,{recursive:true});
const deck=await PresentationFile.importPptx(await FileBlob.load(path.join(root,'presentations/방송콘텐츠_메타데이터_수집검증_20261012_최종.pptx')));
const slides=[...deck.slides.items];
function at(s,x,y){const item=s.shapes.items.find(t=>Math.abs(t.position.left-x)<2&&Math.abs(t.position.top-y)<2);if(!item)throw Error(`Missing text ${x},${y}`);return item;}
const policy=slides[6];
at(policy,64,46).text='CJ ENM: 자동 수집 제한과 페이지 직접 확인';
at(policy,415,150).text='API 호스트의 robots.txt에서 수집 제한 확인';
at(policy,415,345).text='자동화 크롤러의 접근·수집: 정책상 제한';
at(policy,415,399).text='일반 크롤러에 전체 경로 제한 명시\n지속적인 자동 수집 적용은 허용 범위 확인 후 결정';
at(policy,415,502).text='사람이 상세페이지에 접속해 API 응답 확인';
at(policy,415,554).text='페이지가 요청한 응답에 작품 소개·제작진·인물 정보 존재';
at(policy,64,654).text='자동 수집 제한 확인 후 브라우저에서 데이터 존재 점검 / 직접 API 조회 결과는 다음 검증에서 설명';
policy.speakerNotes.text += '\n발표 순서: robots.txt의 자동 수집 제한을 먼저 설명하고, 사람이 상세페이지를 직접 열어 페이지의 API 요청·응답에서 작품 메타데이터를 발견한 과정으로 이어갑니다. 정책상 제한을 기술적인 호출 불가능으로 표현하지 않습니다. 이후 별도 Python 직접 호출 검증에서 두 API의 HTTP 200 및 쿠키·인증 불필요 결과를 설명합니다.';
const basic=slides[4];
at(basic,64,46).text='CJ ENM 상세페이지에서 확인한 작품 정보';
const api=slides[5];
at(api,64,46).text='CJ ENM: 페이지의 API 응답에서 작품 정보 확인';
at(api,64,570).text='추가 검증: Python 직접 조회와 JSON 저장 성공';
at(api,64,654).text='브라우저 응답 확인 후 두 API 직접 호출 검증 / 2026.10.12 / 정책상 제한과 기술적 성공은 구분';
api.speakerNotes.text += '\n브라우저에서 발생한 API 요청·응답을 먼저 확인했고, 그 요청 구조로 Python 직접 호출을 추가 검증했습니다. 브라우저에서만 데이터가 제공된다거나 모든 자동 요청이 기술적으로 실패한다고 주장하지 않습니다.';
const order=[...slides.slice(0,4),policy,basic,api,...slides.slice(7)];
deck.slides.reorder(order.map(s=>`sl/${s.id}`));
for(const [i,s] of deck.slides.items.entries()){
 const page=s.shapes.items.find(t=>t.position.left>=1160&&t.position.top>=660);
 if(page)page.text=String(i+1).padStart(2,'0');
}
for(const n of [5,6,7]){
 const blob=await deck.export({slide:deck.slides.items[n-1],format:'png',scale:1});
 await fs.writeFile(path.join(build,`slide-${n}.png`),new Uint8Array(await blob.arrayBuffer()));
}
const candidate=path.join(build,'candidate.pptx');
await (await PresentationFile.exportPptx(deck)).save(candidate);
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const owners=[2,6,7,10,11];
const result=await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:path.join(root,'presentations/방송콘텐츠_메타데이터_수집검증_20261012_설명수정.pptx'),explicitTotalSlideCount:13,requiredNativeTableOwnerSlides:owners,pythonExecutable:'C:/Users/moon/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit',...owners.flatMap(n=>['--require-native-table-slide',String(n)])],fontPolicy:{basis:'design',families:['Malgun Gothic']},verifyArtifactToolImport:true,receiptPath:path.join(build,'validation.json')});
console.log(JSON.stringify({finalPath:result.finalPath,integrity:result.packageIntegrity.status,layoutFindings:result.presentationLayout.findingCount}));
