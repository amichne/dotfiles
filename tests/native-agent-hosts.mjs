// Explicit qualification: local canned responses only, with no paid model inference.
import assert from 'node:assert/strict';
import { execFile, execFileSync, spawn } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import readline from 'node:readline';
import { createRequire } from 'node:module';
import test from 'node:test';
import { pathToFileURL } from 'node:url';
import { promisify } from 'node:util';

const execute = promisify(execFile);
const root = path.resolve(import.meta.dirname, '..');
const required = name => {
  assert.ok(process.env[name], `missing explicit qualification dependency: ${name}`);
  return fs.realpathSync(process.env[name]);
};
const python = required('PYTHON_BIN');
const uv = required('UV_BIN');
const vale = required('VALE_BIN');
const slopsentral = required('ENGINEERING_SLOPSENTRAL_ROOT');
const codex = required('CODEX_BIN');
const piRoot = required('PI_SDK_ROOT');
const typescriptRoot = required('TYPESCRIPT_ROOT');
const uvCache = required('ENGINEERING_UV_CACHE');

function fixture(t, { adopt = true } = {}) {
  const directory = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'engineering native ')));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  const home = path.join(directory, 'home');
  const cwd = path.join(directory, 'project');
  fs.mkdirSync(cwd); fs.mkdirSync(home);
  fs.mkdirSync(path.join(home, '.codex'));
  for (const name of ['.config/agent-engineering', '.pi/agent']) {
    fs.cpSync(path.join(root, name), path.join(home, name), { recursive: true });
  }
  fs.writeFileSync(path.join(home, '.codex/AGENTS.md'), '# Existing custom instructions\n\nKeep this native global text.\n');
  fs.writeFileSync(path.join(home, '.pi/agent/APPEND_SYSTEM.md'), 'Keep existing Pi append instructions.\n');
  const bin = path.join(home, '.local/bin'); fs.mkdirSync(bin, { recursive: true });
  fs.copyFileSync(path.join(root, '.local/bin/agent-check'), path.join(bin, 'agent-check'));
  fs.chmodSync(path.join(bin, 'agent-check'), 0o755);
  fs.symlinkSync(uv, path.join(bin, 'uv'));
  fs.symlinkSync(process.execPath, path.join(bin, 'node'));
  const env = { HOME: home, CODEX_HOME: path.join(home, '.codex'),
    PI_CODING_AGENT_DIR: path.join(home, '.pi/agent'), XDG_STATE_HOME: path.join(home, '.local/state'),
    XDG_CONFIG_HOME: path.join(home, '.config'), XDG_CACHE_HOME: path.join(home, '.cache'),
    XDG_DATA_HOME: path.join(home, '.local/share'), UV_CACHE_DIR: uvCache,
    UV_PYTHON: python, UV_PYTHON_DOWNLOADS: 'never', UV_OFFLINE: '1',
    PATH: `${bin}:/usr/bin:/bin`, GIT_CONFIG_NOSYSTEM: '1', GIT_CONFIG_GLOBAL: '/dev/null', TERM: 'dumb' };
  const git = (...args) => execFileSync('/usr/bin/git', args, { cwd, env, encoding: 'utf8' });
  git('init', '-q'); git('config', 'user.name', 'Fixture'); git('config', 'user.email', 'fixture@example.invalid');
  fs.writeFileSync(path.join(cwd, 'README.md'), 'Read the file.\n');
  fs.writeFileSync(path.join(cwd, 'GLOSSARY.md'), '# Glossary\n\n- §FIXTURE§: A disposable test input.\n  - Known synonyms: none\n');
  git('add', '.'); git('commit', '-qm', 'initial');
  const check = (...args) => {
    try { return JSON.parse(execFileSync(path.join(bin, 'agent-check'), args, { cwd, env, encoding: 'utf8' })); }
    catch (error) { if (args[0] === 'status' && error.status === 1) return JSON.parse(error.stdout); throw error; }
  };
  const selection = ['--kotlin', path.join(slopsentral, 'source/hooks/kotlin-horizontalization-check'),
    '--assessment', path.join(slopsentral, 'source/skills/controlled-technical-writing/scripts/assess_text.py'), '--vale', vale];
  const install = () => { const plan = check('install', ...selection);
    return check('install', ...selection, '--apply', '--expected-plan', plan.planId); };
  if (adopt) install();
  return { directory, home, cwd, env, git, check, install };
}

