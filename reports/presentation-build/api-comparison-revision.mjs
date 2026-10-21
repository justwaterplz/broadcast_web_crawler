import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {FileBlob,PresentationFile} from 'file:///C:/Users/moon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
const root='D:/MMLAB/projects/broadcast_web_crawler';
const build=path.join(root,'reports/presentation-api-comparison-20261012');
const skill='C:/Users/moon/.codex/plugins/cache/openai-primary-runtime/presentations/26.1007.11041/skills/presentations';
await fs.mkdir(build,{recursive:true});
const deck=await PresentationFile.importPptx(await FileBlob.load(path.join(root,'presentations/방송콘텐츠_메타데이터_수집검증_20261012_화면정보수정.pptx')));
const slide=deck.slides.items[6];
const inspected=await deck.inspect({kind:'table',maxChars:20000});
for(const item of inspected.ndjson.split('\n').filter(Boolean).map(JSON.parse))if(item.kind==='table'&&item.slideIndex===6)deck.delete(item.id);
for(const shape of [...slide.shapes.items])shape.delete();
slide.images.items[0].frame={left:64,top:190,width:310,height:344};
function text(content,x,y,w,h,size=25,color='#303044',bold=false){
 const sh=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 sh.text=content;sh.text.style={typeface:'Malgun Gothic',fontSize:size,color,bold,insets:0,verticalAlignment:'top',autoFit:'none',wrap:'square'};
}
text('CJ ENM: 화면 정보와 API 응답 비교',64,46,1152,76,43,'#303044',true);
text('프로그램 API 응답',64,143,310,40,26,'#716095',true);
const values=[
 ['항목','화면에서 확인','API 응답으로 확인'],
 ['시청 등급','미표시','15세 이상 / 추가 정보'],
 ['작품 소개','접힌 소개문 일부','전체 소개문 텍스트 반환'],
 ['제작·출연','연출·극본·4명 출연진','동일 정보를 필드별 JSON으로 제공'],
 ['등장인물','2명 설명','동일한 2명 / 추가 인물 없음'],
 ['회차 정보','총 12회','총 12회 / 회차별 시놉시스 없음'],
];
const table=slide.tables.add({rows:values.length,columns:3,left:415,top:151,width:801,height:384,values,columnWidths:[145,225,431]});
table.borders.assign({fill:'#DED9EA',width:1,style:'solid'});
for(let r=0;r<values.length;r++)for(let c=0;c<3;c++){
 const cell=table.getCell(r,c);cell.fill=r===0?'#EEEBF7':'#FFFFFF';cell.text.style={typeface:'Malgun Gothic',fontSize:23,color:r===0?'#716095':'#303044',bold:r===0,verticalAlignment:'middle',insets:12};
}
text('추가 확인: 연령 등급 / 전체 소개문 텍스트 확보',64,570,1152,57,29,'#716095',true);
text('화면의 더보기 펼침은 별도 확인 / 두 API의 직접 조회와 JSON 저장 검증 완료',64,654,1085,32,17,'#797587');
text('07',1170,666,45,26,17,'#797587');
slide.speakerNotes.text+='\n화면과 API 비교 수정: 제공 캡처 cjenm_detail1.png에는 시청 등급이 표시되지 않고 소개문은 접힌 상태로 더보기 링크가 있습니다. API dlbrtGrd는 15세 이상이며 pgmDescp는 전체 소개문 텍스트입니다. 더보기 클릭 후 화면에 같은 전체 소개문이 표시되는지는 이번 비교에서 확인하지 않았으므로 전체 소개문을 API에서만 존재하는 정보로 단정하지 않습니다. 제작진·출연진·회차 수는 화면과 API에 공통이며 구조화된 필드로 확보할 수 있습니다. 등장인물 응답은 화면과 같은 2명으로 추가 인물이 없고, 두 API에는 회차별 시놉시스가 없습니다. API 실측 근거 reports/cjenm-api-verification/20261012_085630의 원본 응답과 검증 보고서입니다.';
const blob=await deck.export({slide,format:'png',scale:1});
await fs.writeFile(path.join(build,'slide-7.png'),new Uint8Array(await blob.arrayBuffer()));
const candidate=path.join(build,'candidate.pptx');
await(await PresentationFile.exportPptx(deck)).save(candidate);
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const owners=[2,6,7,10,11];
const result=await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:path.join(root,'presentations/방송콘텐츠_메타데이터_수집검증_20261012_화면API비교_최종.pptx'),explicitTotalSlideCount:13,requiredNativeTableOwnerSlides:owners,pythonExecutable:'C:/Users/moon/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit',...owners.flatMap(n=>['--require-native-table-slide',String(n)])],fontPolicy:{basis:'design',families:['Malgun Gothic']},verifyArtifactToolImport:true,receiptPath:path.join(build,'validation-final.json')});
console.log(JSON.stringify({finalPath:result.finalPath,layoutFindings:result.presentationLayout.findingCount}));

