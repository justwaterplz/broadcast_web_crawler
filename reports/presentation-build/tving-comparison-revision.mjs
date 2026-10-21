import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {FileBlob,PresentationFile} from 'file:///C:/Users/moon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
const root='D:/MMLAB/projects/broadcast_web_crawler';
const build=path.join(root,'reports/presentation-tving-comparison-20261012');
const skill='C:/Users/moon/.codex/plugins/cache/openai-primary-runtime/presentations/26.1007.11041/skills/presentations';
await fs.mkdir(build,{recursive:true});
const deck=await PresentationFile.importPptx(await FileBlob.load(path.join(root,'presentations/방송콘텐츠_메타데이터_수집검증_20261012_화면API비교_최종.pptx')));
const slide=deck.slides.items[7];
for(const shape of [...slide.shapes.items])shape.delete();
slide.images.items[0].frame={left:64,top:151,width:310,height:169};
function text(s,content,x,y,w,h,size=25,color='#303044',bold=false){
 const sh=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 sh.text=content;sh.text.style={typeface:'Malgun Gothic',fontSize:size,color,bold,insets:0,verticalAlignment:'top',autoFit:'none',wrap:'square'};
}
text(slide,'TVING: CJ ENM 정보에 추가되는 작품·회차 정보',64,46,1152,76,43,'#303044',true);
text(slide,'같은 작품: 포핸즈',64,343,310,45,27,'#716095',true);
text(slide,'CJ ENM의 연결 URL로 식별\nP001790301',64,402,310,80,23);
text(slide,'12개 회차\n시놉시스 12개 저장',64,503,310,85,27,'#716095',true);
const values=[
 ['항목','CJ ENM에서 확보','TVING으로 보완'],
 ['작품 소개','작품 전체 소개문','작품 소개 제공 / 공통 정보'],
 ['출연진','4명','7명 / 윤세아·김주헌·서재희 추가'],
 ['회차 수','총 12회','12개 회차 목록·제목 확보'],
 ['시놉시스','회차별 내용 없음','1~12화 각각의 소개문 확보'],
 ['방송일','작품 방송 기간','각 회차의 방송일 확보'],
 ['재생 시간','회차별 값 없음','각 회차의 재생 시간(초) 확보'],
];
const table=slide.tables.add({rows:values.length,columns:3,left:415,top:151,width:801,height:420,values,columnWidths:[145,240,416]});
table.borders.assign({fill:'#DED9EA',width:1,style:'solid'});
for(let r=0;r<values.length;r++)for(let c=0;c<3;c++){
 const cell=table.getCell(r,c);cell.fill=r===0?'#EEEBF7':'#FFFFFF';cell.text.style={typeface:'Malgun Gothic',fontSize:23,color:r===0?'#716095':'#303044',bold:r===0,verticalAlignment:'middle',insets:12};
}
text(slide,'회차별 시놉시스 확보가 핵심 보완 정보',64,602,1152,40,29,'#716095',true);
text(slide,'포핸즈 기준 비교 / CJ ENM: 2026.10.12 API 검증 / TVING: 2026.10.07 저장 데이터',64,654,1085,32,17,'#797587');
text(slide,'08',1170,666,45,26,17,'#797587');
slide.speakerNotes.text+='\nCJ ENM과 TVING 비교 근거: reports/cjenm-api-verification/20261012_085630/content-metadata.json 및 data/tving/20261007_210908_251349_드라마_전체/contents.json의 P001790301. TVING episodes는 12개이며 전 회차에 시놉시스·방송일·duration_seconds가 있습니다. CJ ENM 응답의 episode_count 12는 총 회차 수만 제공하고 episodes 배열은 비어 있습니다. 출연진은 CJ ENM 4명, TVING 7명이며 추가 3명은 윤세아·김주헌·서재희입니다. 두 출처는 다른 시점의 데이터이며 출연진 전체의 완전성을 보장하지 않습니다. 방송 기간과 회차별 방송일을 구분합니다. TVING director 배열은 제작 역할이 혼재할 수 있어 추가 연출진 확정 자료로 사용하지 않습니다. CJ ENM에서 확인한 연출 박현석·작가 신이원을 유지하고 원본 출처별 값을 별도로 보존합니다. 시놉시스는 회차 소개이며 대본 원문이 아닙니다.';
const api=deck.slides.items[8];
api.shapes.items.find(s=>Math.abs(s.position.top-46)<2).text='TVING: 추가 회차 정보의 API 응답 근거';
api.shapes.items.find(s=>Math.abs(s.position.top-536)<2).text='CJ ENM의 작품 소개를 회차별 세부 정보로 보완';
api.speakerNotes.text+='\n이 슬라이드는 앞 비교표의 추가 회차 정보에 대한 응답 근거입니다. CJ ENM의 두 API에는 회차별 시놉시스·방송일·재생 시간 목록이 없으며 TVING 응답에서 확보합니다. 1화와 2화 예시 외에도 저장 JSON에 12개 회차를 확인했습니다.';
for(const n of [8,9]){
 const blob=await deck.export({slide:deck.slides.items[n-1],format:'png',scale:1});
 await fs.writeFile(path.join(build,`slide-${n}.png`),new Uint8Array(await blob.arrayBuffer()));
}
const candidate=path.join(build,'candidate.pptx');
await(await PresentationFile.exportPptx(deck)).save(candidate);
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const owners=[2,6,7,8,10,11];
const result=await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:path.join(root,'presentations/방송콘텐츠_메타데이터_수집검증_20261012_TVING보완비교.pptx'),explicitTotalSlideCount:13,requiredNativeTableOwnerSlides:owners,pythonExecutable:'C:/Users/moon/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit',...owners.flatMap(n=>['--require-native-table-slide',String(n)])],fontPolicy:{basis:'design',families:['Malgun Gothic']},verifyArtifactToolImport:true,receiptPath:path.join(build,'validation.json')});
console.log(JSON.stringify({finalPath:result.finalPath,layoutFindings:result.presentationLayout.findingCount}));
