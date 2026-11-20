// Node does not automatically strip TypeScript inside node_modules. Explicitly
// strip the pinned source and import temporary JS with its original dependency.
import { mkdir, mkdtemp, readFile, rm, symlink, writeFile } from 'node:fs/promises'
import * as Module from 'node:module'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { pathToFileURL } from 'node:url'

async function commanderRoot(sourcePath) {
    const require = Module.createRequire(pathToFileURL(sourcePath))
    let directory = dirname(require.resolve('commander'))
    while (true) {
        try {
            const manifest = JSON.parse(await readFile(join(directory, 'package.json'), 'utf8'))
            if (manifest.name === 'commander') return directory
        } catch (error) {
            if (error.code !== 'ENOENT') throw error
        }
        const parent = dirname(directory)
        if (parent === directory) throw new Error('Cannot locate the parser Commander package')
        directory = parent
    }
}

export async function loadDshParser(sourcePath, {
    stripTypes = Module.stripTypeScriptTypes,
    temporaryRoot = tmpdir(),
} = {}) {
    if (typeof stripTypes !== 'function') {
        throw new Error('DSH parser validation requires Node with stripTypeScriptTypes (the image uses Node 24)')
    }
    const dependency = await commanderRoot(sourcePath)
    const source = await readFile(sourcePath, 'utf8')
    const javascript = stripTypes(source, { mode: 'strip', sourceUrl: sourcePath })
    const temporary = await mkdtemp(join(temporaryRoot, 'dsh-parser-check-'))
    try {
        await mkdir(join(temporary, 'node_modules'))
        await symlink(dependency, join(temporary, 'node_modules', 'commander'), 'dir')
        const target = join(temporary, 'args.mjs')
        await writeFile(target, javascript)
        const parser = await import(pathToFileURL(target).href)
        if (typeof parser.parseDshArgs !== 'function') throw new Error('Pinned DSH parser export is missing')
        return parser.parseDshArgs
    } finally {
        await rm(temporary, { recursive: true, force: true })
    }
}