test('the Pi adapter passes strict native TypeScript declarations', t => {
  const f = fixture(t);
  const config = path.join(f.directory, 'tsconfig.json');
  fs.writeFileSync(config, JSON.stringify({ compilerOptions: { target: 'ES2023', module: 'ESNext',
    moduleResolution: 'Bundler', strict: true, noUncheckedIndexedAccess: true, exactOptionalPropertyTypes: true,
    noEmit: true, allowImportingTsExtensions: true, skipLibCheck: true, types: ['node'],
    typeRoots: [path.resolve(typescriptRoot, '../@types')],
    paths: { '@earendil-works/pi-coding-agent': [path.join(piRoot, 'dist/index.d.ts')] } },
    files: [path.join(root, '.config/agent-engineering/pi-extension.ts')] }));
  execFileSync(process.execPath, [path.join(typescriptRoot, 'bin/tsc'), '--project', config], { env: f.env, encoding: 'utf8' });
});

test('real validators reject bad prose, expose layout advisories, and cache unchanged inputs', t => {
  const f = fixture(t);
  assert.equal(fs.readFileSync(path.join(root, 'tests/fixtures/text-assessment-v1.schema.json'), 'utf8'),
    fs.readFileSync(path.join(slopsentral, 'source/skills/controlled-technical-writing/references/text-assessment.schema.json'), 'utf8'),
    'unit schema fixture must match the qualified owner exactly');
  fs.writeFileSync(path.join(f.cwd, '.gitignore'), 'Ignored*.kt\n');
  f.check('begin', '--session', 'real-validator');
  const packageDir = path.join(f.cwd, 'src/main/kotlin/orders'); fs.mkdirSync(packageDir, { recursive: true });
  for (let i = 0; i < 8; i++) fs.writeFileSync(path.join(packageDir, `OrderCase${i}.kt`), `class OrderCase${i}\n`);
  fs.writeFileSync(path.join(f.cwd, 'README.md'), 'You should leverage this revolutionary tool.\n');
  assert.throws(() => f.check('turn', '--session', 'real-validator'));
  const failed = f.check('status', '--session', 'real-validator');
  assert.equal(failed.status, 'failed');
  assert.equal(failed.checks.kotlin.status, 'advisory');
  assert.ok(failed.checks.kotlin.report.findings.some(x => x.evidence.directKotlinFiles === 8));
  assert.equal(failed.checks.prose.report.type, 'ASSESSED');
  assert.equal(failed.checks.prose.report.schemaVersion, 1);
  assert.ok(failed.checks.prose.report.documents[0].findings.some(x => x.rule === 'Slopsentral.Diction'));
  fs.writeFileSync(path.join(f.cwd, 'README.md'), 'Read the new file.\n');
  const passed = f.check('turn', '--session', 'real-validator');
  assert.equal(passed.status, 'advisory');
  assert.equal(passed.checks.kotlin.cached, true);
  assert.equal(f.check('handoff', '--session', 'real-validator').checks.prose.cached, true);
  fs.writeFileSync(path.join(packageDir, 'IgnoredPeer.kt'), 'class IgnoredPeer\n');
  const peerChange = f.check('handoff', '--session', 'real-validator');
  assert.equal(peerChange.checks.kotlin.cached, false);
  assert.ok(peerChange.checks.kotlin.report.findings.some(x => x.evidence.directKotlinFiles === 9));
  f.git('add', '.'); f.git('commit', '-qm', 'during session');
  assert.equal(f.check('handoff', '--session', 'real-validator').checks.kotlin.cached, true);
  // An ignored ignore file cannot hide a failed, previously observed prose input.
  fs.appendFileSync(path.join(f.cwd, '.gitignore'), 'sub/.gitignore\n');
  fs.mkdirSync(path.join(f.cwd, 'sub'));
  f.check('begin', '--session', 'ignored-ignore');
  fs.writeFileSync(path.join(f.cwd, 'sub/new.md'), 'You should leverage this revolutionary tool.\n');
  assert.throws(() => f.check('handoff', '--session', 'ignored-ignore'));
  assert.equal(f.check('status', '--session', 'ignored-ignore').checks.prose.report.type, 'ASSESSED');
  fs.writeFileSync(path.join(f.cwd, 'sub/.gitignore'), 'new.md\n');
  assert.throws(() => f.check('handoff', '--session', 'ignored-ignore'));
  const contracted = f.check('status', '--session', 'ignored-ignore');
  assert.equal(contracted.status, 'failed');
  assert.match(contracted.failure, /ignore-scope-changed/);
  const glossaryFile = path.join(f.cwd, 'GLOSSARY.md');
  const glossaryBytes = fs.readFileSync(glossaryFile);
  fs.unlinkSync(glossaryFile);
  f.check('begin', '--session', 'missing-glossary');
  fs.writeFileSync(path.join(f.cwd, 'README.md'), 'Read another file.\n');
  assert.throws(() => f.check('handoff', '--session', 'missing-glossary'));
  const incomplete = f.check('status', '--session', 'missing-glossary');
  assert.equal(incomplete.status, 'failed');
  assert.equal(incomplete.checks.prose.report.type, 'INCOMPLETE');
  assert.equal(incomplete.checks.prose.report.glossary.type, 'NOT_PROVIDED');
  fs.writeFileSync(glossaryFile, glossaryBytes);
  f.check('begin', '--session', 'restored-glossary');
  fs.writeFileSync(path.join(f.cwd, 'README.md'), 'Read the updated file.\n');
  const complete = f.check('handoff', '--session', 'restored-glossary');
  assert.equal(complete.status, 'passed');
  assert.equal(complete.checks.prose.report.type, 'ASSESSED');
  t.diagnostic(`Real Vale 3.24.0 and Slopsentral ${f.git('-C', slopsentral, 'rev-parse', 'HEAD').trim()}; bad-prose control failed, layout remained advisory.`);
});

