# AGENTS.md — core-service router

## 1. Scope

This file applies to:

```text
backend/core-service/**
```

Use it together with:

- root [`AGENTS.md`](../../AGENTS.md);
- repository rules [`rules/README.md`](../../rules/README.md);
- applicable canonical workflows under [`rules/workflows/`](../../rules/workflows/);
- current behavioral specs under `openspec/specs/**` resolved through repository policy;
- [`docs/design/adr/active/platform/core-service-architecture-style-guide.md`](../../docs/design/adr/active/platform/core-service-architecture-style-guide.md) when architecture/application-layer conventions are affected.

This file is a **service-level router and operational guide**. It does not define current business/calculation semantics.

If this file conflicts with root invariants or the canonical routing model, classify it as `BROKEN_ROUTING` and stop semantic editing until the conflict is resolved.

## 2. Core-service responsibilities

`backend/core-service/` is responsible for:

- HTTP API and application orchestration;
- All server-side services and workflows.
- authoring sources that feed published/generated contracts where registered in `rules/policy.yaml`.

These responsibilities identify routing boundaries. They do not grant authority to change business semantics.

## 3. Scoped routing

Resolve additional topics/workflows from the actual changed paths.

Example:

| Changed scope | Additional routing |
|---|---|
| `src/api/**` | API topic; `SPEC-WF-API-CONTRACT` when public shape or consumer-visible semantics change; architecture style guide for structural API changes |
| contract-producing models/commands | JSON Schema/OpenAPI workflow when published contract shape changes |
| structural application/service refactor | Core-service architecture style guide |

Path location alone does **not** prove that a change is semantic.

```text
sensitive path changed
-> inspect semantic impact
```

Then:

```text
behavior preserved
-> resolve normal/workflow-gated obligations
```

or:

```text
business/calculation behavior changed
-> SPEC-WF-HIGH-RISK-SEMANTICS
-> approval_policy >= human_required
```

The strictest policy resolved by root/catalog always wins.

## 4. Architecture and application-layer rules

Detailed coding/architecture conventions live in:

TODO

Do not duplicate detailed style-guide rules here.

## 5. High-risk semantic routing

For core-service, behavior-affecting changes in these areas require:

[`SPEC-WF-HIGH-RISK-SEMANTICS`](../../rules/workflows/high-risk-semantics.md)

and at least:

```text
approval_policy: human_required
```

when intended semantics change:

- TODO - add areas.

Before human approval, analysis/proposal work is allowed; choosing or implementing new business/calculation semantics is not.

After approval, the agent may execute the approved mechanical implementation and verification until a new semantic ambiguity appears.

## 10. Python documentation conventions

Detailed documentation/comment conventions live in the core-service architecture style guide.

Enforcement summary:

- all public classes and public methods in the business/application layer MUST have meaningful docstrings;
- private (`_`) methods are exempt unless non-obvious behavior warrants documentation;
- boilerplate docstrings that only repeat the symbol name are insufficient;
- comments/docstrings explain local implementation intent and do not replace governing specs;
- non-obvious orchestration, mapping, fallback, dataframe/array assumptions, and exception handling should be documented according to the style guide;
- BlackFormatter rules (PEP) are required.

backend/core-service/
```

unless a command explicitly states otherwise.

Environment:

```text
virtualenv: .venv/
pytest: .venv/bin/pytest
config: pytest.ini
```

Do not rely on system `python`/`python3` having repository test dependencies installed.

### Unit suite

```bash
PYTHONPATH=. .venv/bin/pytest tests/unit/ -v
```

### Specific test file

```bash
PYTHONPATH=. .venv/bin/pytest tests/unit/test_reporting/test_hive_parquet_writer.py -v
```

### Specific test

```bash
PYTHONPATH=. .venv/bin/pytest tests/unit/test_reporting/test_hive_parquet_writer.py::TestBuildPartitionPath::test_basic_path_construction -v
```

### From repository root

```bash
PYTHONPATH=backend/core-service \
  backend/core-service/.venv/bin/pytest \
  backend/core-service/tests/unit/test_reporting/test_hive_parquet_writer.py -v
```

### Coverage

From `backend/core-service/`:

```bash
PYTHONPATH=. .venv/bin/pytest tests/unit/ -v --cov
```

High-risk semantic changes require targeted regression evidence defined by the governing spec and `SPEC-WF-HIGH-RISK-SEMANTICS`.

Excel-affecting changes require the verification defined by `SPEC-WF-EXCEL-COMPATIBILITY`.

The existence of a test is not proof of successful verification; record executed commands/results during closeout.


### Verification command source

Concrete verification invocations must come from `rules/policy.yaml`
or be proven from current repository evidence before execution.

Rules:

- Do not infer `.venv/bin/ruff` or any other `.venv/bin/<tool>` from the existence of `.venv`.
- Do not add lint/typecheck commands just because the corresponding tool is common in Python projects.
- Preserve registered invocation text exactly, including cwd, arguments, redirects, and pipes.
- If a required executable/command is not registered or proven available, record `MISSING_EVIDENCE`; do not guess a substitute.


## 12. Core-service closeout additions

In addition to root closeout requirements, record:

- changed core-service scopes;
- sensitive areas inspected for semantic impact;
- behavior-preserving vs semantic classification;
- resolved `approval_policy`;
- applicable valuation/filter/curve/Excel/API/Proto topics;
- workflows actually applied;
- Python↔Rust parity obligations;
- authoring contract sources changed;
- generated/published artifacts regenerated;
- targeted regression tests executed;
- broader checks executed or deliberately skipped;
- unresolved `AMB-*` gates or evidence gaps.

Do not mark high-risk semantic work complete while required human approval, governing spec reconciliation, parity verification, contract regeneration, or required Excel compatibility evidence remains unresolved.

## 13. Portability

This router must remain usable in Cursor, ZooCode, and future agent environments.

Tool-specific rules may help load this router or constrain context, but they must not:

- contain the only copy of core-service business semantics;
- relax `approval_policy`;
- bypass contract workflows;
- make required governing evidence inaccessible.

Repository routing remains canonical.
