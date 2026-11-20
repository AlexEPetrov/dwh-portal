import { writeFileSync } from 'node:fs'

export const name = 'portal-packaging-guard'
export const inject = ['tools']

// The monotonic guard cannot be turned into an allow by a later tool listener.
export function apply(ctx) {
    ctx.tools.guard(() => 'Catalog MCP is not connected; tools are disabled in the packaging prototype.')
    writeFileSync('/tmp/portal-harness-guard-ready', String(process.pid), { mode: 0o600 })
}
