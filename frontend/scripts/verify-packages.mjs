import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import ts from 'typescript';
import { build } from 'vite';
import { frontend, packPackages } from './pack-packages.mjs';

const temporary = await fs.mkdtemp(path.join(os.tmpdir(), 'portal-package-consumer-'));
try {
    const packages = await packPackages(path.join(temporary, 'archives'));
    const modules = path.join(temporary, 'node_modules');
    await fs.mkdir(path.join(modules, '@asset-management'), { recursive: true });
    // Reuse installed third-party peers, but never workspace package symlinks.
    // No network, cache assumptions or dependency installation are needed.
    const peers = new Set(['@types/react', '@types/react-dom']);
    for (const { manifest } of packages) {
        for (const name of Object.keys(manifest.peerDependencies ?? {})) peers.add(name);
    }
    for (const entry of peers) {
        const target = path.join(modules, entry);
        await fs.mkdir(path.dirname(target), { recursive: true });
        await fs.symlink(path.join(frontend, 'node_modules', entry), target);
    }
    const imports = [];
    for (const { manifest, packed, archive } of packages) {
        assert(packed.files.every(({ path: name }) => name.startsWith('dist/') || ['package.json', 'README.md'].includes(name)),
            `${manifest.name}: unexpected archive payload`);
        const target = path.join(modules, manifest.name);
        await fs.mkdir(target, { recursive: true });
        execFileSync('tar', ['-xzf', archive, '--strip-components=1', '-C', target]);
        assert(!(await fs.lstat(target)).isSymbolicLink());
        for (const [subpath, value] of Object.entries(manifest.exports)) {
            const specifier = manifest.name + (subpath === '.' ? '' : subpath.slice(1));
            for (const file of typeof value === 'string' ? [value] : Object.values(value)) {
                await fs.access(path.join(target, file));
            }
            if (typeof value === 'string') imports.push(`import '${specifier}';`);
            else {
                const alias = `entry${imports.length}`;
                imports.push(`import * as ${alias} from '${specifier}';\nconsole.log(${alias});`);
            }
        }
        assert(!packed.files.some(({ path: name }) => name.startsWith('src/')));
    }
    await fs.writeFile(path.join(temporary, 'package.json'), JSON.stringify({ private: true, type: 'module' }));
    await fs.writeFile(path.join(temporary, 'index.html'), '<div id="root"></div><script type="module" src="/main.ts"></script>');
    const main = path.join(temporary, 'main.ts');
    await fs.writeFile(main, imports.join('\n'));
    const options = {
        target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ESNext,
        moduleResolution: ts.ModuleResolutionKind.Bundler, jsx: ts.JsxEmit.ReactJSX,
        strict: true, noEmit: true, skipLibCheck: false,
        types: ['react', 'react-dom'],
    };
    const program = ts.createProgram([main], options);
    const diagnostics = ts.getPreEmitDiagnostics(program);
    const formatHost = {
        getCurrentDirectory: () => temporary, getCanonicalFileName: name => name, getNewLine: () => '\n',
    };
    // The host already uses skipLibCheck for upstream declaration incompatibilities.
    // Still check our emitted declarations rather than skipping all library files.
    // Report external diagnostics separately; never hide a consumer/package error.
    const external = diagnostics.filter(diagnostic => diagnostic.file
        && !diagnostic.file.fileName.startsWith(temporary + path.sep));
    const owned = diagnostics.filter(diagnostic => !external.includes(diagnostic));
    assert.equal(owned.length, 0, ts.formatDiagnosticsWithColorAndContext(owned, formatHost));
    if (external.length) {
        console.warn(`Third-party declaration diagnostics (${external.length}; not package-owned):`);
        console.warn(ts.formatDiagnosticsWithColorAndContext(external, formatHost));
    }
    await build({
        root: temporary, configFile: false, logLevel: 'warn',
        plugins: [{
            name: 'assert-archive-isolation',
            moduleParsed({ id }) {
                for (const { library } of packages) {
                    assert(!id.startsWith(path.join(frontend, library) + path.sep), `Workspace library leaked into consumer: ${id}`);
                }
            },
        }],
        build: { minify: false },
    });
    const assets = path.join(temporary, 'dist', 'assets');
    const styles = (await Promise.all((await fs.readdir(assets)).filter(name => name.endsWith('.css'))
        .map(name => fs.readFile(path.join(assets, name), 'utf8')))).join('\n');
    assert(styles.includes('fonts.googleapis.com'), 'UI Kit foundation CSS missing');
    assert(styles.includes('.ag-theme-alpine'), 'Grid CSS missing');
    assert(styles.includes('100vw'), 'Shell geometry CSS missing');
    console.log(`PASS: both archive payloads, every public entry, package-owned declaration checking, isolated Vite consumer and CSS; ${external.length} third-party declaration diagnostics`);
} finally {
    // Remove only the uniquely created consumer, never repository/user files.
    await fs.rm(temporary, { recursive: true, force: true });
}
