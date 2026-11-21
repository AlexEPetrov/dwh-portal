// Container-only protocol check using the very SDK deployed for DSH's client.
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import { catalogGuard, catalogTools } from './dsh-guard.mjs'

const require = createRequire('/opt/dsh/node_modules/@deepseek-ai/dsh-mcp-client/package.json')
const { Client, StreamableHTTPClientTransport } = await import(
    pathToFileURL(require.resolve('@modelcontextprotocol/client')).href
)
const client = new Client({ name: 'portal-offline-smoke', version: '1' })
const transport = new StreamableHTTPClientTransport(new URL('http://127.0.0.1:5051/mcp'))

function payload(result) {
    assert.notEqual(result.isError, true)
    assert.ok(result.structuredContent, 'SDK must preserve structured catalog output')
    assert.equal(typeof result.structuredContent.navigation?.portal, 'string')
    assert.equal(typeof result.structuredContent.navigation?.universe, 'string')
    return result.structuredContent.data
}

try {
    await client.connect(transport)
    const listed = await client.listTools()
    assert.deepEqual(
        listed.tools.map(tool => `mcp__portal__${tool.name}`).sort(),
        [...catalogTools].sort(),
    )
    for (const tool of listed.tools) {
        assert.equal(catalogGuard({ name: `mcp__portal__${tool.name}` }), undefined)
        assert.equal(tool.annotations.readOnlyHint, true)
    }
    const search = payload(await client.callTool({
        name: 'search_catalog', arguments: { q: 'ice_brent', asset_types: ['TABLE'] },
    }))
    assert.ok(search.items.length > 0)
    const assetId = search.items[0].id
    const detail = payload(await client.callTool({ name: 'get_object', arguments: { asset_id: assetId } }))
    assert.equal(detail.object.id, assetId)
    assert.ok(detail.columns.length > 0)
    const lineage = payload(await client.callTool({ name: 'get_lineage', arguments: { asset_id: assetId } }))
    assert.equal(lineage.asset_id, assetId)
    assert.equal(lineage.bounded, true)
    assert.ok(lineage.nodes.length > 0)
    const links = payload(await client.callTool({ name: 'get_object_links', arguments: { asset_id: assetId } }))
    assert.ok(links.object.endsWith(`/objects/${assetId}`))
    assert.ok(links.lineage.endsWith(`/lineage/${assetId}`))
    assert.ok(links.universe.endsWith(`/lineage/universe/${assetId}`))
    assert.equal(typeof catalogGuard({ name: 'bash' }), 'string')
    console.log('PASS: pinned DSH MCP SDK → Portal HTTP catalog tools (no model/provider call)')
} finally {
    await client.close()
}
