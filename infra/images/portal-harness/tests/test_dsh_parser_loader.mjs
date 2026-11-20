import assert from 'node:assert/strict'
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import * as Module from 'node:module'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { loadDshParser } from '../dsh-parser-loader.mjs'

async function fixture(run) {
    const root = await mkdtemp(join(tmpdir(), 'portal-parser-fixture-'))
    try {
        const sourceDirectory = join(root, 'node_modules/@deepseek-ai/dsh/src')
        const commander = join(root, 'node_modules/commander')
        const scratch = join(root, 'scratch')
        await mkdir(sourceDirectory, { recursive: true })
        await mkdir(commander, { recursive: true })
        await mkdir(scratch)
        await writeFile(join(commander, 'package.json'), JSON.stringify({ name: 'commander', main: './index.cjs' }))
        await writeFile(join(commander, 'index.cjs'), 'exports.marker = "original-dependency"\n')
        const sourcePath = join(sourceDirectory, 'args.ts')
        const source = 'import { marker } from "commander"; export function parseDshArgs(value: string) { return marker + ":" + value }'
        await writeFile(sourcePath, source)
        await run({ root, sourcePath, source, scratch })
    } finally {
        await rm(root, { recursive: true, force: true })
    }
}

test('loads explicit JavaScript output with the original dependency and cleans temporary files', async () => {
    await fixture(async ({ sourcePath, source, scratch }) => {
        let calls = 0
        const parser = await loadDshParser(sourcePath, {
            temporaryRoot: scratch,
            stripTypes(input, options) {
                calls++
                assert.equal(input, source)
                assert.equal(options.mode, 'strip')
                // A mocked transform result tests loading, not a substitute TS compiler.
                return 'import { marker } from "commander"; export function parseDshArgs(value) { return marker + ":" + value }'
            },
        })
        assert.equal(calls, 1)
        assert.equal(parser('web'), 'original-dependency:web')
        assert.equal(await readFile(sourcePath, 'utf8'), source)
        assert.deepEqual(await readdir(scratch), [])
    })
})

test('cleans temporary files when transformed output cannot be imported', async () => {
    await fixture(async ({ sourcePath, scratch }) => {
        await assert.rejects(loadDshParser(sourcePath, { temporaryRoot: scratch, stripTypes: () => 'invalid syntax !!!' }))
        assert.deepEqual(await readdir(scratch), [])
    })
})

test('rejects a missing parser export', async () => {
    await fixture(async ({ sourcePath, scratch }) => {
        await assert.rejects(loadDshParser(sourcePath, { temporaryRoot: scratch, stripTypes: () => 'export const other = 1' }), /export is missing/)
        assert.deepEqual(await readdir(scratch), [])
    })
})

test('reports an unsupported Node API instead of installing tools', async () => {
    await fixture(async ({ sourcePath, scratch }) => {
        await assert.rejects(loadDshParser(sourcePath, { temporaryRoot: scratch, stripTypes: null }), /requires Node/)
        assert.deepEqual(await readdir(scratch), [])
    })
})

test('native Node stripping handles a source file under node_modules', {
    skip: typeof Module.stripTypeScriptTypes !== 'function' ? 'Native strip API absent; exercised by Node 24 in the image build' : false,
}, async () => {
    await fixture(async ({ sourcePath, source, scratch }) => {
        const parser = await loadDshParser(sourcePath, { temporaryRoot: scratch })
        assert.equal(parser('web'), 'original-dependency:web')
        assert.equal(await readFile(sourcePath, 'utf8'), source)
        assert.deepEqual(await readdir(scratch), [])
    })
})
