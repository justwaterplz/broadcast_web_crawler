import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import sharp from 'file:///C:/Users/moon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp/dist/index.mjs';
import { FileBlob, PresentationFile } from 'file:///C:/Users/moon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';

const root = 'D:/MMLAB/projects/broadcast_web_crawler';
const build = path.join(root,'reports/presentation-evidence-20261012');
const skill = 'C:/Users/moon/.codex/plugins/cache/openai-primary-runtime/presentations/26.1007.11041/skills/presentations';
await fs.mkdir(build,{recursive:true});
const source = path.join(root,'presentations/방송콘텐츠_메타데이터_수집검토_수정본_20261011.pptx');
const deck = await PresentationFile.importPptx(await FileBlob.load(source));
const old = [...deck.slides.items];
const C={bg:'#FAF9FD',ink:'#303044',purple:'#716095',muted:'#797587',pale:'#EEEBF7',border:'#DED9EA'};
const FONT='Malgun Gothic';
const read=async p=>JSON.parse(await fs.readFile(path.join(root,p),'utf8'));
const tvPath='data/tving/20261007_210908_251349_드라마_전체/contents.json';
const tv=(await read(tvPath)).programs.find(x=>x.program_id==='P001790301');
const summary=(await read('data/tving/20261007_210908_251349_드라마_전체/collection-report.json')).summary;
const cjDir='reports/cjenm-api-verification/20261012_085630';
const cj=await read(cjDir+'/content-metadata.json');
const verified=await read(cjDir+'/verification-report.json');
const wikiPath='data/namuwiki/20261008_144044_283930_나무위키_냉장고를 부탁해/contents.json';
const wiki=(await read(wikiPath)).programs[0];
const evidence=[];
function txt(s,content,x,y,w,h,size=25,color=C.ink,bold=false){
 const sh=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 sh.text=content;sh.text.style={typeface:FONT,fontSize:size,color,bold,insets:0,verticalAlignment:'top',autoFit:'none',wrap:'square'};return sh;
}
function title(s,t){txt(s,t,64,46,1152,76,43,C.ink,true);}
function footer(s,t){txt(s,t,64,654,1085,32,17,C.muted);}
function add(t,notes){const s=deck.slides.add();s.background.fill=C.bg;title(s,t);s.speakerNotes.text=notes;return s;}
function table(s,values,x,y,w,h,widths,size=24){
 const t=s.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width:w,height:h,values,columnWidths:widths});
 t.borders.assign({fill:C.border,width:1,style:'solid'});
 for(let r=0;r<values.length;r++)for(let c=0;c<values[0].length;c++){
  const cell=t.getCell(r,c);cell.fill=r===0?C.pale:'#FFFFFF';cell.text.style={typeface:FONT,fontSize:size,color:r===0?C.purple:C.ink,bold:r===0,verticalAlignment:'middle',insets:12};
 }return t;
}
async function img(s,name,x,y,w,h,crop){
 const original=path.join(root,'reports/1',name);const bytes=crop?await sharp(original).extract(crop).png().toBuffer():await fs.readFile(original);
 s.images.add({blob:bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),contentType:'image/png',alt:name,fit:'contain',position:{left:x,top:y,width:w,height:h}});
 evidence.push({file:original,crop:crop||null,slide_id:s.id});
}
// Reuse the source slides and its visual system. Replace tables on changed slides.
const inspected=await deck.inspect({kind:'table',maxChars:20000});
for(const r of inspected.ndjson.split('\n').filter(Boolean).map(JSON.parse))if(r.kind==='table'&&[2,3,4].includes(r.slideIndex))deck.delete(r.id);
for(const i of [2,3,4,5])for(const sh of [...old[i].shapes.items])sh.delete();
for(const image of [...old[5].images.items])image.delete();
for(const sh of old[0].shapes.items){
 if(String(sh.text).includes('TVING과 나무위키'))sh.text='CJ ENM API 검증과 동일 작품의 출처별 정보 보완';
 if(String(sh.text).includes('2026.10.11'))sh.text='국가 용역과제 진행 보고\n2026.10.12';
}
old[0].speakerNotes.text='CJ ENM·컴투스 그룹·MBC 충북을 기본 검토 대상으로 유지합니다. TVING과 나무위키는 추가 수집원입니다. CJ ENM 기술 검증은 2026-10-12, TVING 배치 수집은 2026-10-07, 나무위키 기존 수집 사례는 2026-10-08 기준입니다. 사용자 제공 캡처는 reports/1에서 확보했고 촬영일 자체는 확인하지 않았습니다.';

