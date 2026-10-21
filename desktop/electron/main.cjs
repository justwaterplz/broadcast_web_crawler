const { app, BrowserWindow, ipcMain, shell, dialog, session } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const { randomBytes } = require('node:crypto');
const { pathToFileURL } = require('node:url');
const { containedPath } = require('./paths.cjs');
const { loadSelectedResponses } = require('./cjenm-files.cjs');

const projectRoot = path.resolve(__dirname, '../..');
const outputRoot = path.join(projectRoot, 'data');
const token = randomBytes(32).toString('hex');
const smoke = process.argv.includes('--smoke-test');
let backend;
let window;
let baseUrl;
let backendLog = '';
let stopping = false;

async function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
  });
}

async function api(route, body) {
  const response = await fetch(baseUrl + route, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(route === '/inspect' ? 40000 : 15000),
  });
  const result = await response.json();
  if (!response.ok) {
    throw new Error(typeof result.detail === 'string' ? result.detail : JSON.stringify(result.detail));
  }
  return result;
}

async function startBackend() {
  const port = await freePort();
  const venv = path.join(projectRoot, '.venv', 'Scripts', 'python.exe');
  const python = process.env.BROADCAST_PYTHON || (fs.existsSync(venv) ? venv : 'python');
  baseUrl = `http://127.0.0.1:${port}`;
  backend = spawn(python, ['-X', 'utf8', '-m', 'broadcast_web_crawler.desktop_api',
    '--port', String(port), '--output-root', outputRoot], {
    cwd: projectRoot,
    env: { ...process.env, BROADCAST_DESKTOP_TOKEN: token,
      PYTHONPATH: [path.join(projectRoot, 'src'), process.env.PYTHONPATH].filter(Boolean).join(path.delimiter) },
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  backend.stdout.on('data', chunk => { backendLog = (backendLog + chunk).slice(-6000); });
  backend.stderr.on('data', chunk => { backendLog = (backendLog + chunk).slice(-6000); });
  let spawnError;
  backend.on('error', err => { spawnError = err; });
  backend.on('exit', () => {
    if (!stopping && window) window.webContents.send('studio:backend-stopped');
  });
  for (let i = 0; i < 100; i++) {
    if (spawnError || backend.exitCode !== null) break;
    try { await api('/health'); return; } catch { /* Wait for Python startup. */ }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error(`Python 수집기를 시작하지 못했습니다. Python 의존성을 확인해 주세요.\n${spawnError || backendLog}`);
}

function registerIPC() {
  const handlers = {
    'studio:health': () => api('/health'),
    'studio:inspect': (_, payload) => api('/inspect', payload),
    'studio:cjenm-files': async (_, url) => {
      const parsed = new URL(url);
      if (parsed.protocol !== 'https:' || !['www.cjenm.com', 'cjenm.com'].includes(parsed.hostname)) throw new Error('CJ ENM 공식 URL을 입력해 주세요.');
      const selected = await dialog.showOpenDialog(window, { title: 'CJ ENM 작품 응답과 등장인물 응답 선택',
        properties: ['openFile', 'multiSelections'], filters: [{ name: 'JSON 응답', extensions: ['json', 'txt'] }] });
      if (selected.canceled) return null;
      const payload = { url, ...loadSelectedResponses(selected.filePaths) };
      return { payload, inspection: await api('/cjenm/inspect', payload) };
    },
    'studio:cjenm-import': (_, payload) => api('/cjenm/import', payload),
    'studio:submit': (_, payload) => api('/jobs', payload),
    'studio:job': (_, id) => {
      if (!/^[0-9a-f-]{36}$/.test(id)) throw new Error('Invalid job ID');
      return api(`/jobs/${id}`);
    },
    'studio:collections': () => api('/collections'),
    'studio:hide': (_, candidate) => api('/collections/hide', { path: containedPath(outputRoot, candidate) }),
    'studio:restore': (_, candidate) => api('/collections/restore', { path: containedPath(outputRoot, candidate) }),
    'studio:inventory': (_, payload) => api('/inventory/jobs', payload),
    'studio:inventories': () => api('/inventories'),
    'studio:read': (_, candidate) => api('/read', { path: containedPath(outputRoot, candidate) }),
    'studio:view': (_, candidate, index) => api('/view', { path: containedPath(outputRoot, candidate), ...(index === undefined ? {} : { program_index: index }) }),
    'studio:open-folder': async (_, candidate) => {
      const resolved = containedPath(outputRoot, candidate);
      const folder = fs.statSync(resolved).isDirectory() ? resolved : path.dirname(resolved);
      const error = await shell.openPath(folder);
      if (error) throw new Error(error);
    },
  };
  for (const [channel, handler] of Object.entries(handlers)) {
    ipcMain.handle(channel, (event, ...args) => {
      if (!window || event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame) {
        throw new Error('Untrusted IPC sender');
      }
      return handler(event, ...args);
    });
  }
}

async function smokeTest() {
  await new Promise(resolve => setTimeout(resolve, 1800));
  const health = await api('/health');
  const collections = await api('/collections');
  if (!collections.length) throw new Error('Smoke test requires a saved collection');
  const sample = await api('/view', { path: collections[0].file });
  if (!sample.programs?.length) throw new Error('Stored content could not be read');
  const content = await window.webContents.executeJavaScript('document.body.innerText');
  if (!content.includes('방송 메타데이터') || !content.includes('수집 시작')) {
    throw new Error('React interface did not render');
  }
  const interactions = await window.webContents.executeJavaScript(`(async () => {
    const pause = () => new Promise(resolve => setTimeout(resolve, 150));
    const assert = (condition, message) => { if (!condition) throw new Error(message); };
    const activateTab = node => {
      node.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, button: 0 }));
      node.click();
    };
    assert(document.querySelectorAll('[data-slot="card"]').length === 2, 'shadcn cards missing');
    assert(document.querySelector('#url[data-slot="input"]'), 'shadcn URL input missing');
    const checkbox = document.querySelector('#all-programs');
    checkbox.click(); await pause();
    assert(checkbox.getAttribute('aria-checked') === 'true', 'Checkbox did not update');
    assert(document.querySelector('#limit').disabled && document.querySelector('#pages'),
      'All-program scope did not update');
    checkbox.click(); await pause();
    assert(!document.querySelector('#limit').disabled && document.querySelector('#pages'),
      'Bounded scope did not restore');
    const triggers = [...document.querySelectorAll('[role="tab"]')];
    assert(triggers.length === 4, 'shadcn result tabs missing');
    activateTab(triggers[1]); await pause();
    assert(document.querySelector('[aria-label="회차 검색"]'), 'Episode tab did not render');
    triggers[2].dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, key: 'Enter' }));
    await pause();
    const jsonText = document.querySelector('[role="tabpanel"][data-state="active"] pre')?.textContent;
    assert(jsonText && (JSON.parse(jsonText).programs || JSON.parse(jsonText).contentInfo || JSON.parse(jsonText).modules || JSON.parse(jsonText).programResponse),
      'JSON tab did not show stored contents');
    activateTab(triggers[3]);
    for (let i = 0; i < 30; i++) {
      await pause();
      if (triggers[3].getAttribute('aria-selected') === 'true') break;
    }
    assert(triggers[3].getAttribute('aria-selected') === 'true', 'Collection report did not load');
    activateTab(triggers[0]); await pause();
    const examples = [...document.querySelectorAll('.examples button')];
    examples[2].click(); await pause();
    assert(document.querySelector('#url').value.includes('namu.wiki/w/'), 'Wiki URL example failed');
    assert(!document.querySelector('#all-programs'), 'Wiki URL kept TVING controls');
    examples[0].click(); await pause();
    assert(document.querySelector('#all-programs'), 'TVING scope did not restore');
    assert(document.querySelector('.inventory-panel'), 'Inventory controls missing');
    const collectButton = document.querySelector('button[type="submit"]');
    assert(collectButton.disabled, 'Official URL collection must wait for target review');
    document.querySelector('.url-row button').click();
    for (let i = 0; i < 240 && !document.querySelector('#confirm-target'); i++) await pause();
    const confirm = document.querySelector('#confirm-target');
    assert(confirm, 'Official source preview did not render');
    assert(collectButton.disabled, 'Unconfirmed preview must not start collection');
    confirm.click(); await pause();
    assert(!collectButton.disabled, 'Confirmed official URL must enable collection');
    assert(getComputedStyle(document.documentElement).getPropertyValue('--primary').trim() === '#171717',
      'Monochrome theme missing');
    const before = document.querySelectorAll('.library-item').length;
    document.querySelector('.library-item').dispatchEvent(new MouseEvent('contextmenu', {
      bubbles: true, cancelable: true, button: 2, clientX: 100, clientY: 260,
    }));
    await pause();
    const deleteItem = [...document.querySelectorAll('[role="menuitem"]')].find(node => node.textContent.includes('이력에서 삭제'));
    assert(deleteItem, 'History context menu missing');
    deleteItem.click();
    for (let i = 0; i < 30 && document.querySelectorAll('.library-item').length !== before - 1; i++) await pause();
    assert(document.querySelectorAll('.library-item').length === before - 1, 'History was not hidden');
    document.querySelector('.history-undo button').click();
    for (let i = 0; i < 30 && document.querySelectorAll('.library-item').length !== before; i++) await pause();
    assert(document.querySelectorAll('.library-item').length === before, 'History undo failed');
    document.querySelector('.library-item').click();
    for (let i = 0; i < 30 && !document.querySelector('[role="tab"]'); i++) await pause();
    return { cards: true, checkbox: true, tabs: true, report: true, sourceRouting: true,
      historyMenu: true, historyUndo: true, inventoryControls: true, monochromeTheme: true,
      directUrlReview: true };
  })()`);
  const errors = await window.webContents.executeJavaScript('window.__studioErrors || []');
  if (errors.length) throw new Error(errors.join('\n'));
  let live;
  if (process.argv.includes('--live-test')) {
    const submitted = await api('/jobs', { url: 'https://www.tving.com/contents/P001790587' });
    for (let i = 0; i < 120; i++) {
      await new Promise(resolve => setTimeout(resolve, 500));
      live = await api(`/jobs/${submitted.id}`);
      if (['completed', 'failed'].includes(live.status)) break;
    }
    if (live.status !== 'completed') throw new Error(live.error || 'Live collection timed out');
    const saved = await api('/view', { path: live.content_file });
    if (!saved.programs?.[0]?.episodes?.length) throw new Error('Live episode data was not saved');
    console.log(`Live collection passed: ${saved.programs[0].episodes.length} episodes saved`);
  }
  const reportDir = path.join(projectRoot, 'reports', 'desktop');
  fs.mkdirSync(reportDir, { recursive: true });
  const shot = await window.webContents.capturePage();
  fs.writeFileSync(path.join(reportDir, 'studio.png'), shot.toPNG());
  fs.writeFileSync(path.join(reportDir, 'smoke.json'), JSON.stringify({
    status: 'passed', backend: health.status, savedCollections: collections.length,
    rendered: true, interactions, liveCollection: live,
    screenshot: path.join(reportDir, 'studio.png'),
  }, null, 2));
  console.log('Electron smoke test passed: backend, saved JSON, React rendering, screenshot');
  stopping = true;
  app.quit();
}

app.whenReady().then(async () => {
  await startBackend();
  session.defaultSession.setPermissionRequestHandler((_, __, callback) => callback(false));
  window = new BrowserWindow({
    width: 1440, height: 960, minWidth: 1040, minHeight: 740,
    title: '방송 메타데이터 스튜디오', backgroundColor: '#f7f7f7', show: !smoke,
    autoHideMenuBar: true,
    webPreferences: { preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false, contextIsolation: true, sandbox: true },
  });
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('will-navigate', event => event.preventDefault());
  registerIPC();
  const renderer = process.env.ELECTRON_RENDERER_URL;
  if (renderer && renderer !== 'http://127.0.0.1:5173') throw new Error('Unexpected renderer URL');
  await window.loadURL(renderer || pathToFileURL(path.join(__dirname, '../dist/index.html')).href);
  if (smoke) await smokeTest();
}).catch(err => {
  console.error(err.message);
  if (!smoke) dialog.showErrorBox('앱을 시작하지 못했습니다', err.message);
  stopping = true;
  app.exit(1);
});

app.on('before-quit', () => { stopping = true; backend?.kill(); });
app.on('window-all-closed', () => app.quit());
process.on('exit', () => backend?.kill());
