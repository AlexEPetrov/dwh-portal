# AGENTS.md — root router

All agents MUST follow this file.

This file is a **repository router**, not a domain specification.

Canonical locations:

```text
openspec/specs/**   current behavioral contract — WHAT THE SYSTEM DOES
openspec/changes/** proposed/in-progress changes
rules/**            repository execution, routing, approval, contracts, verification
docs/**             rationale, evidence, history, guides
```

## 1. Resolve context before editing

Before editing:

1. Read this root `AGENTS.md`.
2. Determine intended changed paths and change types.
3. Load every applicable nested `AGENTS.md` from root to leaf.
4. Read `rules/README.md` and resolve applicable policy from `rules/policy.yaml`.
5. Load only the referenced current specs needed for the task.
6. Do not begin a semantic edit while routing, authority, or required approval is unresolved.

When paths/change types expand, recompute:

```text
ApplicableContext(changed_paths, change_types, repository_state)
```

Contract/workflow obligations may add downstream reconciliation targets **before those paths appear in the diff**.

## 2. Authority and precedence

Instruction precedence, semantic authority, and executable evidence are separate.

```text
non-overridable root invariants
> approved task scope within those invariants
> applicable scoped AGENTS.md
> applicable repository workflow
> tool-specific adapter guidance
```

Nested/tool-specific instructions may refine or strengthen repository rules, but may not weaken root invariants or resolved `approval_policy`.

Current behavioral authority lives in `openspec/specs/**` when a current spec exists for the topic. Legacy material under `docs/**` is evidence/history unless explicitly registered otherwise in `rules/policy.yaml`.

## 3. Global invariants

### Preserve repository and user state

- Never commit secrets, credentials, tokens, private keys, or `.env` files.
- Do not discard, reset, restore, stash, clean, or overwrite existing working-tree changes unless explicitly required and approved.
- Generated artifacts are read-only **by hand**. Change the authoring source and use the registered generation/reconciliation path.
- Merged database migrations are immutable; create a new migration.

### Execution is closed-world

Do not invent execution steps, tools, paths, services, URLs, aliases, or verification modalities.

Run only actions required by the applicable workflow or registered verification evidence.

If required execution evidence is missing, classify it as `MISSING_EVIDENCE`. Do not guess substitutes, scan arbitrary installation locations, install tools, infer executables, or rewrite a registered command.

Canonical invocations are in `rules/policy.yaml` and are exact, including cwd, arguments, environment, redirects, and pipes.

### Reconciliation is contract-driven

- Do not bypass contract pipelines with handwritten substitutes or ad-hoc direct calls.
- Required downstream artifacts/consumers come from the applicable contract/workflow, not only from files already present in the diff.
- Shared behavior across producer/consumer or Python/Rust boundaries must not silently diverge.

### Blocked semantics stay blocked

Do not resolve `SEMANTIC_CONFLICT`, `UNRESOLVED_AUTHORITY`, or `BROKEN_ROUTING` by guesswork.

Cursor/ZooCode/OpenSpec adapters may impose stricter execution limits, but may never relax repository policy.

## 4. Approval policy

The canonical model is defined in `rules/README.md` and ranked in `rules/policy.yaml`:

```text
autonomous < workflow_allowed < human_required
```

The strictest applicable policy wins across change class, topic, and contract boundary.

Path sensitivity alone does not make a change semantic; classify actual behavior effect.

Before required human approval, analysis/proposal work is allowed, but new business/calculation/public-contract semantics must not be selected or implemented.

After approval, continue approved mechanical implementation, regeneration, reconciliation, and verification without repeated approval unless new semantic ambiguity appears.

## 5. Path routing

| Changed path | Also load |
|---|---|
| `backend/core-service/**` | `backend/core-service/AGENTS.md` |
| `frontend/web/**` | `frontend/web/AGENTS.md` |
| `common/contracts/**` | applicable producer/consumer routers + contract workflow |
| `openspec/**` | OpenSpec change/spec lifecycle + applicable topic policy |
| `rules/**` | `rules/README.md`; policy/workflow maintenance |
| `docs/**` | documentation policy/evidence only as applicable |
| `infra/**` | applicable workflow; deployment/environment edits require explicit scope |

Detailed topic/workflow/contract routing belongs in `rules/policy.yaml`, not here.

## 6. Task execution

### Start

Resolve `ApplicableContext` before editing. Routine routing is the agent's responsibility; do not require the user to enumerate governance.

Surface only decisions requiring human approval, unresolved authority/semantic blockers, and material scope changes. Do not dump full routing analysis unless requested.

### During

When actual paths/change types expand, rerun `ApplicableContext` before editing newly activated scopes.

### Closeout

Before completion, report only material facts:

- actual changed scopes;
- workflows/contracts applied;
- approval decisions used;
- authoring sources and generated/published artifacts affected;
- verification actually executed;
- unresolved blockers, drift, or approved exceptions.

Do not mark work complete while required authority, reconciliation, or verification remains unresolved.

## 7. Repository conventions

- `AGENTS.md` files are written in English.
- Use repository-relative paths in repository documentation.
- Do not translate identifiers, filenames, paths, commands, API names, or code symbols.
- New behavioral specs belong in `openspec/specs/**`.
- Detailed rationale/evidence belongs in `docs/**`.

### OpenSpec authoring

Every current capability spec MUST start with a clear H1 title and a
`## Purpose` section before its requirements.

`Purpose` MUST explain the capability in concise, human-readable,
product-facing language. It should describe what the capability provides
and why it exists, not its implementation.

This text may be reused directly in generated documentation.

## 8. Portability

Repository governance must remain usable without Cursor-, ZooCode-, or OpenSpec-specific runtime behavior.

```text
same repository state
+ same changed paths
+ same change types
=> equivalent repository obligations
```

Tool configuration is disposable; repository semantics and rules are durable.
