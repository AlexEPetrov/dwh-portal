import fs from 'node:fs/promises';
import path from 'node:path';
import ts from 'typescript';

// Emit each library independently. Runtime dependencies remain external, and
// explicit relative ESM extensions also make declaration imports portable.
const root = process.cwd();
const manifest = JSON.parse(await fs.readFile(path.join(root, 'package.json'), 'utf8'));
if (!['@asset-management/ui-kit', '@asset-management/app-shell'].includes(manifest.name)) {
    throw new Error('Run this builder in a library workspace');
}
const config = ts.parseJsonConfigFileContent({
    compilerOptions: {
        target: 'ES2020', module: 'ESNext', moduleResolution: 'Bundler',
        lib: ['ES2020', 'DOM', 'DOM.Iterable'], jsx: 'react-jsx', strict: true,
        skipLibCheck: true, declaration: true, noEmitOnError: true,
        rootDir: 'src', outDir: 'dist', types: ['react', 'react-dom'],
    },
    include: ['src/**/*.ts', 'src/**/*.tsx'],
}, ts.sys, root);
const program = ts.createProgram(config.fileNames, config.options);
const diagnostics = [...config.errors, ...ts.getPreEmitDiagnostics(program)];
if (diagnostics.length) {
    console.error(ts.formatDiagnosticsWithColorAndContext(diagnostics, {
        getCurrentDirectory: () => root, getCanonicalFileName: name => name,
        getNewLine: () => '\n',
    }));
    process.exit(1);
}

function explicitExtensions(context) {
    return source => {
        function visit(node) {
            if (ts.isStringLiteral(node) && node.text.startsWith('.')) {
                const parent = node.parent;
                const isSpecifier = parent && (
                    (ts.isImportDeclaration(parent) || ts.isExportDeclaration(parent)) && parent.moduleSpecifier === node
                    || ts.isCallExpression(parent) && parent.expression.kind === ts.SyntaxKind.ImportKeyword
                    || ts.isLiteralTypeNode(parent) && ts.isImportTypeNode(parent.parent)
                );
                // Synthesized declaration nodes may not have parent links. The module
                // declarations below are rewritten explicitly as well.
                if (isSpecifier) return rewrite(node);
            }
            if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
                return context.factory.updateImportDeclaration(node, node.modifiers, node.importClause,
                    rewrite(node.moduleSpecifier), node.attributes);
            }
            if (ts.isExportDeclaration(node) && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)) {
                return context.factory.updateExportDeclaration(node, node.modifiers, node.isTypeOnly,
                    node.exportClause, rewrite(node.moduleSpecifier), node.attributes);
            }
            return ts.visitEachChild(node, visit, context);
        }
        function rewrite(node) {
            if (!node.text.startsWith('.')) return node;
            const resolved = ts.resolveModuleName(node.text, source.fileName, config.options, ts.sys).resolvedModule;
            if (!resolved || !/\.tsx?$/.test(resolved.resolvedFileName)) return node;
            let relative = path.relative(path.dirname(source.fileName), resolved.resolvedFileName).replaceAll(path.sep, '/');
            if (!relative.startsWith('.')) relative = `./${relative}`;
            return context.factory.createStringLiteral(relative.replace(/\.tsx?$/, '.js'));
        }
        return ts.visitNode(source, visit);
    };
}

// Only this package's generated output is replaced, after type checking succeeds.
await fs.rm(path.join(root, 'dist'), { recursive: true, force: true });
const result = program.emit(undefined, undefined, undefined, undefined, {
    after: [explicitExtensions], afterDeclarations: [explicitExtensions],
});
if (result.emitSkipped) throw new Error(`Emission failed for ${manifest.name}`);
async function copyStyles(directory) {
    for (const entry of await fs.readdir(path.join(root, 'src', directory), { withFileTypes: true })) {
        const relative = path.join(directory, entry.name);
        if (entry.isDirectory()) await copyStyles(relative);
        else if (entry.name.endsWith('.css')) {
            const target = path.join(root, 'dist', relative);
            await fs.mkdir(path.dirname(target), { recursive: true });
            await fs.copyFile(path.join(root, 'src', relative), target);
        }
    }
}
await copyStyles('');
console.log(`Built ${manifest.name}: ESM, declarations and CSS`);
