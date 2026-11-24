import {createHash, randomUUID} from 'node:crypto';
import {spawn} from 'node:child_process';
import {mkdir, open, readFile, readdir, rename, unlink, writeFile} from 'node:fs/promises';
import {homedir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {display} from './model.mjs';

const interval = 30_000;
const runner = fileURLToPath(new URL('./context.mjs', import.meta.url));
const hash = value => createHash('sha256').update(value).digest('hex');
const count = value => Number.isSafeInteger(value) && value >= 0;

function location(root, branch, oid, slot) {
  const cache = process.env.XDG_CACHE_HOME || join(homedir(), '.cache');
  const dir = join(cache, 'shell-prompt', 'worktrunk', hash(root));
  return {dir, file: join(dir, `${slot}-${hash(JSON.stringify([branch, oid]))}.json`)};
}

async function readSnapshot(file) {
  try {
    const data = JSON.parse(await readFile(file, 'utf8'));
    if (!Array.isArray(data.labels) || !data.labels.every(s => typeof s === 'string')) return null;
    if (typeof data.working !== 'string') return null;
    if (data.prNumber !== null && !(count(data.prNumber) && data.prNumber > 0)) return null;
    return data;
  } catch {
    return null;
  }
}

// An exclusive reservation admits one worker per worktree, HEAD and time slot.
// A killed worker leaves an empty slot. The next slot can refresh independently.
export async function cachedWorktrunk(g) {
  const branch = g.branch.name ?? '';
  const oid = g.branch.oid;
  if (oid === '(initial)') return null;
  const slot = Math.floor(Date.now() / interval);
  const {dir, file} = location(g.root, branch, oid, slot);
  try {
    const snapshot = await readSnapshot(file);
    if (snapshot) return snapshot;
    await mkdir(dir, {recursive: true, mode: 0o700});
    try {
      await (await open(file, 'wx', 0o600)).close();
      const worker = spawn(process.execPath, [runner, 'refresh-worktrunk', branch, oid, String(slot)], {
        cwd: g.root, detached: true, stdio: 'ignore',
      });
      worker.on('error', () => {});
      worker.unref();
    } catch (error) {
      if (error.code !== 'EEXIST') return null;
    }
    return await readSnapshot(location(g.root, branch, oid, slot - 1).file);
  } catch {
    return null;
  }
}

function lineCounts(diff) {
  return count(diff?.added) && count(diff?.deleted) ? `+${diff.added} -${diff.deleted}` : '';
}

// Schema 2 omits default_branch on some primary worktree rows. Use local refs
// for that comparison, and name the exact ref we actually compared.
async function baseComparison(doc, item, root, read) {
  const name = doc.repo?.default_branch;
  if (typeof name !== 'string' || !name || item.branch === name) return '';
  let base = name;
  let relation = item.default_branch;
  if (!relation) {
    const remote = doc.repo?.forge?.remote;
    const refs = remote ? [`refs/remotes/${remote}/${name}`, `refs/heads/${name}`] : [`refs/heads/${name}`];
    for (const ref of refs) {
      const counts = await read('git', ['rev-list', '--left-right', '--count', `${item.head.sha}...${ref}`, '--'], root, 'base-count');
      const match = counts.stdout?.trim().match(/^(\d+)\s+(\d+)$/);
      if (!match) continue;
      base = ref.replace(/^refs\/(?:remotes|heads)\//, '');
      relation = {ahead: Number(match[1]), behind: Number(match[2])};
      const stat = await read('git', ['diff', '--no-ext-diff', '--no-textconv', '--shortstat', `${ref}...${item.head.sha}`, '--'], root, 'base-diff');
      if (stat.kind === 'complete') {
        relation.diff = {
          added: Number(stat.stdout.match(/(\d+) insertion/)?.[1] ?? 0),
          deleted: Number(stat.stdout.match(/(\d+) deletion/)?.[1] ?? 0),
        };
      }
      break;
    }
  }
  if (!relation) return '';
  const parts = [];
  if (count(relation.ahead) && count(relation.behind) && (relation.ahead || relation.behind)) {
    parts.push(`↑${relation.ahead} ↓${relation.behind}`);
  }
  const lines = lineCounts(relation.diff);
  if (lines && (relation.diff.added || relation.diff.deleted)) parts.push(`${lines} lines`);
  return parts.length ? `vs ${display(base)}: ${parts.join(', ')}` : '';
}

export async function refreshWorktrunk(branch, oid, slot, read) {
  const root = process.cwd();
  if (!Number.isSafeInteger(slot) || !/^[a-f0-9]{40,64}$/.test(oid)) return;
  const {dir, file} = location(root, branch, oid, slot);
  for (const entry of await readdir(dir)) {
    const stamp = /^(\d+)-/.exec(entry);
    if (stamp && Number(stamp[1]) < slot - 1) {
      await unlink(join(dir, entry)).catch(error => { if (error.code !== 'ENOENT') throw error; });
    }
  }
  const result = await read('wt', ['--config-set', 'list.json-schema=2', 'list', 'statusline', '--format=json'], root, 'worktrunk', {timeout: 4000});
  if (result.kind !== 'complete') return;
  const doc = JSON.parse(result.stdout);
  const item = doc.items?.[0];
  if (doc.schema !== 2 || doc.items.length !== 1 || item?.head?.sha !== oid ||
      (item.branch ?? '') !== branch || item.worktree?.path !== root) return;
  const labels = [];
  const workingDiff = item.worktree.changes?.diff;
  const working = workingDiff?.added || workingDiff?.deleted ? lineCounts(workingDiff) : '';
  const comparison = await baseComparison(doc, item, root, read);
  if (comparison) labels.push(comparison);
  const checks = item.checks;
  if (['passed', 'running', 'failed'].includes(checks?.status)) {
    const source = checks.source === 'pr' ? 'PR CI' : checks.source === 'branch' ? 'branch CI' : 'CI';
    labels.push(`${source} ${checks.status}${checks.stale ? ' (stale)' : ''}`);
  }
  const prNumber = item.pr?.number;
  const tmp = `${file}.${randomUUID()}.tmp`;
  await writeFile(tmp, JSON.stringify({working, labels, prNumber: count(prNumber) && prNumber > 0 ? prNumber : null}), {mode: 0o600});
  await rename(tmp, file);
}