const com=add('컴투스 그룹 검토 경로: 작품 상세 정보 부족',`캡처: ${root}/reports/1/com2us_detail.png\n원문 URL: https://com2usn.com/work/255\n작품: 킬러들의 쇼핑몰2. 사용자 캡처에서 작품명과 YouTube 티저 영상 및 이전/다음 글을 확인했습니다. 이 점검 페이지에서 제작진·출연진·줄거리·회차 정보 등의 텍스트는 확인하지 못했습니다. 사이트 전체의 정보 부재로 일반화하지 않습니다. 기본 대상은 첨부 킥오프 자료의 컴투스 그룹(위지윅스튜디오)이며 실제 점검 경로는 컴투스엔입니다.`);
await img(com,'com2us_detail.png',64,157,770,450,{left:670,top:265,width:1200,height:1000});
txt(com,'킬러들의 쇼핑몰2',876,160,340,45,29,C.purple,true);
txt(com,'확인한 상세 페이지에는\n작품명과 티저 영상 1개 표시',876,224,340,100,25);
txt(com,'점검한 페이지의 한계',876,367,340,45,27,C.purple,true);
txt(com,'소개·제작진·출연진 및\n회차 텍스트 정보 미확인\n\n다른 공개 출처로 보완 검토',876,427,340,170,24);
footer(com,'점검 URL: com2usn.com/work/255 / 이 사례는 확인한 작품 페이지에 한정');

const mbc=add('MBC 충북: 기사 정보와 뉴스 원고 확인',`캡처: ${root}/reports/1/mbc충북_뉴스세부.png\n${root}/reports/1/mbc충북_뉴스세부2.png\n원문: https://news.mbccb.co.kr/home/sub.php?menukey=61&mod=view&RECEIVE_DATE=20261011&SEQUENCE=0110&page=1&sccode=99999999&datepicker_st=&datepicker_ed=\n캡처에서 제목, 정재영 기자, 송고 2026-10-11 17:01, 임베드 영상, 앵커/인터뷰 포함 기사 원고, 영상 김현준 표기를 확인했습니다. 구조와 데이터 존재를 확인한 단계이며 MBC 충북의 자동 수집·정책 검증을 완료했다는 뜻은 아닙니다.`);
txt(mbc,'제목·기자·송고 시각·영상',64,137,550,40,27,C.purple,true);
txt(mbc,'앵커·인터뷰를 포함한 원고',666,137,550,40,27,C.purple,true);
await img(mbc,'mbc충북_뉴스세부.png',64,190,550,370,{left:675,top:280,width:845,height:715});
await img(mbc,'mbc충북_뉴스세부2.png',666,190,550,370,{left:690,top:840,width:840,height:485});
txt(mbc,'소풍·교육 한 번에.. 아이 동반 명소로 변신한 청남대',64,578,1152,35,25,C.ink,true);
footer(mbc,'기사 송고: 2026.10.11 17:01 / 데이터 존재 확인 완료, 자동 수집 검증은 별도 진행');

