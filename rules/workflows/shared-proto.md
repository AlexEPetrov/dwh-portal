---
id: SPEC-WF-SHARED-PROTO
status: active
authority: normative-workflow
applies_to:
  - common/contracts/proto/**
  - backend/core-service/src/proto/**
  - backend/calc-service/proto/**
  - backend/calc-service/src/generated/**
approval_policy: workflow_allowed
owners: []
approvers: []
last_reviewed: 2026-08-18
related_gates:
  - AMB-004
---

# Workflow: shared Python↔Rust Proto contract

## Назначение

Этот workflow регулирует изменения shared Proto/wire contract между:

- `backend/core-service/`;
- `backend/calc-service/`;
- published Proto declarations under `common/contracts/proto/`.

Он определяет authoring/generation/reconciliation process. Конкретная business semantics полей и сообщений должна находиться в governing API/business/platform spec.

## Current bootstrap state

Known repository state:

```text
Python/common authoring path:
common/contracts/proto/curve_data_service.proto

Rust build input:
backend/calc-service/proto/curve_data_service.proto
```

Rust generation is driven through `backend/calc-service/build.rs`.

Python generated stubs are produced under:

```text
backend/core-service/src/proto/
```

Rust generated sources are produced under:

```text
backend/calc-service/src/generated/
```

`AMB-004` tracks the unresolved duplicate Proto authoring-source situation.

Until `AMB-004` is resolved, do not assume the two Proto files are interchangeable merely because they currently match.

## When this workflow is mandatory

Activate when:

- a `.proto` declaration changes;
- a shared message/service/field shape changes;
- field optionality/presence/default representation changes;
- service method signature changes;
- wire-compatible/wire-incompatible behavior changes;
- generated Python or Rust Proto consumers must be regenerated;
- a task touches either Proto copy in a way that could affect the shared contract.

## Generated-file rule

Generated sources are read-only.

Never hand-edit:

```text
backend/core-service/src/proto/**
backend/calc-service/src/generated/**
```

Change the correct authoring source and regenerate.

If the canonical authoring source cannot be determined because of `AMB-004`, do not resolve the ambiguity by convenience.

## Approval policy

A purely mechanical regeneration from an unchanged approved authoring source may be:

```text
workflow_allowed
```

A transport shape change that has no business-semantic impact may still require boundary owner approval according to registry policy.

If the change affects business meaning, nullable semantics, fallback/default behavior, calculation meaning, or consumer-visible semantics:

```text
SPEC-WF-SHARED-PROTO
+
SPEC-WF-HIGH-RISK-SEMANTICS
+
approval_policy: human_required
```

The strictest applicable policy wins.

## Pre-change analysis

Before editing, record:

```text
affected Proto message/service/field
current authoring source(s)
published contract
Python generated consumer
Rust generated consumer
affected producer(s)
affected consumer(s)
wire compatibility expectation
semantic impact classification
approval_policy
AMB-004 relevance
```

## Duplicate authoring-source gate (`AMB-004`)

While both copies exist:

```text
common/contracts/proto/curve_data_service.proto
backend/calc-service/proto/curve_data_service.proto
```

the agent must:

1. identify which file each generator/build actually consumes;
2. compare affected declarations before modification;
3. avoid declaring one copy canonical unless authority is already resolved;
4. keep the required copies reconciled only through an explicit approved procedure;
5. report any mismatch as `DRIFT` or `SEMANTIC_CONFLICT` depending on meaning.

If a task requires selecting/removing the duplicate source, that is an authority/architecture decision and remains blocked until `AMB-004` is resolved.

## Contract change procedure

### 1. Resolve semantic authority

Before changing a field/message/service whose meaning changes:

- resolve governing active spec;
- if no active spec exists, reconcile registered evidence;
- apply `SPEC-WF-HIGH-RISK-SEMANTICS` where business meaning changes.

### 2. Determine compatibility

Classify the intended change:

```text
wire-compatible
wire-compatible but semantic-changing
wire-incompatible
unknown
```

`unknown` is blocking for implementation of a shared public boundary.

### 3. Update authoring declaration

Edit only the registered authoring source(s) required by the current bootstrap state.

Do not edit generated Rust/Python sources.

### 4. Reconcile duplicate Proto copies

While `AMB-004` remains open, ensure the Rust build input and common published declaration do not silently diverge.

If repository policy requires both files to remain synchronized, synchronize them explicitly as part of the workflow and record that both were changed.

### 5. Regenerate Python consumer

Use the registered Python generation pipeline for:

```text
backend/core-service/src/proto/**
```

Do not substitute hand-written models/stubs if generation fails.

### 6. Regenerate Rust consumer

Use the registered Rust build/generation pipeline (`build.rs`/cargo path) for:

```text
backend/calc-service/src/generated/**
```

Do not hand-edit generated Rust code.

### 7. Verify both sides

Verify:

- Proto compilation/generation succeeds;
- Python serialization/deserialization where applicable;
- Rust serialization/deserialization where applicable;
- service/client compilation;
- integration path affected by the changed message/method;
- semantic parity if business meaning is shared.

## Nullable / optional / default handling

Presence semantics require explicit treatment.

Do not assume:

```text
Python None
==
Rust required scalar/String
```

or:

```text
missing
==
empty
==
default value
```

If such behavior affects business meaning:

```text
approval_policy: human_required
```

and the exact semantics belong in the governing spec.

The workflow only enforces that both sides implement the approved contract consistently.

## Compatibility rules

Before changing field numbering, message shape, service signatures, optionality, or defaults, determine whether the change preserves supported clients/servers.

Do not:

- reuse removed Proto field numbers;
- silently change field meaning while keeping the same wire shape;
- treat successful code generation as proof of semantic compatibility;
- remove compatibility behavior without explicit authority when existing consumers may depend on it.

Exact supported-version policy should come from the governing boundary spec.

## Drift handling

### Generated consumer differs from source

```text
DRIFT
-> identify authoring source
-> regenerate
-> verify
```

### Two authoring Proto copies differ mechanically but intended meaning is clear

Treat as `DRIFT` only if authority and intended source are already resolved.

### Two Proto copies imply different semantics or authority is unclear

```text
SEMANTIC_CONFLICT
or
UNRESOLVED_AUTHORITY
```

Do not pick one side automatically.

## Verification expectations

At minimum, where applicable:

### Rust

From `backend/calc-service/`:

```bash
cargo test --all-features
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
```

### Python

Use the applicable core-service router/test commands for affected integration/unit tests.

### Boundary

Verify the affected RPC/service path end-to-end when practical and required by the change.

For nullable/presence changes, include explicit cases for:

```text
present value
missing/unset
empty representation
default representation
```

as applicable to the approved contract.

## Definition of done

A shared Proto change is complete only when:

- semantic authority was resolved where meaning changed;
- required approval was obtained;
- compatibility classification is known;
- correct authoring source(s) were changed;
- duplicate Proto copies are reconciled according to current `AMB-004` rules;
- Python generated consumers are regenerated;
- Rust generated consumers are regenerated;
- both sides compile/test as required;
- nullable/presence behavior is verified where affected;
- affected integration paths are checked;
- no manual generated-file edits remain;
- unresolved `AMB-004` implications are explicitly recorded.
