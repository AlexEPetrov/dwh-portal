import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { apply, catalogGuard, catalogStatusPath, catalogTools } from '../dsh-guard.mjs'

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
        assert.deepEqual(options, { mode: 0o600 })
        if (path === `${catalogStatusPath}.next`) {
            assert.equal(JSON.parse(value).global.state, 'unavailable')
            calls.push('status')
            return
        }
        calls.push('ready')
        assert.deepEqual(calls, ['guard', 'status', 'ready'])
        assert.equal(path, '/tmp/portal-harness-guard-ready')
        assert.equal(value, String(process.pid))
    })
    t.mock.method(fs, 'renameSync', () => { })
    // Faithful to pinned ToolsService: restrict() is illegal at host scope.
    // No agent or catalog registration exists yet during plugin activation.
    const tools = {
        definitions() { return [] },
        restrict() { throw new Error('tools.restrict() requires a scoped context (agent.ctx)') },
        guard(callback) {
            calls.push('guard')
            assert.equal(callback, catalogGuard)
            for (const name of catalogTools) assert.equal(callback({ name }), undefined)
            assert.equal(typeof callback({ name: 'bash' }), 'string')
        },
    }
    apply({ tools, on() { }, systemPrompt: { context() { } } })
    assert.deepEqual(calls, ['guard', 'status', 'ready'])
})

test('does not mark ready when guard registration fails', (t) => {
    const ready = t.mock.method(fs, 'writeFileSync', () => { })
    assert.throws(() => apply({
        on() { },
        systemPrompt: { context() { } },
        tools: {
            guard() { throw new Error('guard registration failed') },
        }
    }), /guard registration failed/)
    assert.equal(ready.mock.callCount(), 0)
})

test('propagates readiness marker failures instead of reporting successful activation', (t) => {
    let registered = false
    t.mock.method(fs, 'writeFileSync', (path) => {
        if (path === '/tmp/portal-harness-guard-ready') throw new Error('marker unavailable')
    })
    t.mock.method(fs, 'renameSync', () => { })
    assert.throws(() => apply({
        on() { },
        systemPrompt: { context() { } },
        tools: {
            definitions() { return [] },
            guard(callback) {
                assert.equal(callback, catalogGuard)
                registered = true
            },
        }
    }), /marker unavailable/)
    assert.equal(registered, true)
})

function fixture(t) {
    let globalDefinitions = []
    const files = new Map()
    const events = new Map()
    let context
    t.mock.method(fs, 'writeFileSync', (path, value) => files.set(path, value))
    t.mock.method(fs, 'renameSync', (source, target) => {
        assert.equal(source, `${catalogStatusPath}.next`)
        assert.equal(target, catalogStatusPath)
        files.set(target, files.get(source))
        files.delete(source)
    })
    const scopes = new Map()
    const ctx = {
        tools: {
            guard(callback) { assert.equal(callback, catalogGuard) },
            definitions(scope, toolSet) {
                if (toolSet !== undefined) return toolSet.definitions
                return scope === undefined ? globalDefinitions : scopes.get(scope)
            },
        },
        on(event, callback) { events.set(event, callback) },
        systemPrompt: { context(value) { context = value } },
    }
    apply(ctx)
    return {
        files, scopes, ctx,
        status: () => JSON.parse(files.get(catalogStatusPath)),
        change(names) {
            globalDefinitions = names.map(name => ({ name }))
            events.get('tools/change')()
        },
        get context() { return context },
    }
}

test('observes actual host registration, partial sets, lookalikes and disconnects', (t) => {
    const f = fixture(t)
    assert.equal(f.files.get('/tmp/portal-harness-guard-ready'), String(process.pid))
    assert.equal(f.status().pid, process.pid)
    assert.equal(f.status().global.state, 'unavailable')
    assert.equal(f.status().last_agent_assembly.state, 'unknown')
    f.change([...catalogTools.slice(1), 'mcp__portal__search_catalog_extra'])
    assert.deepEqual(f.status().global.missing, [catalogTools[0]])
    f.change([...catalogTools, 'bash'])
    assert.equal(f.status().global.state, 'ready')
    assert.deepEqual(f.status().global.available, catalogTools)
    assert.equal(f.status().last_agent_assembly.state, 'unknown')
    assert.equal(JSON.stringify(f.status()).includes('bash'), false)
    f.change([])
    assert.equal(f.status().global.state, 'unavailable')
})

test('prompt reports scoped and step-admitted tools, not global readiness as model proof', (t) => {
    const f = fixture(t)
    f.change(catalogTools)
    const scope = {}
    f.scopes.set(scope, [])
    assert.equal(f.context.required, true)
    assert.equal(f.context.interpolate, false)
    assert.match(f.context.text({ scope }), /unavailable/)
    assert.equal(f.status().last_agent_assembly.state, 'unknown')
    // A step set is authoritative even if the global registry contains all four.
    const toolSet = { definitions: catalogTools.slice(1).map(name => ({ name })) }
    assert.match(f.context.text({ scope, toolSet }), /unavailable/)
    assert.deepEqual(f.status().last_agent_assembly.missing, [catalogTools[0]])
    toolSet.definitions = catalogTools.map(name => ({ name }))
    assert.match(f.context.text({ scope, toolSet }), /never require tool names/)
    assert.equal(f.status().last_agent_assembly.state, 'ready')
    assert.equal(f.status().global.state, 'ready')
    f.change([])
    assert.equal(f.status().last_agent_assembly.state, 'unknown')
})

test('registry inspection failure stays unknown and never enables fallbacks', (t) => {
    const f = fixture(t)
    f.ctx.tools.definitions = () => { throw new Error('credential-must-not-leak') }
    assert.match(f.context.text({ scope: {}, toolSet: {} }), /availability is unknown/)
    assert.equal(f.status().global.state, 'unknown')
    assert.equal(f.status().last_agent_assembly.state, 'unknown')
    assert.equal(JSON.stringify(f.status()).includes('credential'), false)
    assert.equal(typeof catalogGuard({ name: 'read_resource' }), 'string')
})

test('diagnostic publication failure prevents successful guard activation marker', (t) => {
    t.mock.method(fs, 'writeFileSync', () => { })
    t.mock.method(fs, 'renameSync', () => { throw new Error('atomic replacement failed') })
    assert.throws(() => apply({
        tools: { guard() { }, definitions() { return [] } },
        on() { }, systemPrompt: { context() { } },
    }), /atomic replacement failed/)
    assert.equal(fs.writeFileSync.mock.callCount(), 1)
    assert.equal(fs.writeFileSync.mock.calls[0].arguments[0], `${catalogStatusPath}.next`)
})