const cjBase=old[2];title(cjBase,'CJ ENM: 포핸즈 기본 정보와 등장인물 설명');
await img(cjBase,'cjenm_detail1.png',64,142,392,488);
table(cjBase,[['항목','확보한 정보'],['기본 정보',`${cj.title}, tvN, ${cj.episode_count}회, ${cj.rating}`],['제작진','연출 박현석 / 극본 신이원'],['출연진',cj.cast.join(', ')],['등장인물','강비오(송강), 최정요(이준영)\n각 인물의 상세 설명'],['TVING 연결','P001790301 / 동일 작품 URL']],496,151,720,355,[175,545],23);
txt(cjBase,'프로그램 소개와 인물 설명을 구조화된 JSON으로 저장',496,539,720,83,27,C.purple,true);
footer(cjBase,'CJ ENM API 실측: 2026.10.12 / 두 응답에는 회차별 시놉시스 없음');
cjBase.speakerNotes.text=`캡처: ${root}/reports/1/cjenm_detail1.png\n원문: https://www.cjenm.com/ko/featured-contents/%ED%8F%AC%ED%95%B8%EC%A6%88/\n출처 JSON: ${root}/${cjDir}/content-metadata.json\nAPI는 프로그램 정보와 등장인물 2명 정보를 제공했습니다. 전체 등장인물 완전성은 검증하지 않았습니다. 이미지 필드는 정규화 결과에서 제외했습니다.`;

const api=add('CJ ENM API: 쿠키·인증 없이 직접 조회 성공',`브라우저 캡처: ${root}/reports/1/cjenm_console1.png\n실측 보고서: ${root}/${cjDir}/verification-report.json\n응답 비교: ${root}/${cjDir}/response-comparison.json\n프로그램 GET https://web2-cf-api.cjenm.com/apis/v1/conts/detail?pgmSeq=220264&svcCd=SV001&siteCd=ST000001&ctgCd=MC010003\n등장인물 GET https://web2-cf-api.cjenm.com/apis/v1/conts/detail/prsn?pgmSeq=220264\nPython urllib의 직접 HTTP 요청입니다. User-Agent BroadcastMetadataVerifier/1.0, Accept application/json만 전송했습니다. Cookie, Authorization, Origin, Referer 없이 두 API 모두 HTTP 200, resultCd 0000 응답. 사용자 저장 JSON과 파싱 후 전체 내용 일치. 해당 작품의 두 요청에 한정되며 다른 작품·반복·대량 수집·URL 식별자 자동 추출을 검증한 결과는 아닙니다.`);
await img(api,'cjenm_console1.png',64,163,525,370,{left:680,top:230,width:690,height:660});
txt(api,'프로그램 정보 / 등장인물 정보',634,145,582,44,28,C.purple,true);
table(api,[['검증 조건','두 API의 결과'],['직접 HTTP 요청','200 OK / resultCd 0000'],['브라우저·로그인','사용하지 않음'],['Cookie·Authorization','사용하지 않음'],['기존 응답 비교','JSON 내용 동일']],634,214,582,300,[275,307],23);
txt(api,'조회와 JSON 저장은 기술적으로 가능',64,570,1152,50,31,C.purple,true);
footer(api,'검증 시각: 2026.10.12 08:56 KST / 검증 범위: 포핸즈의 두 API 요청');

const policy=add('CJ ENM: 기술적 조회 가능성과 수집 정책',`사용자 메인 사이트 캡처: ${root}/reports/1/cjenm_robots.png\n캡처 주소 cjenm.com/robots.txt는 기본 제한과 특정 봇에 대한 허용 예외를 함께 보여줍니다.\nAPI 호스트 실측: https://web2-cf-api.cjenm.com/robots.txt\n저장 근거: ${root}/${cjDir}/robots.txt\nAPI 호스트는 User-Agent: * / Disallow: /만 반환했습니다. robots.txt는 접근 차단 장치가 아니며 이번 직접 호출은 실제 성공했습니다. 본 자료는 법률상 금지 또는 공식 공개 API 제공을 단정하지 않습니다. 지속 자동 수집 적용에는 허용 범위 확인이 필요합니다.`);
await img(policy,'cjenm_robots.png',64,149,302,477);
txt(policy,'API 호스트의 robots.txt 실측',415,150,801,42,29,C.purple,true);
txt(policy,'User-Agent: *\nDisallow: /',415,218,801,89,29,C.ink,true);
txt(policy,'직접 조회: 성공',415,345,801,42,30,C.purple,true);
txt(policy,'robots.txt가 이번 API 요청을 기술적으로 차단하지 않음',415,399,801,63,25);
txt(policy,'정기·대량 수집 적용: 허용 범위 확인 후 결정',415,502,801,42,27,C.purple,true);
txt(policy,'API 호스트는 일반 크롤러의 전체 경로 수집 제한 명시',415,554,801,65,24);
footer(policy,'왼쪽: 메인 사이트 규칙 / 오른쪽: API 호스트 실측 / 조회 성공과 수집 허용은 구분');

