import { readFile } from 'node:fs/promises';
import { lookup } from 'node:dns/promises';
import { execFileSync } from 'node:child_process';

const packageJson = JSON.parse(await readFile(new URL('../package.json', import.meta.url), 'utf8'));
const required = { ...packageJson.dependencies, ...packageJson.devDependencies };
const missing = [];
const line = (label, value) => console.log(`${label.padEnd(27)} ${value}`);

console.log(`FLEXY AI frontend environment check (${packageJson.version})`);
console.log('------------------------------------------------');
line('Node.js', process.version);
try {
  line('npm', execFileSync('npm', ['--version'], { encoding: 'utf8' }).trim());
} catch {
  line('npm', 'NOT FOUND');
  missing.push('npm');
}

for (const name of Object.keys(required)) {
  try {
    import.meta.resolve(name);
    line(`Dependency: ${name}`, 'available');
  } catch {
    line(`Dependency: ${name}`, 'MISSING');
    missing.push(name);
  }
}

const registry = execFileSync('npm', ['config', 'get', 'registry'], { encoding: 'utf8' }).trim();
line('npm registry', registry);
const registryHost = new URL(registry).hostname;
try {
  const result = await lookup(registryHost);
  line('Registry DNS', `available (${result.address})`);
} catch (error) {
  line('Registry DNS', `unavailable (${error.code ?? error.message})`);
  missing.push('registry DNS');
}

console.log('------------------------------------------------');
if (missing.length) {
  console.log(`Build prerequisites incomplete: ${missing.join(', ')}`);
  console.log('Install dependencies with: npm install --no-audit --no-fund');
  process.exitCode = 1;
} else {
  console.log('Build prerequisites appear available. Run npm run typecheck and npm run build.');
}
