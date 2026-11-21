import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { apply, catalogGuard, catalogTools } from '../dsh-guard.mjs'

test('allows exactly four server-qualified Portal catalog tools', () => {
    assert.deepEqual(catalogTools, [
        'mcp__portal__search_catalog',
        'mcp__portal__get_object',
        'mcp__portal__get_lineage',
        'mcp__portal__get_object_links',
    ])
    for (const name of catalogTools) assert.equal(catalogGuard({ name }), undefined)
})

test('denies general tools, other servers and prefix lookalikes', () => {
    for (const name of [
        'bash', 'read_file', 'run_code', 'browser', 'collect',
        'mcp__other__search_catalog', 'search_catalog',
        'mcp__portal__collect', 'mcp__portal__get_object_extra',
        'mcp__portal__get_object;bash', '', undefined,
    ]) assert.equal(typeof catalogGuard({ name }), 'string')
})

test('activates in host scope before MCP tools are discovered and marks ready only after registration', (t) => {
    const calls = []
    t.mock.method(fs, 'writeFileSync', (path, value, options) => {
        calls.push('ready')
        assert.deepEqual(calls, ['guard', 'ready'])
        assert.equal(path, '/tmp/portal-harness-guard-ready')
        assert.equal(value, String(process.pid))
        assert.deepEqual(options, { mode: 0o600 })
    })
    // Faithful to pinned ToolsService: restrict() is illegal at host scope.
    // No agent or catalog registration exists yet during plugin activation.
    const tools = {
        restrict() { throw new Error('tools.restrict() requires a scoped context (agent.ctx)') },
        guard(callback) {
            calls.push('guard')
            assert.equal(callback, catalogGuard)
            for (const name of catalogTools) assert.equal(callback({ name }), undefined)
            assert.equal(typeof callback({ name: 'bash' }), 'string')
        },
    }
    apply({ tools })
    assert.deepEqual(calls, ['guard', 'ready'])
})

test('does not mark ready when guard registration fails', (t) => {
    const ready = t.mock.method(fs, 'writeFileSync', () => { })
    assert.throws(() => apply({
        tools: {
            guard() { throw new Error('guard registration failed') },
        }
    }), /guard registration failed/)
    assert.equal(ready.mock.callCount(), 0)
})

test('propagates readiness marker failures instead of reporting successful activation', (t) => {
    let registered = false
    t.mock.method(fs, 'writeFileSync', () => { throw new Error('marker unavailable') })
    assert.throws(() => apply({
        tools: {
            guard(callback) {
                assert.equal(callback, catalogGuard)
                registered = true
            },
        }
    }), /marker unavailable/)
    assert.equal(registered, true)
})