const tvDetail=old[3];title(tvDetail,'TVING: 같은 포핸즈의 회차 정보로 보완');
await img(tvDetail,'cjenm_detail2.png',64,151,1152,288,{left:45,top:148,width:2460,height:948});
txt(tvDetail,'12개 회차의 제목·시놉시스·방송일·재생 시간 저장',64,465,1152,47,29,C.purple,true);
txt(tvDetail,'2화 소개 예시',64,529,210,38,24,C.ink,true);
txt(tvDetail,'비오는 정요를 의식적으로 멀리한다. 현수는 교습의 조건으로 정요와의 포핸즈를 내건다.',295,529,921,87,25);
footer(tvDetail,'CJ ENM 응답의 TVING URL로 연결 / 12개 회차 수집 근거: 2026.10.07 저장 JSON');
tvDetail.speakerNotes.text=`사용자 캡처 reports/1/cjenm_detail2.png는 이름과 달리 TVING 포핸즈 화면입니다.\n원문: https://www.tving.com/contents/P001790301\n실제 수집 JSON: ${root}/${tvPath}\n포핸즈의 episodes 배열 길이 12, 시놉시스 12개를 확인했습니다. 2화 소개 예시는 원문 시놉시스의 일부를 발표용으로 요약했습니다. 회차 시놉시스는 대본이 아닙니다. 이번 요청에서 TVING을 다시 호출한 결과가 아니라 저장된 수집 데이터 기준입니다.`;

const tvApi=add('TVING API 응답: 회차별 필드 확인',`캡처: ${root}/reports/1/tving_drama_detail2.png\n${root}/reports/1/tving_drama_detail3.png\n작품 URL: https://www.tving.com/contents/P001790301\nepisode.code/frequency/broadcast_date/synopsis.ko/duration 필드와 1·2화 데이터를 확인했습니다. 화면의 header.status 200은 JSON 내부 값이며 HTTP 상태를 나타내는 Headers 캡처와 구분합니다.\n저장 JSON: ${root}/${tvPath}`);
txt(tvApi,'1화 응답',64,143,550,40,27,C.purple,true);
txt(tvApi,'2화 응답',666,143,550,40,27,C.purple,true);
await img(tvApi,'tving_drama_detail2.png',64,191,550,316,{left:699,top:291,width:875,height:729});
await img(tvApi,'tving_drama_detail3.png',666,191,550,316,{left:714,top:322,width:875,height:538});
txt(tvApi,'회차 번호 / 제목 / 방송일 / 시놉시스 / 재생 시간',64,536,1152,44,29,C.purple,true);
txt(tvApi,'1화: 2026.08.29, 4,072초      2화: 2026.08.30, 3,570초',64,592,1152,40,25);
footer(tvApi,'응답 필드: frequency, vod_name.ko, broadcast_date, synopsis.ko, duration');

