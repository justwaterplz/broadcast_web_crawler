import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {FileBlob,PresentationFile} from 'file:///C:/Users/moon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
const root='D:/MMLAB/projects/broadcast_web_crawler';
const build=path.join(root,'reports/presentation-source-scope-review-20261012');
const skill='C:/Users/moon/.codex/plugins/cache/openai-primary-runtime/presentations/26.1007.11041/skills/presentations';
await fs.mkdir(build,{recursive:true});
const deck=await PresentationFile.importPptx(await FileBlob.load(path.join(root,'presentations/방송콘텐츠_메타데이터_수집검증_20261012_TVING보완비교.pptx')));
const records=(await deck.inspect({kind:'table',maxChars:20000})).ndjson.split('\n').filter(Boolean).map(JSON.parse);
function clear(n){
 const s=deck.slides.items[n-1];
 for(const r of records.filter(r=>r.slideIndex===n-1))deck.delete(r.id);
 for(const sh of [...s.shapes.items])sh.delete();
 return s;
}
function text(s,content,x,y,w,h,size=25,color='#303044',bold=false){
 const sh=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 sh.text=content;sh.text.style={typeface:'Malgun Gothic',fontSize:size,color,bold,insets:0,verticalAlignment:'top',autoFit:'none',wrap:'square'};
}
function table(s,values,x,y,w,h,widths,size=23){
 const t=s.tables.add({rows:values.length,columns:widths.length,left:x,top:y,width:w,height:h,values,columnWidths:widths});
 t.borders.assign({fill:'#DED9EA',width:1,style:'solid'});
 for(let r=0;r<values.length;r++)for(let c=0;c<widths.length;c++){
  const cell=t.getCell(r,c);cell.fill=r===0?'#EEEBF7':'#FFFFFF';cell.text.style={typeface:'Malgun Gothic',fontSize:size,color:r===0?'#716095':'#303044',bold:r===0,verticalAlignment:'middle',insets:12};
 }
}
function footer(s,n,content){text(s,content,64,654,1085,32,17,'#797587');text(s,String(n).padStart(2,'0'),1170,666,45,26,17,'#797587');}
for(const n of [8,10,11,12]){
 const blob=await deck.export({slide:deck.slides.items[n-1],format:'png',scale:1});
 await fs.writeFile(path.join(build,`before-${n}.png`),new Uint8Array(await blob.arrayBuffer()));
}
const s8=clear(8);
text(s8,'TVING: CJ ENM 정보에 추가되는 작품·회차 정보',64,46,1152,76,43,'#303044',true);
text(s8,'같은 작품: 포핸즈',64,343,310,45,27,'#716095',true);
text(s8,'CJ ENM의 연결 URL로 식별\nP001790301',64,402,310,80,23);
text(s8,'12개 회차\n시놉시스 12개 저장',64,503,310,85,27,'#716095',true);
table(s8,[
 ['항목','CJ ENM에서 확보','TVING으로 보완'],
 ['작품 소개','작품 전체 소개문','작품 소개 제공 / 공통 정보'],
 ['출연진','4명','7명 / 윤세아·김주헌·서재희 추가'],
 ['회차 수','총 12회','12개 회차 목록·제목 확보'],
 ['시놉시스','회차별 내용 없음','1~12화 각각의 소개문 확보'],
 ['방송일','작품 방송 기간','각 회차의 방송일 확보'],
 ['재생 시간','회차별 값 없음','각 회차의 재생 시간(초) 확보'],
 ['작가·인물','작가·2명 인물 설명','작가·인물 설명 미확보'],
],415,151,801,448,[145,240,416]);
text(s8,'공통 기본 정보에 출처별 고유 정보를 결합',64,615,1152,38,29,'#716095',true);
footer(s8,8,'포핸즈 기준 / CJ ENM: 2026.10.12 API 검증 / TVING: 2026.10.07 저장 데이터');
s8.speakerNotes.text+='\n부분집합으로 단정하지 않습니다. CJ ENM에는 작가 신이원 및 두 인물의 배역·설명 텍스트가 있습니다. TVING 저장본에는 writers=null이며 인물 설명 필드가 없습니다. TVING directors는 연출·작가 등의 역할이 혼재한 원본 인명 배열이므로 연출진이 더 많다는 결론을 내리지 않습니다.';
const ps=JSON.parse(await fs.readFile(path.join(root,'data/tving/20261007_210908_251349_드라마_전체/contents.json'),'utf8')).programs;
const es=ps.flatMap(p=>p.episodes);
const pc=k=>ps.filter(p=>p[k]!=null&&p[k]!==''&&(!Array.isArray(p[k])||p[k].length)).length;
const ec=k=>es.filter(e=>e[k]!=null&&e[k]!=='').length;
await fs.writeFile(path.join(build,'field-coverage.json'),JSON.stringify({programs:ps.length,episodes:es.length,program_fields:Object.fromEntries(Object.keys(ps[0]).filter(k=>k!=='episodes').map(k=>[k,pc(k)])),episode_fields:Object.fromEntries(Object.keys(es[0]).map(k=>[k,ec(k)]))},null,2));
const s10=clear(10);
s10.images.items[0].frame={left:64,top:151,width:310,height:169};
text(s10,'TVING 상위 20개: 작품 정보와 회차 세부 정보',64,46,1152,76,43,'#303044',true);
text(s10,'수집 방식',64,343,310,45,27,'#716095',true);
text(s10,'작품 정보\n페이지 내부 구조화 데이터\n\n회차 정보\nAPI 응답',64,397,310,181,23);
table(s10,[
 ['범위','저장한 필드','값 확보 건수'],
 ['작품 기본','작품명·장르·제작연도·채널','각 20/20 작품'],
 ['출연·소개','출연진·작품 소개·시청 등급','각 20/20 작품'],
 ['제작 인명','원본 인명 배열 / 역할 검토 필요','20/20 작품'],
 ['방송 기간','시작일 / 종료일','20/20, 19/20'],
 ['회차 기본','ID·번호·제목·방송일·재생 시간','각 341/341회'],
 ['시놉시스','회차별 소개문','341/341회'],
 ['미확보','작가·키워드','각 0/20 작품'],
],415,151,801,448,[145,455,201]);
text(s10,'시놉시스 외에도 작품·회차별 필드를 함께 저장',64,615,1152,38,29,'#716095',true);
footer(s10,10,'2026.10.07 저장본 / 건수는 확보한 값 기준 / 현재·향후 전체 회차의 완전성을 뜻하지 않음');
s10.speakerNotes.text='집계 근거: data/tving/20261007_210908_251349_드라마_전체/contents.json. 20개 작품과 341개 회차를 저장했습니다. 작품 기본 정보는 __NEXT_DATA__ 및 JSON-LD에서 추출하며 회차 세부 정보는 /v2/media/frequency/program/{code} API 응답에서 추출합니다. 코드 근거: src/broadcast_web_crawler/tving.py parse_detail, content_metadata, collect_program_with_report. 현재 배치가 기본 정보까지 API만으로 수집했음을 검증한 것은 아닙니다. HTTP HTML과 API 요청을 결합하고 브라우저 화면 조작 없이 저장합니다. 모든 제시된 작품 공통 필드는 각각 20개에 값이 있으며 종료일은 19개, 작가와 키워드는 0개입니다. 회차 ID·번호·제목·방송일·재생 시간·시놉시스는 각각 341개에 값이 있습니다. 인명 역할 및 자료의 사실 정확성 검증과는 별개의 값 존재 집계입니다. TVING director에는 작가 등 다른 역할이 혼재할 수 있습니다. 수집기는 페이지네이션 및 여러 시즌 순회를 지원하지 않으므로 회차 개수로 전체 작품의 완전성을 일반화하지 않습니다. 왼쪽 화면은 목록 구조 예시이며 당시 순위 증거는 저장 배치 기준입니다.';
const s11=clear(11);
text(s11,'나무위키: 포핸즈 본문 수집과 하위 문서 보완',64,46,1152,76,43,'#303044',true);
table(s11,[
 ['항목','CJ ENM·TVING에서 확보','나무위키 본문에서 확보'],
 ['제작사','두 저장본에 제작사 필드 값 없음','스튜디오드래곤·스튜디오N·나무엑터스'],
 ['장르','CJ ENM: 드라마 / TVING: 로맨스','청춘·성장·음악 등 세부 장르'],
 ['시청 등급','15세 이상','주제·언어·모방위험 부가 표기'],
 ['공통 정보','연출·작가·방송 기간·총 회차 수','기존 출처의 값과 대조할 정보'],
 ['하위 문서','CJ ENM 인물 2명 / TVING 회차 12개','등장인물·방영 목록 링크 2개 발견'],
],64,151,1152,330,[170,437,545]);
text(s11,'다음 확인: 사람이 하위 문서 URL 검토 후 별도 수집',64,520,1152,42,28,'#716095',true);
text(s11,'본문 기본 정보는 저장 완료. 하위 문서의 인물·회차 세부 내용은 아직 미수집',64,575,1152,57,24);
footer(s11,11,'2026.10.08 저장본 / 위키의 서술을 출처별로 보존하고 공식 정보와 비교');
s11.speakerNotes.text='근거: data/namuwiki/20261008_151253_308786_나무위키_TVING_20개작품/포핸즈_20261008/program.json 및 collection-report.json. 포핸즈 본문은 2026.10.08 HTTP 200, status=exists, extraction_status=collected로 저장됐습니다. 본문 제작사 원본은 스튜디오드래곤, 스튜디오N, 나무엑터스입니다. 위키의 주장을 제작 사실로 독립 검증한 것은 아닙니다. 시청 등급 원본은 15세 이상 시청가 (주제, 언어, 모방위험)입니다. related_documents에 포핸즈/등장인물 및 포핸즈/방영 목록 링크를 확보했으며 related_documents_checked=false, episode_details_collected=false, episodes=[] 입니다. 현재 등장인물 절의 텍스트는 하위 문서 안내만 포함합니다. 하위 문서의 상세 인물·관계·줄거리·회차 정보는 아직 확인하거나 수집하지 않았습니다. 사용자가 직접 대상 작품과 하위 문서 URL을 확인한 뒤 입력하는 흐름을 사용합니다. 수집 시 문서 URL·절 제목·수집 시각 및 가능하면 문서 버전을 같이 보존하고 작품 일치 여부, 원문 근거, 사실과 평가의 구분을 검토합니다. 이번 검토에서 현재 웹 도구로 본문을 다시 열지는 못했습니다. 이 슬라이드는 저장된 과거 수집 결과를 기준으로 하며 현재 접속 검증을 주장하지 않습니다. 기존 냉장고를 부탁해 예시를 같은 작품인 포핸즈의 저장 데이터로 대체해 출처 간 비교를 유지합니다.';
const s12=deck.slides.items[11];
for(const sh of s12.shapes.items){
 const val=String(sh.text??'');
 if(val.includes('12개 회차의'))sh.text=val.replace(/12개 회차의\s*세부 정보/u,'작품 정보·12개 회차 세부 정보');
 if(val.includes('사람이 확인한 문서로 추가 보완'))sh.text=val.replace('사람이 확인한 문서로 추가 보완','제작사·세부 장르 / 하위 문서 추가 확인');
}
s12.speakerNotes.text+='\n출처들은 엄밀한 부분집합 관계가 아닙니다. CJ ENM 고유 정보는 작가와 인물 설명, TVING은 회차별 소개·방송일·재생 시간, 나무위키 본문은 제작사·세부 장르·등급 부가 표기입니다. 포핸즈 위키 본문은 저장 완료이며 하위 문서 수집은 다음 확인 범위입니다. 중복 값은 출처별로 보존하고 동일 작품을 제목뿐 아니라 TVING 연결 ID, 방송 기간, 채널 등으로 확인합니다.';
const s5=deck.slides.items[4];
for(const sh of s5.shapes.items){
 const val=String(sh.text??'');
 if(val.includes('API 호스트의 robots.txt에서 수집 제한 확인'))sh.text=val.replace('API 호스트의 robots.txt에서 수집 제한 확인','사이트·API 호스트의 robots.txt에서 수집 제한 확인');
 if(val.startsWith('자동 수집 제한 확인 후 브라우저에서 데이터 존재 점검'))sh.text='왼쪽: CJ ENM 사이트 robots.txt / API 호스트는 별도 확인 / 응답 존재와 수집 허용은 구분';
}
for(let n=1;n<=13;n++){
 const blob=await deck.export({slide:deck.slides.items[n-1],format:'png',scale:1});
 await fs.writeFile(path.join(build,`slide-${n}.png`),new Uint8Array(await blob.arrayBuffer()));
}
const candidate=path.join(build,'candidate.pptx');
await(await PresentationFile.exportPptx(deck)).save(candidate);
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const owners=[2,6,7,8,10,11];
const result=await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:path.join(root,'presentations/방송콘텐츠_메타데이터_수집검증_20261012_출처보완검토.pptx'),explicitTotalSlideCount:13,requiredNativeTableOwnerSlides:owners,pythonExecutable:'C:/Users/moon/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit',...owners.flatMap(n=>['--require-native-table-slide',String(n)])],fontPolicy:{basis:'design',families:['Malgun Gothic']},verifyArtifactToolImport:true,receiptPath:path.join(build,'validation-delivery.json')});
console.log(JSON.stringify({finalPath:result.finalPath,layoutFindings:result.presentationLayout.findingCount}));
