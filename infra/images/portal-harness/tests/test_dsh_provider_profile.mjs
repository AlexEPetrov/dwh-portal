// Dependency-free checks of our patch expressions, not a substitute for DSH startup.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { runInNewContext } from 'node:vm'

const source = readFileSync(new URL('../dsh.patch.yml', import.meta.url), 'utf8')
const publicRows = [
    'llm-deepseek', 'llm-deepseek-account', 'deepseek-account',
    'ui-settings-account', 'ui-account-notifications',
    'web-search-deepseek', 'web-deepseek-api', 'llm-pi-ai', 'agent-default-model',
]

function evaluate(id, key, env) {
    let selected = false
    for (const line of source.split('\n')) {
        const text = line.trim()
        if (text.startsWith('- id: ')) {
            if (selected) break
            selected = text === `- id: ${id}`
        } else if (selected && text.startsWith(`${key}: !!js `)) {
            const expression = JSON.parse(text.slice(`${key}: !!js `.length))
            return runInNewContext(expression, { process: { env } })
        }
    }
    assert.fail(`Missing ${id}.${key} expression`)
}

test('Ollama and unset modes disable built-in public providers and old settings namespaces', () => {
    for (const env of [{}, { PORTAL_PROVIDER_MODE: 'ollama' }]) {
        for (const id of publicRows) assert.equal(evaluate(id, 'disabled', env), true, id)
        assert.equal(evaluate('portal-ollama', 'disabled', env), false)
        assert.equal(evaluate('portal-ollama-default-model', 'disabled', env), false)
        assert.equal(Object.keys(evaluate('portal-ollama', 'providers', env)).length, 0)
    }
})

test('public providers require explicit upstream mode', () => {
    const env = { PORTAL_PROVIDER_MODE: 'upstream' }
    for (const id of publicRows) assert.equal(evaluate(id, 'disabled', env), false, id)
    assert.equal(evaluate('portal-ollama', 'disabled', env), true)
    assert.equal(evaluate('portal-ollama-default-model', 'disabled', env), true)
})

test('declared Ollama model configuration does not expand to a cloud catalog', () => {
    const profiles = {
        'portal-ollama': {
            api: 'openai-completions', baseURL: 'http://ollama.internal:11434/v1',
            models: [{ id: 'test-local-model', contextWindow: 8192, maxTokens: 2048 }],
        }
    }
    const env = {
        PORTAL_PROVIDER_MODE: 'ollama', PORTAL_OLLAMA_MODEL: 'test-local-model',
        PORTAL_OLLAMA_PROVIDERS: JSON.stringify(profiles)
    }
    assert.equal(JSON.stringify(evaluate('portal-ollama', 'providers', env)), JSON.stringify(profiles))
    assert.equal(evaluate('portal-ollama-default-model', 'model', env), 'test-local-model')
})