const batch=add('TVING 드라마 전체: 상위 20개 수집 결과',`사용자 화면: ${root}/reports/1/tving_drama1.png\n원문: https://www.tving.com/more/genre/PCA\n실제 집계: ${root}/data/tving/20261007_210908_251349_드라마_전체/collection-report.json\n2026-10-07 저장 배치의 성공 작품 20, 수집 회차 341, 시놉시스 있는 회차 341. 화면 캡처의 작품 순서는 해당 과거 배치 순서를 증명하지 않습니다. 작품별 전체 시즌의 완전성을 뜻하지 않습니다.`);
await img(batch,'tving_drama1.png',64,152,705,447,{left:50,top:193,width:2450,height:1085});
txt(batch,'2026.10.07 저장 배치',821,153,395,43,28,C.purple,true);
table(batch,[['항목','결과'],['작품','20개'],['회차','341개'],['회차 시놉시스','341개']],821,227,395,257,[250,145],24);
txt(batch,'포핸즈 포함\n12개 회차 시놉시스 확보',821,535,395,88,25);
footer(batch,'왼쪽 캡처는 목록 구조 예시 / 집계와 당시 순위는 저장된 수집 보고서 기준');

const wikiSlide=old[4];title(wikiSlide,'나무위키: 기존 수집 검증과 포핸즈 보완 범위');
txt(wikiSlide,'기존 수집 검증\n냉장고를 부탁해',64,140,584,74,27,C.purple,true);
table(wikiSlide,[['항목','저장된 값'],['방송사 / 제작사',`${wiki.channel} / ${wiki.production_company}`],['진행자',wiki.hosts.join(', ')],['총 회차 수','254회 (시즌 1)'],['관련 문서','링크 저장, 하위 문서 미수집']],64,222,584,297,[195,389],23);
txt(wikiSlide,'포핸즈의 위키 문서 보완',704,145,512,77,27,C.purple,true);
txt(wikiSlide,'사용자가 본문과 하위 문서 존재 확인\n\n관련 문서를 사람이 확인하고 선택\n선택한 URL에서 추가 데이터 수집\n문서별 출처를 유지해 비교·분석',704,259,512,227,25);
txt(wikiSlide,'포핸즈 본문·하위 문서의 수집은 후속 검증',704,538,512,82,24,C.purple,true);
footer(wikiSlide,'나무위키 캡처는 제공 폴더에 없음 / 기존 사례 2026.10.08, 포핸즈 보완은 계획');
wikiSlide.speakerNotes.text=`기존 수집 근거: ${root}/${wikiPath}\n위키 포핸즈 URL: https://namu.wiki/w/%ED%8F%AC%ED%95%B8%EC%A6%88\n포핸즈 본문 및 하위 문서 존재는 사용자 직접 확인 근거입니다. 도구 조회는 실패했으므로 구체적 하위 문서 목록이나 수집 결과는 검증 완료로 제시하지 않습니다. 현재 namuwiki.py는 관련 문서 링크 저장까지 지원하며 선택 문서 추가 수집 UI는 후속 구현입니다. 폴더 reports/1에는 나무위키 캡처가 없습니다. 냉장고를 부탁해의 254회는 시즌 1 정보이고 episodes 배열은 비어 있습니다.`;

const app=old[5];title(app,'출처별 정보 보완과 수집 도구');
const appBytes=await fs.readFile(path.join(root,'reports/desktop/studio.png'));
app.images.add({blob:appBytes.buffer.slice(appBytes.byteOffset,appBytes.byteOffset+appBytes.byteLength),contentType:'image/png',alt:'Electron React Python 수집 앱',fit:'contain',position:{left:64,top:153,width:673,height:444}});
txt(app,'포핸즈의 출처별 역할',787,153,429,44,29,C.purple,true);
txt(app,'CJ ENM\n작품 기본 정보·제작진·등장인물\n\nTVING\n12개 회차의 세부 정보\n\n나무위키\n사람이 확인한 문서로 추가 보완',787,215,429,303,25);
txt(app,'출처·수집일을 유지하고 불일치 검토',787,562,429,65,23,C.purple,true);
footer(app,'TVING·나무위키 URL 입력 도구 구현 / CJ ENM은 별도 API 검증 완료, 앱 연결은 후속 작업');
app.speakerNotes.text=`앱 캡처: ${root}/reports/desktop/studio.png\n기존 Electron React Python 앱입니다. CJ ENM의 두 API 검증 스크립트는 별도이며 앱의 URL 라우팅에 CJ ENM을 연결하지 않았습니다.\nCJ ENM의 pgmReplayUrlAddr로 TVING 작품 식별자를 연결합니다. TVING director 배열에는 작가 등 역할이 혼재할 수 있으므로 원본을 유지하고 CJ ENM의 pdNm/writrNm 및 seoData와 비교합니다. 나무위키 값으로 자동 덮어쓰기하지 않고 출처별 값을 유지합니다.`;