test('Pi 1.3.0 discovers B0 once and awaits native turn and settlement checks', async t => {
  const f = fixture(t);
  assert.equal(JSON.parse(fs.readFileSync(path.join(piRoot, 'package.json'))).version, '1.3.0');
  const previous = { ...process.env };
  for (const key of Object.keys(process.env)) delete process.env[key];
  Object.assign(process.env, f.env);
  t.after(() => { for (const key of Object.keys(process.env)) delete process.env[key]; Object.assign(process.env, previous); });
  const sdk = await import(pathToFileURL(path.join(piRoot, 'dist/index.js')));
  const aiRoot = createRequire(path.join(piRoot, 'package.json')).resolve.paths('@earendil-works/pi-ai')
    .map(directory => path.join(directory, '@earendil-works/pi-ai')).find(directory => fs.existsSync(path.join(directory, 'package.json')));
  assert.ok(aiRoot, 'Pi must supply its declared pi-ai dependency');
  const ai = await import(pathToFileURL(path.join(aiRoot, 'dist/index.js')));
  const agentDir = f.env.PI_CODING_AGENT_DIR;
  const settingsManager = sdk.SettingsManager.inMemory({ builtInExtensions: [], cacheWarming: { mode: 'off' } });
  const loader = new sdk.DefaultResourceLoader({ cwd: f.cwd, agentDir, settingsManager });
  await loader.reload();
  assert.deepEqual(loader.getExtensions().errors, []);
  assert.equal(loader.getAgentsFiles().agentsFiles.filter(x => x.content.includes('# Engineering baseline B0')).length, 1);
  assert.deepEqual(loader.getSkills().skills, []);
  const runtime = await sdk.ModelRuntime.create({ authPath: path.join(agentDir, 'auth.json'), modelsPath: null,
    modelsStorePath: path.join(agentDir, 'models.json'), allowModelNetwork: false, refreshOnCreate: false });
  const requests = [];
  runtime.registerProvider('fixture', { api: 'openai-completions', apiKey: 'fixture-no-network',
    baseUrl: 'http://127.0.0.1:9', models: [{ id: 'canned', name: 'Canned', reasoning: false, input: ['text'],
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: 100000, maxTokens: 1000 }],
    streamSimple(model, context) {
      requests.push(context);
      fs.writeFileSync(path.join(f.cwd, 'README.md'), 'You should leverage this revolutionary tool.\n');
      const stream = ai.createAssistantMessageEventStream();
      const message = { role: 'assistant', content: [{ type: 'text', text: 'Canned fixture.' }], api: model.api,
        provider: model.provider, model: model.id, usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } }, stopReason: 'stop', timestamp: Date.now() };
      stream.push({ type: 'done', reason: 'stop', message }); stream.end(message); return stream;
    } });
  const { session } = await sdk.createAgentSession({ cwd: f.cwd, agentDir, resourceLoader: loader, settingsManager,
    modelRuntime: runtime, model: runtime.getModel('fixture', 'canned'), sessionManager: sdk.SessionManager.inMemory(f.cwd) });
  t.after(() => session.dispose());
  await session.bindExtensions({ mode: 'print', onError: error => assert.fail(error.message) });
  assert.equal(session.systemPrompt.split('# Engineering baseline B0').length - 1, 1);
  assert.match(session.systemPrompt, /Keep existing Pi append instructions/);
  await session.prompt('Run one local canned response.');
  const entries = session.sessionManager.getEntries().filter(x => x.type === 'custom' && x.customType === 'engineering-check');
  assert.deepEqual(entries.map(x => x.data.phase), ['begin', 'turn', 'handoff']);
  assert.equal(entries[1].data.status, 'failed');
  assert.equal(entries[2].data.status, 'failed');
  assert.equal(entries[2].data.checks.prose.cached, true);
  assert.equal(requests.length, 1, 'validator failure must not trigger another model request');
  assert.equal(session.extensionRunner.getRegisteredCommands().length, 0);
  const outside = path.join(f.directory, 'nonrepo'); fs.mkdirSync(outside);
  const outsideLoader = new sdk.DefaultResourceLoader({ cwd: outside, agentDir, settingsManager });
  await outsideLoader.reload();
  const projectless = (await sdk.createAgentSession({ cwd: outside, agentDir, resourceLoader: outsideLoader, settingsManager,
    modelRuntime: runtime, model: runtime.getModel('fixture', 'canned'), sessionManager: sdk.SessionManager.inMemory(outside) })).session;
  t.after(() => projectless.dispose());
  await projectless.bindExtensions({ mode: 'print', onError: error => assert.fail(error.message) });
  await projectless.prompt('One projectless canned response.');
  const outsideEntries = projectless.sessionManager.getEntries().filter(x => x.type === 'custom' && x.customType === 'engineering-check');
  assert.deepEqual(outsideEntries.map(x => x.data.phase), ['begin', 'turn', 'handoff']);
  assert.ok(outsideEntries.every(x => x.data.status === 'not-applicable' && x.data.reason === 'outside-repository' && fs.existsSync(x.data.receipt)));
  assert.equal(requests.length, 2, 'projectless Pi use must remain available without a repair loop');
  fs.mkdirSync(path.join(f.cwd, '.pi'));
  fs.writeFileSync(path.join(f.cwd, '.pi/APPEND_SYSTEM.md'), 'Project append.\n');
  await loader.reload();
  assert.equal(loader.getAgentsFiles().agentsFiles.filter(x => x.content.includes('# Engineering baseline B0')).length, 1);
  fs.writeFileSync(path.join(agentDir, 'AGENTS.override.md'), 'Explicit native override.\n');
  await loader.reload();
  assert.equal(loader.getAgentsFiles().agentsFiles.filter(x => x.content.includes('# Engineering baseline B0')).length, 0);
  t.diagnostic('Actual Pi lifecycle with two in-process canned responses: failed repository checks and projectless not-applicable receipts; no hidden context entries or continuation.');
});

