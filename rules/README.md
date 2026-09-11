# Repository rules

`rules/**` is the repository control plane for **how changes may be executed**.

It does not define product behavior.

```text
openspec/specs/**   WHAT THE SYSTEM DOES — current behavioral contract
openspec/changes/** WHAT WE ARE CHANGING — proposals/deltas/tasks
rules/**            HOW CHANGES ARE ROUTED, APPROVED, RECONCILED, VERIFIED
docs/**             WHY / EVIDENCE / HISTORY / GUIDES
```

## Resolution

For every change:

1. classify the actual change type;
2. match applicable topics/contracts in `policy.yaml`;
3. load only referenced current specs/workflows/evidence;
4. resolve the strictest approval policy;
5. execute only registered workflow/verification obligations;
6. recompute when scope expands.

## Approval

```text
autonomous < workflow_allowed < human_required
```

Effective policy is the strictest applicable policy across:

```text
change class
topic
contract boundary
```

Policy may escalate as a task discovers new scope. Tool configuration may raise restrictions but never lower repository policy.

### autonomous

The agent may execute without a separate human gate when all applicable rules and verification obligations are satisfied.

### workflow_allowed

The agent may execute without separate semantic approval only through every applicable workflow and only while no semantic ambiguity/authority blocker remains.

### human_required

Intended semantics/consumer-visible behavior must be explicitly approved before semantic implementation. After approval, mechanical implementation/reconciliation/verification continues without repeated confirmation until new semantic ambiguity appears.

## Authority

When present, `openspec/specs/<capability>/spec.md` is the current behavioral contract for that capability.

`openspec/changes/<change>/specs/**` is a proposed delta until finalized/archived into current specs.

Legacy documents under `docs/legacy/**` are evidence/history, not current behavioral authority unless `policy.yaml` explicitly says otherwise.

Do not create new normative behavioral specs under a separate top-level `specs/` directory.

## Workflows

`rules/workflows/**` contains only cross-cutting procedures that cannot be represented by a topic spec alone, for example API publication/client regeneration or shared Proto regeneration.

Load a workflow only when `policy.yaml` selects it.

## Verification

`policy.yaml` stores exact registered invocations. Commands are closed-world: do not infer tools, aliases, URLs, services, executable paths, or additional verification modalities.

If required evidence is unavailable, report `MISSING_EVIDENCE` rather than inventing a substitute.

## Conflict classes

```text
DRIFT
SEMANTIC_CONFLICT
MISSING_EVIDENCE
UNRESOLVED_AUTHORITY
BROKEN_ROUTING
```

Semantic/authority/routing conflicts block semantic implementation. Drift is reconciled from the authoritative source through the registered pipeline.
