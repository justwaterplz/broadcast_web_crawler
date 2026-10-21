import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { NativeSelect } from '@/components/ui/native-select';
import { Checkbox } from '@/components/ui/checkbox';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { ContextMenu, ContextMenuTrigger, ContextMenuContent, ContextMenuItem, ContextMenuLabel } from '@/components/ui/context-menu';
import { ArrowRight, ExternalLink, RefreshCw, X, AlertCircle, Trash2, Undo2, ListChecks } from 'lucide-react';
import './style.css';

window.__studioErrors = [];
window.addEventListener('error', e => window.__studioErrors.push(e.message));
window.addEventListener('unhandledrejection', e => window.__studioErrors.push(String(e.reason)));
const studio = window.studio;
const examples = [
  ['TVING 드라마 전체', 'https://www.tving.com/more/genre/PCA'],
  ['TVING 예능 전체', 'https://www.tving.com/more/genre/PCD'],
  ['나무위키 · 냉장고를 부탁해', 'https://namu.wiki/w/냉장고를%20부탁해'],
  ['tvN 전체 프로그램', 'https://tvn.cjenm.com/ko/program/'],
];
function identify(value) {
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:') return null;
    if (['www.cjenm.com', 'cjenm.com'].includes(url.hostname) && /^\/(ko|en)\/featured-contents\/[^/]+/.test(url.pathname)) return 'cjenm_detail';
    if (url.hostname === 'tvn.cjenm.com' && /^\/ko\/[A-Za-z0-9_-]+/.test(url.pathname)) return url.pathname.startsWith('/ko/program/') || url.pathname === '/ko/program' ? 'tvn_category' : 'tvn_detail';
    if (url.hostname === 'namu.wiki' && url.pathname.startsWith('/w/')) return 'namuwiki';
    if (['tving.com', 'www.tving.com'].includes(url.hostname)) {
      if (/^\/contents\/[PE]\d+/.test(url.pathname)) return 'tving_detail';
      if (url.pathname.startsWith('/more/genre/')) return 'tving_category';
    }
  } catch { /* Incomplete input. */ }
  return null;
}
const text = value => Array.isArray(value) ? value.map(v => typeof v === 'object' ? (v.name || JSON.stringify(v)) : v).join(' · ') : (value || '—');
const date = value => value ? new Date(value).toLocaleString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';

function sameSourceUrl(left, right) {
  try {
    const normalize = value => {
      const parsed = new URL(value);
      parsed.pathname = parsed.pathname.replace(/\/$/, ''); parsed.hash = ''; parsed.searchParams.sort();
      return parsed.href;
    };
    return normalize(left) === normalize(right);
  } catch { return false; }
}