const appendix=add('참고: 목록 페이지와 TVING 작품 응답',`추가 캡처: ${root}/reports/1/mbc충북_뉴스탭.png\n${root}/reports/1/tving_drama_detail1.png\nMBC 뉴스 목록 원문: https://news.mbccb.co.kr/home/sub.php?menukey=61\nTVING 작품: https://www.tving.com/contents/P001790301\nMBC 목록의 제목·기자·시각·미리보기, TVING 응답의 출연진·작품 소개 등의 존재를 확인합니다. TVING director 필드에 제작 역할이 혼재할 가능성이 있으므로 연출·작가를 그대로 확정하지 말고 출처별 비교가 필요합니다.`);
txt(appendix,'MBC 충북 뉴스 목록',64,142,550,42,28,C.purple,true);
txt(appendix,'TVING 작품 메타데이터 응답',666,142,550,42,28,C.purple,true);
await img(appendix,'mbc충북_뉴스탭.png',64,198,550,330,{left:670,top:270,width:865,height:790});
await img(appendix,'tving_drama_detail1.png',666,198,550,330,{left:726,top:293,width:735,height:545});
txt(appendix,'뉴스 항목별 제목·기자·시각 표시',64,564,550,63,24);
txt(appendix,'출연진·소개 존재, 제작 역할은 비교 필요',666,564,550,63,24);
footer(appendix,'캡처 원본은 reports/1에 보관 / 상세 출처와 검증 범위는 각 슬라이드의 발표자 노트에 기재');

const order=[old[0],old[1],com,mbc,cjBase,api,policy,tvDetail,tvApi,batch,wikiSlide,app,appendix];
deck.slides.reorder(order.map(s=>`sl/${s.id}`));
for(const [i,s] of deck.slides.items.entries()){
 const page=s.shapes.items.find(x=>x.position.left>=1160&&x.position.top>=660);
 if(page)page.text=String(i+1).padStart(2,'0');else txt(s,String(i+1).padStart(2,'0'),1170,666,45,26,17,C.muted);
}
await fs.writeFile(path.join(build,'media-manifest.json'),JSON.stringify(evidence.map(x=>({...x,slide:order.findIndex(s=>s.id===x.slide_id)+1})),null,2));
const candidate=path.join(build,'candidate.pptx');
await (await PresentationFile.exportPptx(deck)).save(candidate);
for(const [i,s] of deck.slides.items.entries()){
 const blob=await deck.export({slide:s,format:'png',scale:1});
 await fs.writeFile(path.join(build,`slide-${i+1}.png`),new Uint8Array(await blob.arrayBuffer()));
}
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const tables=[2,5,6,10,11];
const result=await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:path.join(root,'presentations/방송콘텐츠_메타데이터_수집검증_20261012_최종.pptx'),explicitTotalSlideCount:13,requiredNativeTableOwnerSlides:tables,pythonExecutable:'C:/Users/moon/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit',...tables.flatMap(n=>['--require-native-table-slide',String(n)])],fontPolicy:{basis:'design',families:[FONT]},verifyArtifactToolImport:true,receiptPath:path.join(build,'validation-final.json')});
console.log(JSON.stringify(result));

