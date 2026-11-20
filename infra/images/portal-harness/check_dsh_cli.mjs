// Exercise the pinned upstream parser, not a handwritten approximation.
// The deployed CLI includes its source (declared by its upstream package files).
import assert from 'node:assert/strict'
import { loadDshParser } from './dsh-parser-loader.mjs'

const parseDshArgs = await loadDshParser('/opt/dsh/node_modules/@deepseek-ai/dsh/src/args.ts')
const argv = JSON.parse(process.argv[2])
const invocation = parseDshArgs(argv, '0.2.2-rc.5')
assert.equal(invocation.mode, 'profile')
assert.equal(invocation.profile, 'web')
assert.deepEqual(invocation.patches, ['/opt/portal-harness/dsh.patch.yml'])
assert.equal(invocation.args[0], '--no-open')
assert.ok(!invocation.args.includes('--patch'), 'launcher flags must not reach the Web parser')
console.log('PASS: pinned DSH launcher consumed the patch before forwarding Web arguments')
