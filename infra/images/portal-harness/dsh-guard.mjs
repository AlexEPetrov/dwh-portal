import fs from 'node:fs'

export const name = 'portal-packaging-guard'
export const inject = ['tools']

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

// The monotonic guard cannot be turned into an allow by a later tool listener.
export function apply(ctx) {
    // This plugin is host-scoped. Pinned DSH rejects restrict() outside an
    // agent scope (and before MCP discovery its tool names are not registered).
    // A global monotonic guard enforces the exact policy for every agent.
    ctx.tools.guard(catalogGuard)
    fs.writeFileSync('/tmp/portal-harness-guard-ready', String(process.pid), { mode: 0o600 })
}