function App() {
  const [health, setHealth] = useState(null);
  const [url, setUrl] = useState(examples[0][1]);
  const [category, setCategory] = useState('drama');
  const [limit, setLimit] = useState(20);
  const [rank, setRank] = useState(1);
  const [all, setAll] = useState(false);
  const [pages, setPages] = useState(500);
  const [checking, setChecking] = useState(false);
  const [inspection, setInspection] = useState(null);
  const [confirmedTarget, setConfirmedTarget] = useState(false);
  const [cjenmInput, setCjenmInput] = useState(null);
  const [error, setError] = useState('');
  const [job, setJob] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [collections, setCollections] = useState([]);
  const [file, setFile] = useState('');
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(0);
  const [tab, setTab] = useState('content');
  const [query, setQuery] = useState('');
  const [report, setReport] = useState(null);
  const [lastHidden, setLastHidden] = useState(null);
  const [inventory, setInventory] = useState(null);
  const [viewBusy, setViewBusy] = useState(false);
  const kind = identify(url);
  const listingKind = ['tving_category', 'tvn_category'].includes(kind);
  const officialKind = kind && kind !== 'namuwiki';
  const inspectionReady = inspection?.status === 'ready' && sameSourceUrl(inspection.url, url.trim()) && inspection.kind === kind;
  const canCollect = !officialKind || (inspectionReady && confirmedTarget);
  const active = submitting || ['queued', 'running'].includes(job?.status);
  const programs = data?.programs || [];
  const program = programs[selected];
  const episodes = program?.episodes || [];
  const sourceParts = file.split(/[/\\]/);
  const wikiResult = sourceParts.includes('namuwiki');
  const tvingResult = sourceParts.includes('tving');
  const tvnResult = sourceParts.includes('tvn');
  const selectedSource = data?.source_documents?.[selected];
  const matchingInventory = listingKind && inventory?.complete_listing && sameSourceUrl(inventory.source_url, url.trim()) && inventory.category === (kind === 'tvn_category' ? 'tvn' : category);
  const payload = () => ({ url: url.trim(), category, limit: Number(limit), start_rank: Number(rank), all_programs: all, max_pages: Number(pages), require_review: Boolean(officialKind), review_id: inspection?.review_id, confirmed_target: confirmedTarget, ...(matchingInventory ? { inventory_file: inventory.file } : {}) });
  async function openResult(path, index = 0, keepTab = false) {
    setViewBusy(true);
    try {
      const result = await studio.view(path, index);
      setData(result); setFile(path); setSelected(index); if (!keepTab) { setTab('content'); setReport(null); } setQuery('');
    } catch (e) { setError(e.message); }
    finally { setViewBusy(false); }
  }
  async function refresh(loadFirst = false) {
    try {
      const items = await studio.collections();
      setCollections(items);
      if (loadFirst && items.length) await openResult(items[0].file);
    } catch (e) { setError(e.message); }
  }
  async function refreshInventory() {
    try {
      const items = await studio.inventories();
      const match = items.find(item => sameSourceUrl(item.source_url, url.trim()) && item.category === (kind === 'tvn_category' ? 'tvn' : category));
      setInventory(match || null);
    } catch (e) { setError(e.message); }
  }
  async function hideCollection(item) {
    try {
      await studio.hide(item.file); setLastHidden(item);
      if (file === item.file) { setFile(''); setData(null); setReport(null); }
      await refresh();
    } catch (e) { setError(e.message); }
  }
  async function restoreCollection() {
    try { await studio.restore(lastHidden.file); setLastHidden(null); await refresh(); }
    catch (e) { setError(e.message); }
  }
  async function scanInventory() {
    setError(''); setSubmitting(true);
    try { setJob(await studio.inventory(payload())); }
    catch (e) { setError(e.message); }
    finally { setSubmitting(false); }
  }
  useEffect(() => {
    studio.health().then(setHealth).catch(e => setError(e.message));
    refresh(true);
  }, []);
  useEffect(() => { if (listingKind) refreshInventory(); else setInventory(null); }, [url, category]);
  useEffect(() => {
    if (!job || !['queued', 'running'].includes(job.status)) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const next = await studio.job(job.id);
        if (cancelled) return;
        setJob(next);
        if (next.status === 'completed') {
          if (['tving_inventory', 'tvn_inventory'].includes(next.kind)) await refreshInventory();
          else { await refresh(); await openResult(next.content_file); }
        }
        if (next.status === 'failed') { setError(next.error); await refresh(); }
      } catch (e) { if (!cancelled) { setError(e.message); setJob(j => ({ ...j, status: 'failed', stage: '수집기 연결이 끊겼습니다.' })); } }
    }, 900);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [job]);
  function changeUrl(value) {
    setUrl(value); setInspection(null); setConfirmedTarget(false); setCjenmInput(null); setError('');
    if (value.includes('/genre/PCD')) setCategory('entertainment');
    if (value.includes('/genre/PCA')) setCategory('drama');
  }
  function changeCategory(value) {
    setCategory(value);
    setInspection(null); setConfirmedTarget(false);
    if (/\/more\/genre\/(PCA|PCD)\/?$/.test(url)) {
      setUrl(`https://www.tving.com/more/genre/${value === 'drama' ? 'PCA' : 'PCD'}`);
      setInspection(null);
    }
  }
  async function inspect() {
    setChecking(true); setError(''); setConfirmedTarget(false); setInspection(null);
    try {
      const result = await studio.inspect(payload());
      if (result.url) setUrl(result.url);
      setInspection(result);
    } catch (e) { setError(e.message); }
    finally { setChecking(false); }
  }
  async function submit(event) {
    event.preventDefault(); setError('');
    if (!canCollect) { setError('URL 확인 후 대상 작품 또는 목록을 확인해 주세요.'); return; }
    setSubmitting(true);
    try {
      if (kind === 'cjenm_detail') {
        if (!cjenmInput || !canCollect) throw new Error('응답 파일의 작품을 확인해 주세요.');
        const result = await studio.importCjenm({ ...cjenmInput, url: url.trim(), review_id: inspection.review_id, confirmed_target: confirmedTarget });
        setJob(result); await refresh(); await openResult(result.content_file);
      } else setJob(await studio.submit(payload()));
    } catch (e) { setError(e.message); }
    finally { setSubmitting(false); }
  }
  async function selectCjenmFiles() {
    setError(''); setChecking(true); setConfirmedTarget(false);
    try {
      const selected = await studio.cjenmFiles(url.trim());
      if (selected) { setCjenmInput(selected.payload); setUrl(selected.inspection.url); setInspection(selected.inspection); }
    } catch (e) { setError(e.message); }
    finally { setChecking(false); }
  }
  async function showReport() {
    try {
      const result = await studio.read(file.replace(/[^\\/]+$/, 'collection-report.json'));
      setReport(result); setTab('report');
    } catch (e) { setError(e.message); }
  }
  const inspectionMessage = inspection && ({ ready: '입력 URL의 대상을 확인했습니다. 아래 내용을 검수해 주세요.', manual_import_required: 'CJ ENM은 공식 URL에 대응하는 저장된 API 응답을 가져옵니다. 응답 파일을 선택해 주세요.', exists: '문서가 존재합니다. 수집을 시작할 수 있습니다.', supported: '지원하는 URL 형식입니다.', not_found: '해당 문서가 존재하지 않습니다.', access_denied: '사이트가 접근을 제한했습니다.', unknown: '문서 본문인지 확인할 수 없습니다.' }[inspection.status] || `확인 결과: ${inspection.status}`);
  return <div className="app">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">B<span>·</span></span><div>방송 메타데이터<small>COLLECTION STUDIO</small></div></div>
      <div className="nav-label">WORKSPACE</div>
      <div className="nav-item current"><span>◈</span> 콘텐츠 수집 <span className="nav-arrow">↗</span></div>
      <div className="library-heading">저장된 수집 <Button variant="ghost" size="icon-sm" type="button" aria-label="목록 새로고침" onClick={() => refresh()}><RefreshCw/></Button></div>
      <div className="library">{collections.map(item => <ContextMenu key={item.file}><ContextMenuTrigger asChild><Button variant="ghost" type="button" className={`library-item block h-auto w-full px-3 py-3 text-left whitespace-normal ${file === item.file ? 'chosen' : ''}`} onClick={() => openResult(item.file)}>
        <span className="library-source">{item.source} <span>{item.program_count}개 작품</span></span>
        <strong>{item.title}{item.program_count > 1 ? ` 외 ${item.program_count - 1}개` : ''}</strong>
        <small>{date(item.modified_at)}</small>
      </Button></ContextMenuTrigger><ContextMenuContent><ContextMenuLabel>저장된 JSON은 보존됩니다</ContextMenuLabel><ContextMenuItem onSelect={() => hideCollection(item)}><Trash2/>이력에서 삭제</ContextMenuItem></ContextMenuContent></ContextMenu>)}{!collections.length && <p className="empty-note">수집 결과가 여기에 쌓입니다.</p>}</div>
      {lastHidden && <div className="history-undo"><p>이력에서 삭제했습니다.<small>저장된 JSON은 유지됩니다.</small></p><Button variant="ghost" size="sm" onClick={restoreCollection}><Undo2/>되돌리기</Button></div>}
      <div className="local-status"><i className={health ? 'online' : ''}/><div>{health ? '로컬 수집기 연결됨' : '수집기 연결 확인 중'}<small>Electron · React · Python</small></div></div>
    </aside>
    <main>
      <header><div><p className="eyebrow">BROADCAST RESEARCH / METADATA</p><h1>방송 메타데이터 수집</h1><p className="subtitle">작품 URL을 입력하고, 프로그램 정보와 회차별 시놉시스를 모으세요.</p></div><span className="local-tag">LOCAL WORKSPACE</span></header>
      <Card className="input-card gap-0 px-6 py-6">
        <div className="section-heading"><h2><span className="step">01</span> 수집할 페이지</h2><Badge variant="secondary">{kind === 'namuwiki' ? '나무위키 · 문서' : kind === 'tving_category' ? 'TVING · 카테고리' : kind === 'tving_detail' ? 'TVING · 작품 상세' : kind === 'tvn_category' ? 'tvN · 프로그램 목록' : kind === 'tvn_detail' ? 'tvN · 작품 상세' : kind === 'cjenm_detail' ? 'CJ ENM · 응답 가져오기' : 'URL 입력'}</Badge></div>
        <form onSubmit={submit}>
          <Label className="field-label" htmlFor="url">콘텐츠 URL</Label>
          <div className="url-row"><Input className="h-11 flex-1" id="url" type="url" required value={url} onChange={e => changeUrl(e.target.value)} placeholder="https://…" disabled={active}/><Button type="button" variant="outline" className="h-11" disabled={!kind || checking || active || !health} onClick={inspect}>{checking ? '확인 중…' : 'URL 확인'}</Button></div>
          <div className="examples"><span>빠른 입력</span>{examples.map(([label, value]) => <Button variant="ghost" size="xs" type="button" key={value} disabled={active} onClick={() => changeUrl(value)}>{label}<ExternalLink className="size-3"/></Button>)}</div>
          {listingKind && <div className="scope">
            {kind === 'tving_category' && <div className="scope-field"><Label htmlFor="category">카테고리</Label><NativeSelect className="w-40" id="category" value={category} onChange={e => changeCategory(e.target.value)} disabled={active}><option value="drama">드라마</option><option value="entertainment">예능</option></NativeSelect></div>}
            <div className="scope-field"><Label htmlFor="rank">시작 순위</Label><Input id="rank" type="number" min="1" max="100000" required value={rank} onChange={e => setRank(e.target.value)} disabled={active}/></div>
            <div className="scope-field"><Label htmlFor="limit">{kind === 'tvn_category' ? '최대 수집 작품 수' : '수집 작품 수'}</Label><Input id="limit" type="number" min="1" max="1000" required value={limit} onChange={e => setLimit(e.target.value)} disabled={active || all}/></div>
            <div className="all-check"><Checkbox id="all-programs" checked={all} onCheckedChange={value => setAll(value === true)} disabled={active}/><Label htmlFor="all-programs">전체 작품 수집</Label></div>
            <div className="scope-field"><Label htmlFor="pages">최대 목록 페이지</Label><Input id="pages" type="number" min="1" max="500" required value={pages} onChange={e => setPages(e.target.value)} disabled={active}/></div>
          </div>}
          {listingKind && <div className="inventory-panel"><div><strong>{inventory ? `${inventory.unique_count.toLocaleString()}개 작품${inventory.complete_listing ? ' · 전체 목록 확인됨' : ' 이상 · 전체 수 미확정'}` : '전체 작품 수 확인'}</strong><p>{inventory ? `${inventory.pages_read}페이지 · ${date(inventory.checked_at)} 확인${inventory.error ? ` · ${inventory.error}` : ''}` : '다음 목록 주소를 끝까지 확인하고 작품 ID로 중복을 제외합니다.'}</p>{matchingInventory && <small>수집 시작 시 저장한 이 목록을 사용합니다. 전부 수집하려면 시작 순위 1과 전체 작품 수집을 선택하세요.</small>}</div><Button type="button" variant="outline" disabled={active || !health || checking || !canCollect} onClick={scanInventory}><ListChecks/>{inventory ? '목록 다시 확인' : '전체 목록 확인'}</Button></div>}
          {kind?.startsWith('tvn_') && <p className="notice">입력 URL의 채널·장르 필터를 사용합니다. 채널 탭 이름으로 작품 장르를 추정하지 않습니다.{listingKind && ' 목록은 1페이지부터 읽으며 시작 순위로 수집 구간을 선택합니다.'}</p>}
          {kind === 'cjenm_detail' && <div className="notice"><p>공식 작품 URL과 해당 작품의 JSON 응답 파일을 사용합니다. 이 기능은 네트워크 요청 없이 원본 응답을 저장합니다.</p><Button type="button" variant="outline" size="sm" disabled={active || checking || !health} onClick={selectCjenmFiles}>CJ ENM 응답 파일 선택</Button></div>}
          {inspectionReady && <div className="target-review"><strong>{inspection.site} · {inspection.title}</strong><p>{inspection.scope}{inspection.program_id ? ` · ID ${inspection.program_id}` : ''}{inspection.genre ? ` · ${inspection.genre}` : ''}</p><p className="review-url">{inspection.url}</p><div className="review-confirm"><Checkbox id="confirm-target" checked={confirmedTarget} onCheckedChange={value => setConfirmedTarget(value === true)} disabled={active}/><Label htmlFor="confirm-target">공식 페이지의 작품 또는 목록 범위가 맞는지 확인했습니다{kind === 'cjenm_detail' ? ' (선택한 응답 파일 포함)' : ''}.</Label></div></div>}
          {inspectionMessage && <p className={`notice ${['ready', 'exists', 'supported'].includes(inspection.status) ? '' : 'warning'}`}>{inspectionMessage}</p>}
          <div className="form-footer"><p>{kind === 'namuwiki' ? '입력한 문서의 방송 정보와 관련 링크를 저장합니다.' : kind?.startsWith('tvn_') ? 'tvN 작품 목록과 상세 페이지의 원본 메타데이터를 JSON으로 저장합니다.' : kind === 'cjenm_detail' ? '선택한 CJ ENM 응답 원본과 공식 URL을 연결해 JSON으로 저장합니다.' : 'TVING 원본 메타데이터와 회차 API 응답을 JSON으로 저장합니다.'}<small>{kind === 'namuwiki' ? '실행마다 새로운 폴더에 저장 · 이미지 경로 제외' : '실행마다 새로운 폴더에 저장 · 이미지는 다운로드하지 않습니다'}</small></p><Button size="lg" disabled={!kind || !health || active || checking || !canCollect} type="submit">{active ? '수집 진행 중…' : '수집 시작'}<ArrowRight/></Button></div>
        </form>
      </Card>
      {error && <Alert variant="destructive" className="mt-4 pr-12"><AlertCircle/><AlertTitle>확인이 필요합니다</AlertTitle><AlertDescription className="whitespace-pre-wrap">{error}</AlertDescription><Button variant="ghost" size="icon-sm" className="absolute right-2 top-2" onClick={() => setError('')} aria-label="메시지 닫기"><X/></Button></Alert>}
      {job && <section className={`job-strip ${job.status}`} aria-live="polite"><span className={active ? 'spinner' : 'job-dot'}/><div><strong>{job.stage}</strong><small>{job.processed != null ? `${job.processed} / ${job.total}개 작품` : date(job.started_at)}{job.status === 'completed' ? ' · 저장된 결과를 아래에서 확인하세요.' : ''}</small></div>{job.total > 0 && <Progress className="ml-auto w-44" aria-label="작품 수집 진행률" value={100 * (job.processed || 0) / job.total}/>}</section>}
      <Card className="results gap-0 p-0">
        <div className="section-heading"><h2><span className="step">02</span> 수집 결과 <Badge variant="outline">{programs.length}개 작품</Badge></h2><Button type="button" variant="ghost" size="sm" disabled={!file} onClick={() => studio.openFolder(file).catch(e => setError(e.message))}>저장 폴더 열기<ExternalLink/></Button></div>
        {!program ? <div className="empty-result">아직 선택한 결과가 없습니다.<small>수집을 시작하거나 왼쪽에서 저장된 결과를 선택하세요.</small></div> : <Tabs value={tab} onValueChange={value => value === "report" ? showReport() : setTab(value)} className="gap-0">
          <div className="result-toolbar"><NativeSelect className="w-64 max-w-full" aria-label="작품 선택" value={selected} disabled={viewBusy} onChange={e => openResult(file, Number(e.target.value), true)}>{programs.map((p, i) => <option key={i} value={i}>{p.title}</option>)}</NativeSelect><TabsList aria-label="수집 결과 보기"><TabsTrigger value="content">작품 정보</TabsTrigger><TabsTrigger value="episodes">{tvnResult ? '회차 미리보기' : '회차'} <Badge variant="secondary">{episodes.length}</Badge></TabsTrigger><TabsTrigger value="json">JSON</TabsTrigger><TabsTrigger value="report">수집 보고서</TabsTrigger></TabsList></div>
          <TabsContent value="content" className="content-preview">
            {tvingResult && selectedSource?.collection?.complete_for_current_api_listing === false && <Alert className="mb-6"><AlertCircle/><AlertTitle>회차 목록이 일부만 확보됐습니다</AlertTitle><AlertDescription>원본 응답은 저장했지만 전체 회차가 확보된 상태는 아닙니다. 수집 보고서와 API 응답의 전체 수를 확인해 주세요.</AlertDescription></Alert>}
            <div className="program-heading"><div><p className="eyebrow">PROGRAM METADATA</p><h3>{program.title}</h3></div><Badge variant="secondary">{text(program.content_type)}</Badge></div>
            {wikiResult && <Alert className="mb-6"><AlertCircle/><AlertTitle>검토가 필요한 위키 정보</AlertTitle><AlertDescription>콘텐츠 관계자 외에도 불특정 다수가 같은 문서를 작성·수정할 수 있습니다. 공식 출처와 대조하고 사실·평가를 구분한 뒤 사용해 주세요.</AlertDescription></Alert>}
            <dl className="metadata-grid">{[
              ['장르', program.genre], ['방송사 / 채널', program.channel],
              ...(tvnResult ? [['목록 채널 탭', program.channel_tab], ['방송 상태', program.broadcast_status], ['방송 안내', program.broadcast_schedule], ['등장인물', program.characters?.map(person => person.prsnNm)]] : []),
              [tvingResult ? '크리에이터' : '연출', tvingResult ? (program.director || program.directors || program.production_credits) : program.directors],
              ['작가 / 극본', program.writers], ['출연', program.cast],
              ['제작사', program.production_company], ['시청 등급', program.age_rating],
              ['제작 연도', program.production_year], ['방송 시작', program.broadcast_start_date],
              ['방송 종료', program.broadcast_end_date],
            ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{text(value)}</dd></div>)}</dl>
            <div className="synopsis"><h4>프로그램 소개</h4><p>{text(program.synopsis)}</p></div>
            <p className="missing-note">— 는 원문에서 제공하지 않거나 추출되지 않은 항목입니다. 회차 정보는 출처에서 제공하는 범위만 표시합니다.</p>
          </TabsContent>
          <TabsContent value="episodes" className="episode-preview">{tvnResult && <p className="missing-note">{program.episode_coverage}</p>}<div className="episode-heading"><p>{episodes.length}개 회차 · 시놉시스 {episodes.filter(e => e.synopsis).length}개</p><Input aria-label="회차 검색" placeholder="회차 제목 / 시놉시스 검색" value={query} onChange={e => setQuery(e.target.value)}/></div>{episodes.filter(e => `${e.number} ${e.title} ${e.synopsis}`.toLowerCase().includes(query.toLowerCase())).map((e, i) => <article className="episode" key={e.episode_id || i}><span className="episode-number">{e.number || i + 1}</span><div><h4>{e.title || `${e.number || i + 1}회`}<small>{e.broadcast_date || ''}</small></h4><p>{e.synopsis || '회차 시놉시스가 제공되지 않았습니다.'}</p></div></article>)}{!episodes.length && <p className="empty-result">이 출처에는 수집된 회차 정보가 없습니다.</p>}</TabsContent>
          <TabsContent value="json">{data?.source_documents && <p className="missing-note">선택한 작품의 metadata.json 원본입니다. 각 출처의 필드와 값을 유지하며, 작품 정보 탭의 표시용 정리본은 별도 파일로 저장하지 않습니다.</p>}<pre className="json-preview">{JSON.stringify(data?.source_documents?.[selected] || data, null, 2)}</pre></TabsContent><TabsContent value="report"><pre className="json-preview">{JSON.stringify(report, null, 2)}</pre></TabsContent>
          <div className="result-path" title={file}>{file}</div>
        </Tabs>}
      </Card>
      <footer>방송 · 미디어 콘텐츠 연구용 메타데이터 워크스페이스<span>CJ ENM / TVING / tvN / 나무위키</span></footer>
    </main>
  </div>;
}
createRoot(document.getElementById('root')).render(<App/>);

