import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

const root = path.resolve(import.meta.dirname, '..');
const required = name => {
  assert.ok(process.env[name], `missing explicit dependency: ${name}`);
  return fs.realpathSync(process.env[name]);
};
const piRoot = required('PI_SDK_ROOT');
const typescriptRoot = required('TYPESCRIPT_ROOT');

test('the Pi extensions pass strict native TypeScript declarations', t => {
  const directory = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'dotfiles Pi types ')));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  const home = path.join(directory, 'home');
  fs.mkdirSync(home);
  const piRequire = createRequire(path.join(piRoot, 'package.json'));
  const dependency = name => {
    const selected = piRequire.resolve.paths(name).map(base => path.join(base, name))
      .find(candidate => fs.existsSync(path.join(candidate, 'package.json')));
    assert.ok(selected, `Pi must supply its declared ${name} dependency`);
    return selected;
  };
  const config = path.join(directory, 'tsconfig.json');
  fs.writeFileSync(config, JSON.stringify({ compilerOptions: { target: 'ES2023', module: 'ESNext',
    moduleResolution: 'Bundler', strict: true, noUncheckedIndexedAccess: true, exactOptionalPropertyTypes: true,
    noEmit: true, allowImportingTsExtensions: true, skipLibCheck: true, types: ['node'],
    typeRoots: [path.resolve(typescriptRoot, '../@types')],
    paths: { '@earendil-works/pi-coding-agent': [path.join(piRoot, 'dist/index.d.ts')],
      '@earendil-works/pi-ai': [path.join(dependency('@earendil-works/pi-ai'), 'dist/index.d.ts')],
      'typebox': [dependency('typebox')] } },
    files: ['.pi/agent/extensions/deepen.ts', '.pi/agent/extensions/ask-questions.ts',
      '.pi/agent/lib/questions.ts'].map(name => path.join(root, name)) }));
  const env = { PATH: process.env.PATH, HOME: home,
    XDG_CONFIG_HOME: path.join(home, '.config'), XDG_DATA_HOME: path.join(home, '.local/share'),
    XDG_STATE_HOME: path.join(home, '.local/state'), XDG_CACHE_HOME: path.join(home, '.cache') };
  execFileSync(process.execPath, [path.join(typescriptRoot, 'bin/tsc'), '--project', config], { env, encoding: 'utf8' });
});
