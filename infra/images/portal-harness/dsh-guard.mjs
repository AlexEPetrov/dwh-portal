import fs from 'node:fs'

export const name = 'portal-packaging-guard'
export const inject = ['tools', 'systemPrompt']

export const catalogTools = Object.freeze([
    'mcp__portal__search_catalog',
    'mcp__portal__get_object',
    'mcp__portal__get_lineage',
    'mcp__portal__get_object_links',
])

export function catalogGuard(execution) {
    if (!catalogTools.includes(execution.name)) {
        return 'Only the Portal read-only catalog MCP tools are permitted.'
    }
}

export const catalogStatusPath = '/tmp/portal-harness-catalog-status.json'

// Inspect actual DSH definitions, not a separate SDK connection. Only approved
// names/statuses are persisted; schemas, arguments and credentials never are.
export function catalogAvailability(definitions) {
    const names = new Set(definitions.map(definition => definition.name))
    const available = catalogTools.filter(name => names.has(name))
    const missing = catalogTools.filter(name => !names.has(name))
    return { state: missing.length ? 'unavailable' : 'ready', available, missing }
}

// The monotonic guard cannot be turned into an allow by a later tool listener.
export function apply(ctx) {
    // This plugin is host-scoped. Pinned DSH rejects restrict() outside an
    // agent scope (and before MCP discovery its tool names are not registered).
    // A global monotonic guard enforces the exact policy for every agent.
    ctx.tools.guard(catalogGuard)
    let lastAgentAssembly = { state: 'unknown' }
    let previous
    function inspect(scope, toolSet) {
        try {
            return catalogAvailability(ctx.tools.definitions(scope, toolSet))
        } catch {
            return { state: 'unknown' }
        }
    }
    function publish() {
        const value = JSON.stringify({
            version: 1,
            pid: process.pid,
            global: inspect(),
            last_agent_assembly: lastAgentAssembly,
        })
        if (value === previous) return
        // Atomic replacement prevents health checks from accepting partial JSON.
        fs.writeFileSync(`${catalogStatusPath}.next`, value, { mode: 0o600 })
        fs.renameSync(`${catalogStatusPath}.next`, catalogStatusPath)
        previous = value
    }
    ctx.on('tools/change', () => {
        lastAgentAssembly = { state: 'unknown' }
        publish()
    })
    ctx.systemPrompt.context({
        name: 'portal-catalog-availability',
        order: 50,
        required: true,
        interpolate: false,
        text: ({ scope, toolSet }) => {
            const visible = inspect(scope, toolSet)
            // No scope/step set means inspection, not evidence of model admission.
            if (scope !== undefined && toolSet !== undefined) {
                lastAgentAssembly = visible
                publish()
            }
            if (visible.state === 'ready') {
                return 'Portal catalog capabilities are available in this scope. Select the '
                    + 'appropriate tools from their schemas for the user’s natural-language '
                    + 'question; never require tool names or command syntax from the user. '
                    + 'Availability alone is not evidence of a completed catalog read.'
            }
            return 'Portal catalog capabilities are unavailable or their availability is unknown '
                + 'in this scope. Explain missing catalog access in the user’s language when '
                + 'needed; do not invent results, resource URIs, tool names or execution fallbacks.'
        },
    })
    publish()
    fs.writeFileSync('/tmp/portal-harness-guard-ready', String(process.pid), { mode: 0o600 })
}
