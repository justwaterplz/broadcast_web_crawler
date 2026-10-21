import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {FileBlob,PresentationFile} from 'file:///C:/Users/moon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
const root='D:/MMLAB/projects/broadcast_web_crawler';
const build=path.join(root,'reports/presentation-wiki-filtering-20261012');
const skill='C:/Users/moon/.codex/plugins/cache/openai-primary-runtime/presentations/26.1007.11041/skills/presentations';
await fs.mkdir(build,{recursive:true});
const deck=await PresentationFile.importPptx(await FileBlob.load(path.join(root,'presentations/방송콘텐츠_메타데이터_수집검증_20261012_출처보완검토.pptx')));
const s=deck.slides.items[10];
s.tables.items[0].cells.set(4,2,'박현석·신이원 / 12부작 / 동일 방송 기간');
for(const shape of [...s.shapes.items])if(shape.position.top>490&&shape.position.top<650)shape.delete();
function text(content,y,h,size=23,bold=false,color='#303044'){
 const sh=s.shapes.add({geometry:'textbox',position:{left:64,top:y,width:1152,height:h},fill:'none',line:{fill:'none',width:0}});
 sh.text=content;sh.text.style={typeface:'Malgun Gothic',fontSize:size,color,bold,insets:0,verticalAlignment:'top',autoFit:'none',wrap:'square'};
}
text('공동 편집 문서의 신뢰도 검토',502,35,27,true,'#716095');
text('콘텐츠 관계자 외에도 불특정 다수가 같은 문서를 작성·수정할 수 있으므로,\n공식 출처 대조와 사실·평가 구분 등 정보 필터링이 필요함',547,61);
text('하위 문서: URL 직접 검토 후 수집 예정 / 현재 인물·회차 세부 내용 미수집',618,28,20);
s.speakerNotes.text+='\n사용자 요청 반영: 나무위키는 공동 편집 문서이므로 콘텐츠 관계자 외의 다수 편집자가 서술을 작성·수정할 수 있다는 특성을 설명합니다. 위키 서술을 검증된 공식 사실로 자동 승격하지 않고 원문·출처·수집 시각을 보존하며 공식 출처와 비교하고 사실·평가를 구분하는 필터링 및 검토가 필요합니다. 모든 위키 내용이 잘못되었다고 단정하지 않습니다.';
await fs.writeFile(path.join(build,'slide-11.png'),new Uint8Array(await(await deck.export({slide:s,format:'png',scale:1.5})).arrayBuffer()));
const candidate=path.join(build,'candidate.pptx');
await(await PresentationFile.exportPptx(deck)).save(candidate);
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const owners=[2,6,7,8,10,11];
const result=await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:path.join(root,'presentations/방송콘텐츠_메타데이터_수집검증_20261012_위키필터링_표명확화.pptx'),explicitTotalSlideCount:13,requiredNativeTableOwnerSlides:owners,pythonExecutable:'C:/Users/moon/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit',...owners.flatMap(n=>['--require-native-table-slide',String(n)])],fontPolicy:{basis:'design',families:['Malgun Gothic']},verifyArtifactToolImport:true,receiptPath:path.join(build,'validation-clarified.json')});
console.log(JSON.stringify({finalPath:result.finalPath,layoutFindings:result.presentationLayout.findingCount}));
