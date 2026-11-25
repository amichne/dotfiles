import {spawnSync} from 'node:child_process';
import {randomUUID} from 'node:crypto';
import {mkdir, readFile, rename, rm, writeFile} from 'node:fs/promises';
import {homedir} from 'node:os';
import {dirname, join} from 'node:path';

export const segments = Object.freeze([
  'branch', 'remote', 'sync', 'changes', 'worktree', 'pr', 'working', 'details',
]);
const path = join(process.env.XDG_CONFIG_HOME || join(homedir(), '.config'), 'shell-prompt', 'statusline.json');
const usage = [
  'shell-prompt customize                         Print the active layout',
  'shell-prompt customize --ask "REQUEST"         Propose a layout with ai-ask',
  'shell-prompt customize --apply \'["branch"]\'    Save a layout for the next prompt',
  'Segments in default order: ' + segments.join(', '),
].join('\n');

function parseLayout(text) {
  let layout;
  try { layout = JSON.parse(text); } catch { throw new Error('Expected a JSON array of status-line segments.'); }
  if (!Array.isArray(layout) || !layout.every(name => segments.includes(name)) ||
      new Set(layout).size !== layout.length) {
    throw new Error('Use each segment at most once. Available segments: ' + segments.join(', '));
  }
  return layout;
}

export async function activeLayout() {
  try { return parseLayout(await readFile(path, 'utf8')); }
  catch (error) {
    if (error.code === 'ENOENT') return segments;
    throw error;
  }
}

async function saveLayout(layout) {
  await mkdir(dirname(path), {recursive: true, mode: 0o700});
  const temporary = path + '.' + randomUUID();
  try {
    await writeFile(temporary, JSON.stringify(layout) + '\n', {flag: 'wx', mode: 0o600});
    await rename(temporary, path);
  } finally {
    await rm(temporary, {force: true});
  }
}

export async function customize(args) {
  if (!args.length) return console.log(JSON.stringify(await activeLayout()));
  if (args.length === 1 && args[0] === '--help') return console.log(usage);
  const [option, value] = args;
  if (args.length !== 2 || !value.trim() || !['--ask', '--apply'].includes(option)) {
    throw new Error(usage);
  }
  if (option === '--apply') {
    await saveLayout(parseLayout(value));
    return;
  }
  const request = [
    'Customize the Git status line. Return only a JSON array of segment names in display order.',
    'Omit hidden segments. Use each name at most once. Available: ' + segments.join(', ') + '.',
    'working shows changed line counts. details shows the default-branch comparison and CI status.',
    'Current layout: ' + JSON.stringify(await activeLayout()),
    'Requested change: ' + value,
  ].join('\n');
  const answer = spawnSync('ai-ask', [], {
    input: request, encoding: 'utf8', timeout: 130_000, maxBuffer: 64 * 1024,
  });
  if (answer.error?.code === 'ENOENT') throw new Error('Add the dotfiles .local/bin directory to PATH to use ai-ask.');
  if (answer.error || answer.status !== 0) throw new Error('ai-ask failed. Check the selected provider and its authentication.');
  console.log(JSON.stringify(parseLayout(answer.stdout)));
}
