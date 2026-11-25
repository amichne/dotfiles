import test, {after} from 'node:test';
import assert from 'node:assert/strict';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {mkdtemp, writeFile, readFile, realpath, rm, mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {performance} from 'node:perf_hooks';
import {stripVTControlCharacters} from 'node:util';
import {fileURLToPath} from 'node:url';
import {
  defaults,
  gitANSI,
  gitParts,
  gitText,
  parseStatus,
  parseUntracked,
  validateSettings,
} from '../.config/shell-prompt/model.mjs';

const repository = {
  kind: 'repository',
  branch: {kind: 'named', name: 'feature/prompt-editor', oid: 'a'.repeat(40)},
  tracking: {kind: 'tracked', name: 'origin/feature/prompt-editor', ahead: 2, behind: 1},
  counts: {staged: 1, modified: 3, conflicted: 0, stashed: 1},
  untracked: {kind: 'known', count: 0},
  worktree: {kind: 'linked', name: 'feature-worktree', total: 3, locked: false, prunable: false},
  pr: {kind: 'open', number: 42, draft: false, base: 'main', stale: false},
};

const exec = promisify(execFile);
const isolatedHome = await mkdtemp(join(tmpdir(), 'prompt-home-'));
after(() => rm(isolatedHome, {recursive: true, force: true}));
const runtimeEnv = {
  PATH: process.env.PATH || '/usr/bin:/bin', HOME: isolatedHome,
  XDG_CONFIG_HOME: join(isolatedHome, '.config'),
  XDG_CACHE_HOME: join(isolatedHome, '.cache'),
  XDG_DATA_HOME: join(isolatedHome, '.local/share'),
  XDG_STATE_HOME: join(isolatedHome, '.local/state'),
  GIT_CONFIG_NOSYSTEM: '1', GIT_CONFIG_GLOBAL: '/dev/null',
};
process.env = {...runtimeEnv};
const {readRepository} = await import('../.config/shell-prompt/context.mjs');
async function fixture(t) {
  const root = await mkdtemp(join(tmpdir(), 'prompt-git-'));
  t.after(() => rm(root, {recursive: true, force: true}));
  const repo = join(root, 'repo');
  await mkdir(repo);
  const git = (...args) => exec('/usr/bin/git', args, {cwd: repo, env: runtimeEnv});
  await git('init', '-b', 'fixture-main');
  await writeFile(join(repo, 'tracked'), 'initial\n');
  await git('add', 'tracked');
  await git('-c', 'user.name=Prompt Fixture', '-c', 'user.email=prompt@example.invalid', 'commit', '-m', 'fixture');
  // This readiness check is outside the prompt's measured execution budget.
  await git('rev-parse', '--show-toplevel');
  return {root, repo, git};
}
async function contextProcess(repo, env) {
  const code = `import {readRepository} from ${JSON.stringify(new URL('../.config/shell-prompt/context.mjs', import.meta.url).href)}; console.log(JSON.stringify(await readRepository(process.argv[1])));`;
  const result = await exec(process.execPath, ['--input-type=module', '-e', code, repo], {cwd: repo, env: {...runtimeEnv, ...env}, timeout: 4000});
  return JSON.parse(result.stdout);
}

const renderer = fileURLToPath(new URL('../.config/shell-prompt/context.mjs', import.meta.url));
async function statusline(repo, env) {
  const result = await exec(process.execPath, [renderer, 'statusline'], {
    cwd: repo, env: {...runtimeEnv, ...env}, timeout: 1200,
  });
  return stripVTControlCharacters(result.stdout.trimEnd());
}

test('a blocked Worktrunk cannot delay the local labels; a later redraw adds labeled facts', async t => {
  const {root, repo, git} = await fixture(t);
  const oid = (await git('rev-parse', 'HEAD')).stdout.trim();
  const row = {
    branch: 'fixture-main', head: {sha:oid},
    worktree: {path:await realpath(repo), changes:{diff:{added:270, deleted:1}}},
    default_branch: {ahead:1, behind:61, diff:{added:63, deleted:27}},
    checks: {status:'failed', source:'branch', stale:false},
    pr: {number:42},
  };
  const env = {PATH:root + ':/usr/bin:/bin', XDG_CACHE_HOME:join(root, 'cache')};
  await writeFile(join(root, 'report'), JSON.stringify({schema:2, repo:{default_branch:'main'}, items:[row]}));
  await writeFile(join(root, 'wt'), [
    '#!/bin/sh',
    '[ "$*" = "--config-set list.json-schema=2 list statusline --format=json" ] || exit 64',
    'while [ ! -f "$PWD/../release" ]; do sleep 0.05; done',
    'cat "$PWD/../report"',
  ].join('\n'), {mode:0o755});
  await writeFile(join(repo, 'tracked'), 'changed\n');
  const first = await statusline(repo, env);
  assert.equal(first, 'fixture-main · no upstream · !1');
  await writeFile(join(root, 'release'), '');
  const deadline = performance.now() + 3500;
  let warm;
  do {
    await new Promise(done => setTimeout(done, 40));
    warm = await statusline(repo, env);
  } while (!warm.includes('branch CI failed') && performance.now() < deadline);
  assert.equal(warm, first + ' · PR #42 · working lines +270 -1 · vs main: ↑1 ↓61, +63 -27 lines · branch CI failed');
  await git('restore', 'tracked');
  const clean = await statusline(repo, env);
  assert.match(clean, / · clean · /);
  assert.doesNotMatch(clean, /working lines/);
  await git('switch', '-c', 'same-commit-other-branch');
  assert.doesNotMatch(await statusline(repo, env), /working lines|vs main|CI failed/);
});

test('a slow Git status keeps branch identity and never claims the worktree is clean', async t => {
  const {root, repo} = await fixture(t);
  await writeFile(join(root, 'git'), '#!/bin/sh\nif [ "$1" = status ]; then exec sleep 10; fi\nexec /usr/bin/git "$@"\n', {mode:0o755});
  assert.equal(await statusline(repo, {PATH:root + ':/usr/bin:/bin'}), 'fixture-main · Git status unavailable');
});

test('customize proposes through ai-ask and applies only an explicit valid layout', async t => {
  const {root, repo} = await fixture(t);
  const env = {...runtimeEnv, XDG_CONFIG_HOME:join(root, 'config'), PATH:root + ':' + runtimeEnv.PATH};
  const launcher = fileURLToPath(new URL('../.local/bin/shell-prompt', import.meta.url));
  const customize = (...args) => exec(launcher, ['customize', ...args], {cwd:repo, env});
  const provider = join(root, 'ai-ask');
  await writeFile(provider, '#!/bin/sh\ncat > "$PWD/../request"\necho \'["changes","branch"]\'\n', {mode:0o755});
  const original = (await customize()).stdout;
  const proposed = (await customize('--ask', 'put changes first')).stdout.trim();
  assert.equal(proposed, '["changes","branch"]');
  assert.match(await readFile(join(root, 'request'), 'utf8'), /put changes first/);
  assert.equal((await customize()).stdout, original);
  await customize('--apply', proposed);
  await writeFile(provider, '#!/bin/sh\necho \'["$(whoami)"]\'\n');
  await assert.rejects(customize('--ask', 'invalid response'), /Available segments/);
  await assert.rejects(customize('--apply', '["branch","branch"]'), /at most once/);
  assert.equal((await customize()).stdout.trim(), proposed);
  assert.equal(await statusline(repo, env), 'clean · fixture-main');
});

test('Git context preserves remote, divergence, worktree, and pull request meaning', () => {
  assert.deepEqual(gitParts(defaults, repository).map(part => part.text), [
    'feature/prompt-editor',
    '→ origin//',
    '2 ahead / 1 behind',
    '1 staged 3 modified 1 stashed',
    'wt:feature-worktree / 3 total',
    'PR #42 → main',
  ]);
});

test('the prompt names a linked checkout once across visible and truncated paths', () => {
  const worktree = {...repository.worktree, name: 'feature-prompt-editor', locked: true};
  const labels = (g, path) => gitParts(defaults, g, path)
    .filter(part => part.type === 'branch' || part.type === 'worktree')
    .map(part => part.text);
  const linked = {...repository, worktree};
  assert.deepEqual(labels(linked, '…/repo/feature-prompt-editor/src'), ['3 worktrees / locked']);
  assert.deepEqual(labels(linked, '…/src/deep/lib'), ['feature/prompt-editor', '3 worktrees / locked']);
  assert.deepEqual(labels(linked, '…/feature-prompt-editor-v2'), ['feature/prompt-editor', '3 worktrees / locked']);
  assert.deepEqual(labels(repository, '…/feature-worktree'), ['feature/prompt-editor', '3 worktrees']);
  assert.deepEqual(labels(repository, '…/src/deep/lib'), ['feature/prompt-editor', 'wt:feature-worktree / 3 total']);
  const detached = {...linked, branch: {kind: 'detached', oid: 'a'.repeat(40)}};
  assert.deepEqual(labels(detached, '…/feature-prompt-editor'), ['detached aaaaaaa', '3 worktrees / locked']);
});

test('upstreams with another branch or remote keep their full name', () => {
  for (const name of ['origin/main', 'origin/other/feature/prompt-editor', 'fork/feature/prompt-editor']) {
    const g = {...repository, tracking: {...repository.tracking, name}};
    assert.equal(gitParts(defaults, g).find(part => part.type === 'remote').text, `→ ${name}`);
  }
});

test('terminal Git output carries the same semantic fields with bounded color escapes', () => {
  const output = gitANSI(defaults, repository);
  assert.match(output, /\u001b\[38;2;189;147;249;1mfeature\/prompt-editor\u001b\[0m/);
  assert.match(output, /PR #42 → main/);
  assert.equal(output.replaceAll(/\u001b\[[\d;]+m/g, ''), gitParts(defaults, repository).map(part => part.text).join(' · '));
});

test('porcelain parsing fails closed on incomplete data', () => {
  assert.deepEqual(parseStatus('# branch.head main\0'), {kind: 'unavailable', reason: 'missing-head'});
  assert.deepEqual(parseStatus('# branch.head main'), {kind: 'unavailable', reason: 'incomplete-status'});
});

test('settings preserve Unicode and reject unknown fields', () => {
  const settings = structuredClone(defaults);
  settings.marker = '❯';
  const checked = validateSettings(settings);
  assert.equal(checked.kind, 'valid');
  const decoded = checked.value;
  assert.deepEqual(decoded, settings);
  assert.equal(validateSettings({...settings, surprise: true}).kind, 'invalid');
});

test('unknown untracked evidence never renders a false clean worktree', () => {
  const g = {...repository, counts: {staged: 0, modified: 0, conflicted: 0, stashed: 0}, untracked: {kind: 'unavailable', reason: 'git-timeout'}};
  assert.match(gitText(defaults, g), /untracked unknown/);
  assert.doesNotMatch(gitText(defaults, g), /\bclean\b/);
  assert.match(gitText({...defaults, labels: 'compact'}, g), /\?unknown/);
  assert.match(gitText(defaults, {...g, counts: {...g.counts, staged: 1}}), /1 staged untracked unknown/);
});

test('parsing retains whether untracked files were actually requested', () => {
  const raw = '# branch.head main\0# branch.oid ' + 'a'.repeat(40) + '\0';
  const excluded = parseStatus(raw, 'none');
  assert.deepEqual(excluded.untracked, {kind: 'unavailable', reason: 'not-requested'});
  assert.match(gitText(defaults, excluded), /untracked unknown/);
  assert.doesNotMatch(gitText(defaults, excluded), /\bclean\b/);
  assert.deepEqual(parseStatus(raw).untracked, {kind: 'known', count: 0});
  assert.match(gitText(defaults, parseStatus(raw)), /\bclean\b/);
  assert.deepEqual(parseStatus(raw + '? file\0', 'none'), {kind: 'unavailable', reason: 'unexpected-untracked-entry'});
  assert.deepEqual(parseUntracked('file'), {kind: 'unavailable', reason: 'incomplete-untracked'});
  assert.deepEqual(parseUntracked('file\0\0'), {kind: 'unavailable', reason: 'incomplete-untracked'});
  assert.deepEqual(parseUntracked('line\nfile\0'), {kind: 'known', count: 1});
});

test('real repository reports proven tracked and untracked counts', async t => {
  const {repo, git} = await fixture(t);
  await writeFile(join(repo, 'tracked'), 'changed\n');
  await writeFile(join(repo, 'new-staged'), 'staged\n');
  await git('add', 'new-staged');
  await writeFile(join(repo, 'new-untracked'), 'untracked\n');
  const g = await readRepository(repo);
  assert.equal(g.kind, 'repository');
  assert.equal(g.branch.name, 'fixture-main');
  assert.deepEqual(g.counts, {staged: 1, modified: 1, conflicted: 0, stashed: 0});
  assert.deepEqual(g.untracked, {kind: 'known', count: 1});
  assert.match(gitText(defaults, g), /1 staged 1 modified 1 untracked/);
  assert.equal(g.evidence.every(e => Number.isFinite(e.elapsedMs) && e.elapsedMs >= 0), true);
  assert.equal(g.evidence.some(e => e.stage === 'untracked' && e.outcome === 'COMPLETE'), true);
});

test('slow untracked scan preserves tracked facts and stops its helper processes', async t => {
  const {root, repo, git} = await fixture(t);
  await writeFile(join(repo, 'tracked'), 'changed\n');
  await writeFile(join(repo, 'new-staged'), 'staged\n');
  await git('add', 'new-staged');
  const wrapper = join(root, 'git');
  const pidFile = join(root, 'helper.pid');
  await writeFile(wrapper, '#!/bin/sh\ndelay=0\n[ "$1" = ls-files ] && delay=1\nfor arg do [ "$arg" = --untracked-files=all ] && delay=1; done\nif [ "$delay" = 1 ]; then\n  /bin/sleep 30 &\n  printf "%s" "$!" > "$PROMPT_HELPER_PID"\n  wait\nelse\n  exec /usr/bin/git "$@"\nfi\n', {mode: 0o755});
  const started = performance.now();
  const g = await contextProcess(repo, {PATH: `${root}:/usr/bin:/bin`, PROMPT_HELPER_PID: pidFile});
  const elapsed = performance.now() - started;
  const pid = Number(await readFile(pidFile, 'utf8'));
  t.after(() => {try {process.kill(pid, 'SIGKILL');} catch {}});
  assert.equal(g.kind, 'repository');
  assert.equal(g.branch.name, 'fixture-main');
  assert.deepEqual(g.counts, {staged: 1, modified: 1, conflicted: 0, stashed: 0});
  assert.deepEqual(g.untracked, {kind: 'unavailable', reason: 'git-timeout'});
  assert.match(gitText(defaults, g), /1 staged 1 modified untracked unknown/);
  assert.equal(g.evidence.some(e => e.stage === 'untracked' && e.outcome === 'TIMED_OUT'), true);
  assert.ok(elapsed < 1200, `prompt context exceeded Starship's existing 1200ms budget: ${elapsed}ms`);
  assert.throws(() => process.kill(pid, 0), {code: 'ESRCH'});
});

test('tracked timeout fails closed and reports finite bounded evidence', async t => {
  const {root, repo} = await fixture(t);
  const wrapper = join(root, 'git');
  const pidFile = join(root, 'helper.pid');
  await writeFile(wrapper, '#!/bin/sh\nif [ "$1" = status ]; then\n  /bin/sleep 30 &\n  printf "%s" "$!" > "$PROMPT_HELPER_PID"\n  wait\nelse\n  exec /usr/bin/git "$@"\nfi\n', {mode: 0o755});
  const g = await contextProcess(repo, {PATH: `${root}:/usr/bin:/bin`, PROMPT_HELPER_PID: pidFile});
  const pid = Number(await readFile(pidFile, 'utf8'));
  t.after(() => {try {process.kill(pid, 'SIGKILL');} catch {}});
  assert.equal(g.kind, 'unavailable');
  assert.equal(g.reason, 'git-timeout');
  assert.equal(g.evidence.some(e => e.stage === 'status' && e.outcome === 'TIMED_OUT'), true);
  assert.equal(g.evidence.every(e => Object.keys(e).sort().join(',') === 'elapsedMs,outcome,stage'), true);
  assert.throws(() => process.kill(pid, 0), {code: 'ESRCH'});
});