async function nativeRpc(f, t) {
  const child = spawn(codex, ['app-server'], { cwd: f.cwd, env: f.env, stdio: ['pipe', 'pipe', 'pipe'] });
  t.after(() => child.kill());
  child.stderr.resume();
  const notifications = [];
  const listeners = new Set();
  const pending = new Map(); let nextId = 0;
  const lines = readline.createInterface({ input: child.stdout });
  lines.on('line', line => { const value = JSON.parse(line); if (value.id !== undefined && pending.has(value.id)) {
    pending.get(value.id)(value); pending.delete(value.id);
  } else { notifications.push(value); for (const listener of listeners) listener(value); } });
  const request = (method, params) => new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => reject(new Error(`RPC timeout: ${method}`)), 15000);
    pending.set(id, value => { clearTimeout(timer); if (value.error) reject(new Error(JSON.stringify(value.error))); else resolve(value.result); });
    child.stdin.write(JSON.stringify({ id, method, params }) + '\n');
  });
  await request('initialize', { clientInfo: { name: 'engineering-native-fixture', version: '1' }, capabilities: { experimentalApi: true } });
  child.stdin.write('{"method":"initialized"}\n');
  const wait = method => new Promise((resolve, reject) => {
    const listener = value => { if (value.method === method) { clearTimeout(timer); listeners.delete(listener); resolve(value); } };
    const timer = setTimeout(() => { listeners.delete(listener); reject(new Error(`notification timeout: ${method}`)); }, 15000);
    listeners.add(listener);
  });
  return { request, notifications, wait, close() { child.kill(); lines.close(); } };
}

