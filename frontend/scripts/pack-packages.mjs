import { execFileSync } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const frontend = fileURLToPath(new URL('../', import.meta.url));
export const libraries = ['ui-kit', 'app-shell'];

export async function packPackages(destination) {
    await fs.mkdir(destination, { recursive: true });
    const packages = [];
    for (const library of libraries) {
        const cwd = path.join(frontend, library);
        const manifest = JSON.parse(await fs.readFile(path.join(cwd, 'package.json'), 'utf8'));
        // Callers build in dependency order first. Do not invoke lifecycle scripts
        // from the archive, which deliberately excludes repository build tooling.
        const [packed] = JSON.parse(execFileSync('npm', [
            'pack', '--ignore-scripts', '--json', '--pack-destination', destination,
        ], { cwd, encoding: 'utf8' }));
        packages.push({ library, manifest, packed, archive: path.join(destination, packed.filename) });
    }
    return packages;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
    for (const result of await packPackages(path.join(frontend, 'artifacts'))) console.log(result.archive);
}
