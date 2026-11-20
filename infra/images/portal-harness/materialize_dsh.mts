// Reuse upstream's relocation/validation helpers instead of rewriting symlinks.
import { deduplicateStagedWorkspacePackages, materializeStagedLinks } from '/build/dsh-source/scripts/build-exe-for-python-sdk-staging.ts'
import { verifyStagedDependencies } from '/build/dsh-source/scripts/executable-packaging.ts'

await materializeStagedLinks('/opt/dsh')
await deduplicateStagedWorkspacePackages('/opt/dsh', '/opt/dsh')
await verifyStagedDependencies('/opt/dsh')