async function nativeHookTrust(f, t) {
  const rpc = await nativeRpc(f, t);
  const inventory = await rpc.request('hooks/list', { cwds: [f.cwd] });
  const hooks = inventory.data.flatMap(x => x.hooks).filter(x => x.source === 'user');
  assert.equal(hooks.length, 2, JSON.stringify(inventory));
  assert.ok(hooks.every(x => x.trustStatus === 'untrusted'));
  fs.appendFileSync(path.join(f.env.CODEX_HOME, 'config.toml'), hooks.map(x =>
    `\n[hooks.state.${JSON.stringify(x.key)}]\ntrusted_hash = ${JSON.stringify(x.currentHash)}\n`).join(''));
  rpc.close();
  return hooks;
}

test('native migration keeps existing hook hashes and trust while new checks remain untrusted', async t => {
  const f = fixture(t, { adopt: false });
  const hooksFile = path.join(f.env.CODEX_HOME, 'hooks.json');
  fs.writeFileSync(hooksFile, JSON.stringify({ hooks: { Stop: [{ hooks: [{ type: 'command', command: 'printf existing', timeout: 5 }] }] } }));
  let rpc = await nativeRpc(f, t);
  const before = (await rpc.request('hooks/list', { cwds: [f.cwd] })).data.flatMap(x => x.hooks).filter(x => x.source === 'user');
  assert.equal(before.length, 1);
  const existing = before[0];
  rpc.close();
  const config = `\n[hooks.state.${JSON.stringify(existing.key)}]\ntrusted_hash = ${JSON.stringify(existing.currentHash)}\n`;
  fs.writeFileSync(path.join(f.env.CODEX_HOME, 'config.toml'), config);
  f.install();
  assert.equal(fs.readFileSync(path.join(f.env.CODEX_HOME, 'config.toml'), 'utf8'), config);
  rpc = await nativeRpc(f, t);
  const after = (await rpc.request('hooks/list', { cwds: [f.cwd] })).data.flatMap(x => x.hooks).filter(x => x.source === 'user');
  assert.equal(after.length, 3);
  const retained = after.find(x => x.key === existing.key);
  assert.ok(retained);
  assert.equal(retained.currentHash, existing.currentHash);
  assert.equal(retained.trustStatus, 'trusted');
  assert.ok(after.filter(x => x.key !== existing.key).every(x => x.trustStatus === 'untrusted'));
  rpc.close();
  t.diagnostic('Actual Codex discovery: prior hook identity/hash/trust preserved; both new B0 definitions remain untrusted. Installer never edits config.toml.');
});

