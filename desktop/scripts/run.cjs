// Vite 8 needs Node >=22.12 (or >=20.19). Use the local bundled runtime when needed.
const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

const root = path.resolve(__dirname, '..');
const [major, minor] = process.versions.node.split('.').map(Number);
const supported = major > 22 || (major === 22 && minor >= 12) || (major === 20 && minor >= 19);
const bundled = path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe');
const node = process.env.BROADCAST_NODE || (supported ? process.execPath : fs.existsSync(bundled) ? bundled : null);
if (!node) {
  console.error('Node.js 22.12 이상이 필요합니다. BROADCAST_NODE로 실행 파일을 지정할 수도 있습니다.');
  process.exit(1);
}
const mode = process.argv[2] || 'start';
const vite = path.join(root, 'node_modules/vite/bin/vite.js');
const electron = path.join(root, 'node_modules/electron/cli.js');
const environment = { ...process.env };
delete environment.ELECTRON_RUN_AS_NODE;
function launch(args, env = environment) {
  return spawn(node, args, { cwd: root, stdio: 'inherit', windowsHide: true, env });
}
if (mode === 'dev') {
  const server = launch([vite, '--host', '127.0.0.1']);
  (async () => {
    for (let i = 0; i < 100; i++) {
      try {
        const response = await fetch('http://127.0.0.1:5173');
        if (response.ok) {
          const desktop = launch([electron, '.'], { ...environment, ELECTRON_RENDERER_URL: 'http://127.0.0.1:5173' });
          desktop.on('exit', code => { server.kill(); process.exit(code ?? 1); });
          return;
        }
      } catch { /* Wait for Vite. */ }
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    server.kill();
    console.error('Vite를 시작하지 못했습니다.');
    process.exit(1);
  })();
} else {
  const built = spawnSync(node, [vite, 'build'], { cwd: root, stdio: 'inherit', windowsHide: true });
  if (built.status !== 0) process.exit(built.status || 1);
  if (mode === 'build') process.exit(0);
  const flags = mode.startsWith('smoke') ? ['--smoke-test'] : [];
  if (mode === 'smoke-live') flags.push('--live-test');
  launch([electron, '.', ...flags]).on('exit', code => process.exit(code ?? 1));
}
