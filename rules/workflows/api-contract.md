---
id: SPEC-WF-API-CONTRACT
status: active
authority: normative-workflow
applies_to:
  - backend/core-service/src/api/**
  - common/contracts/openapi/**
  - frontend/web/src/shared/api/generated/**
  - frontend/web/**
approval_policy: human_required
owners: []
approvers: []
last_reviewed: 2026-08-18
contract_ids:
  - HTTP-OPENAPI-FRONTEND
---

# Workflow: public HTTP API contract

## Purpose

This workflow governs the full contract chain:

```text
FastAPI authoring source
-> published OpenAPI
-> generated TypeScript client/types
-> frontend consumer
```

A public API contract change is not complete when backend code is complete.

## Critical closure rule

**Do not use the initial changed-path set as the only trigger for downstream work.**

For:

```text
change_type = public_http_api_shape_change
```

the following obligations become active immediately:

```text
OPENAPI-EXPORT
FRONTEND-GEN-API
frontend consumer impact classification
```

even if these paths are not yet present in the diff:

```text
common/contracts/openapi/openapi.json
frontend/web/src/shared/api/generated/**
```

This is contract reconciliation, not ordinary path routing.

If only an API authoring-source path is known and semantic impact is not yet classified:

```text
backend/core-service/src/api/**
```

then at minimum:

```text
OPENAPI-EXPORT
```

is mandatory. If the resulting OpenAPI changes, `FRONTEND-GEN-API` becomes mandatory.

## Contract registry

Resolve:

```text
HTTP-OPENAPI-FRONTEND
```

from:

```text
rules/policy.yaml
```

The workflow must execute all mandatory reconciliation edges selected by that contract.

## Approval

Public HTTP shape / consumer-visible semantics:

```text
human_required
```

Approval covers the intended method/path/request/response/compatibility decision.
After approval, regeneration and reconciliation are mechanical continuation.

## Procedure

### 1. Resolve applicability

Load:

```text
AGENTS.md
backend/core-service/AGENTS.md
rules/README.md
topic: http-api-contract
workflow: SPEC-WF-API-CONTRACT
contract: HTTP-OPENAPI-FRONTEND
```

Compute:

```text
actual_changed_paths
required_reconciliation_targets
```

### 2. Implement FastAPI authoring source

Change FastAPI source/models. Do not edit generated/published artifacts manually.

### 3. Backend targeted verification

Run only registered/proven backend verification commands.

### 4. Export OpenAPI — mandatory for API authoring-source changes

Run verification ID:

```text
OPENAPI-EXPORT
```

Exact registered invocation:

```bash
cd infra/scripts && bash export_openapi.sh 2>&1 | tail -5
```

Do not rewrite cwd, arguments, redirects, or pipes.

Inspect:

```text
common/contracts/openapi/openapi.json
```

and classify:

```text
changed
unchanged
unexpected_drift
```

### 5. Frontend generation

`FRONTEND-GEN-API` is mandatory when either:

```text
change_type = public_http_api_shape_change
```

or:

```text
published OpenAPI changed
```

Run verification ID:

```text
FRONTEND-GEN-API
```

Exact invocation:

```bash
cd frontend/web && npm run gen-api
```

Do not wait for `frontend/web/src/shared/api/generated/**` to appear in the diff
before deciding whether generation is required.

Generated files are read-only by hand.

### 6. Reroute actual changed paths

After OpenAPI generation and frontend generation, rerun normal path routing using
the paths that actually changed.

This second routing pass is still required, but it is **not** what creates the
generation obligation.

### 7. Frontend consumer reconciliation

Load:

```text
frontend/web/AGENTS.md
```

Classify:

```text
frontend consumer impact: affected
```

or:

```text
frontend consumer impact: none
reason: ...
```

Use generated functions/types where affected.

### 8. Frontend build

If generated frontend API or frontend consumer files changed, run:

```text
FRONTEND-BUILD
```

Exact invocation:

```bash
cd frontend/web && npm run build
```

## Verification command rule

Use only commands from:

```text
rules/policy.yaml
```

Do not infer tools such as `.venv/bin/ruff`.

## Compatibility

Classify:

```text
additive_compatible
behaviorally_compatible
breaking
unknown
```

`unknown` blocks closeout.

## Definition of done

A public API contract change is complete only when:

- required human approval is recorded;
- FastAPI authoring source is updated;
- targeted backend verification is performed;
- `OPENAPI-EXPORT` is executed;
- OpenAPI diff is classified;
- `FRONTEND-GEN-API` is executed when public API shape changed or OpenAPI changed;
- generated TypeScript is not hand-edited;
- actual changed paths are rerouted after generation;
- frontend consumer impact is classified;
- `FRONTEND-BUILD` is executed when generated/consumer frontend files changed;
- compatibility is classified;
- all mandatory `HTTP-OPENAPI-FRONTEND` reconciliation edges are closed.