test('Codex 0.163.0 loads B0 once and hard-stops a failed native Stop check', async t => {
  const f = fixture(t);
  assert.match(execFileSync(codex, ['--version'], { env: f.env, encoding: 'utf8' }), /0\.163\.0/);
  let count = 0; const requests = [];
  const server = http.createServer((request, response) => {
    if (request.method !== 'POST') { response.writeHead(426); response.end(); return; }
    let body = ''; request.on('data', data => { body += data; }); request.on('end', () => {
      requests.push(JSON.parse(body)); count++;
      fs.writeFileSync(path.join(f.cwd, 'README.md'), `You should leverage this revolutionary tool ${count}.\n`);
      const events = [ { type: 'response.created', response: { id: 'fixture' } },
        { type: 'response.output_item.done', item: { type: 'message', role: 'assistant', id: 'message',
          content: [{ type: 'output_text', text: 'Canned fixture.' }] } },
        { type: 'response.completed', response: { id: 'fixture', usage: { input_tokens: 0, output_tokens: 0, total_tokens: 0 } } } ];
      response.writeHead(200, { 'content-type': 'text/event-stream' });
      response.end(events.map(event => `event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`).join(''));
    });
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  fs.writeFileSync(path.join(f.env.CODEX_HOME, 'config.toml'), `model = "canned"\nmodel_provider = "fixture"\ncheck_for_update_on_startup = false\n[model_providers.fixture]\nname = "Local fixture"\nbase_url = "http://127.0.0.1:${server.address().port}/v1"\nwire_api = "responses"\nrequires_openai_auth = false\n`);
  await nativeHookTrust(f, t);
  const execution = execute(codex, ['--no-daemon', '-C', f.cwd, 'exec', '--json', 'One local fixture response.'],
    { cwd: f.cwd, env: f.env, timeout: 45000, maxBuffer: 2 * 1024 * 1024 });
  execution.child.stdin.end();
  const result = await execution;
  assert.equal(count, 1, 'hard stop must not trigger a model continuation');
  assert.equal(JSON.stringify(requests[0]).split('# Engineering baseline B0').length - 1, 1);
  assert.match(JSON.stringify(requests[0]), /Keep this native global text/);
  const sessions = path.join(f.env.XDG_STATE_HOME, 'agent-engineering/sessions');
  const latest = fs.readdirSync(sessions).map(x => path.join(sessions, x, 'latest.json')).filter(fs.existsSync);
  assert.equal(latest.length, 1, result.stdout + result.stderr);
  const report = JSON.parse(fs.readFileSync(latest[0]));
  assert.equal(report.status, 'failed');
  assert.match(result.stdout, /turn.completed/);
  const rpc = await nativeRpc(f, t);
  const inventory = await rpc.request('hooks/list', { cwds: [f.cwd] });
  assert.ok(inventory.data.flatMap(x => x.hooks).every(x => x.trustStatus === 'trusted'));
  const started = await rpc.request('thread/start', { cwd: f.cwd, model: 'canned', modelProvider: 'fixture', approvalPolicy: 'never' });
  const completed = rpc.wait('turn/completed');
  await rpc.request('turn/start', { threadId: started.thread.id, input: [{ type: 'text', text: 'One local fixed response.', textElements: [] }] });
  await completed;
  const stop = rpc.notifications.filter(x => x.method === 'hook/completed').map(x => x.params).find(x => x.run.eventName === 'stop');
  assert.ok(stop, JSON.stringify(rpc.notifications));
  assert.equal(stop.run.status, 'stopped', JSON.stringify(stop));
  assert.ok(stop.run.entries.some(x => /agent-check: failed/.test(x.text)), JSON.stringify(stop));
  assert.equal(count, 2, 'neither failed native Stop check can request another model response');
  rpc.close();
  fs.writeFileSync(path.join(f.env.CODEX_HOME, 'AGENTS.override.md'), 'Explicit native override.\n');
  const prompt = execFileSync(codex, ['-C', f.cwd, 'debug', 'prompt-input', 'Inspect only.'], { env: f.env, encoding: 'utf8', input: '', timeout: 15000 });
  assert.equal(prompt.split('# Engineering baseline B0').length - 1, 0);
  assert.match(prompt, /Explicit native override/);
  t.diagnostic('Actual Codex CLI and App Server: fixture-only native trust; failed check yields hook status stopped, while CLI still exits zero with turn.completed. Receipt/explicit handoff is the check gate. Two loopback canned responses, no paid inference or trust bypass.');
});

test('Codex 0.163.0 permits projectless use with native not-applicable receipts', async t => {
  const f = fixture(t);
  const outside = path.join(f.directory, 'nonrepo'); fs.mkdirSync(outside);
  let count = 0;
  const server = http.createServer((request, response) => {
    if (request.method !== 'POST') { response.writeHead(426); response.end(); return; }
    request.resume(); request.on('end', () => {
      count++;
      const events = [{ type: 'response.created', response: { id: 'projectless' } },
        { type: 'response.output_item.done', item: { type: 'message', role: 'assistant', id: 'message',
          content: [{ type: 'output_text', text: 'Projectless canned response.' }] } },
        { type: 'response.completed', response: { id: 'projectless', usage: { input_tokens: 0, output_tokens: 0, total_tokens: 0 } } }];
      response.writeHead(200, { 'content-type': 'text/event-stream' });
      response.end(events.map(event => `event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`).join(''));
    });
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  fs.writeFileSync(path.join(f.env.CODEX_HOME, 'config.toml'), `model = "canned"\nmodel_provider = "fixture"\ncheck_for_update_on_startup = false\n[model_providers.fixture]\nname = "Local fixture"\nbase_url = "http://127.0.0.1:${server.address().port}/v1"\nwire_api = "responses"\nrequires_openai_auth = false\n`);
  await nativeHookTrust(f, t);
  const rpc = await nativeRpc(f, t);
  const started = await rpc.request('thread/start', { cwd: outside, model: 'canned', modelProvider: 'fixture', approvalPolicy: 'never' });
  const completed = rpc.wait('turn/completed');
  await rpc.request('turn/start', { threadId: started.thread.id, input: [{ type: 'text', text: 'One projectless canned response.', textElements: [] }] });
  const turn = await completed;
  assert.equal(turn.params.turn.status, 'completed');
  assert.equal(count, 1, 'native SessionStart must allow one normal projectless response');
  const hooks = rpc.notifications.filter(x => x.method === 'hook/completed').map(x => x.params.run);
  for (const event of ['sessionStart', 'stop']) {
    const hook = hooks.find(x => x.eventName === event);
    assert.ok(hook, JSON.stringify(hooks));
    assert.equal(hook.status, 'completed', JSON.stringify(hook));
    assert.ok(hook.entries.some(x => /agent-check: not-applicable; outside-repository; receipt=/.test(x.text)), JSON.stringify(hook));
  }
  rpc.close();
  const sessions = path.join(f.env.XDG_STATE_HOME, 'agent-engineering/sessions');
  const receipts = fs.readdirSync(sessions).map(x => JSON.parse(fs.readFileSync(path.join(sessions, x, 'latest.json'))));
  assert.equal(receipts.length, 1);
  assert.equal(receipts[0].status, 'not-applicable');
  assert.equal(receipts[0].reason, 'outside-repository');
  assert.ok(!fs.existsSync(path.join(path.dirname(receipts[0].receipt), 'session.json')), 'projectless use cannot fabricate a repository baseline');
  assert.throws(() => execFileSync(path.join(f.home, '.local/bin/agent-check'), ['handoff', '--repo', outside, '--session', started.thread.id], { cwd: outside, env: f.env, encoding: 'utf8' }), error => error.status === 1 && JSON.parse(error.stdout).failure === 'outside-repository');
  t.diagnostic('Actual trusted native SessionStart and Stop completed with not-applicable receipts; one loopback canned response and no repository proof. Explicit handoff still failed outside Git.');
});
