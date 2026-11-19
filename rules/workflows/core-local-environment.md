---
id: SPEC-WF-CORE-LOCAL-ENVIRONMENT
status: active
authority: normative-workflow
applies_to:
  - backend/core-service/.venv/**
approval_policy: human_required
---

# Workflow: prepare the local core-service environment

## Purpose

Restore the repository-local Python environment required by registered backend
tests and OpenAPI publication without changing dependency versions or deployment.
Activate only with explicit approval to prepare this environment, not for every
backend change. The user approved this procedure and dependency installation for
the `fast-extraction-load-pages` continuation on 2026-11-19.

## Scope and safeguards

- Use `backend/core-service/.venv`, as required by the service router and exporter.
- Install the unchanged `requirements.txt` and `requirements-dev.txt` manifests.
- Do not install system packages, upgrade pip independently, change package pins,
  alter credentials, access databases, or rebuild/deploy containers.
- Do not delete, clear, overwrite, or recreate an existing environment. Inspect
  existing state and resolve ownership before reuse; a failed creation must not
  be retried by removing its partial output.
- Approved exception for `fast-extraction-load-pages` on 2026-11-19: the existing
  environment's activation and pytest launcher reference a former checkout.
  Preserve it intact with `CORE-ENV-PRESERVE-RELOCATED`, then create a new `.venv`
  using the observed local Python 3.12.3. The user explicitly approved this move
  and version. Never overwrite the backup or remove it as part of this task.
- The container image uses Python 3.13. This is evidence of the container version,
  not proof that any local interpreter can install the pinned dependencies.
  Report the actual local version. Missing tooling or installation incompatibility
  is `MISSING_EVIDENCE`; stop rather than selecting another interpreter or changing
  dependencies without further evidence and approval.
- Do not commit the environment or secrets. Preserve pre-existing working-tree
  changes and inspect the final diff.

## Registered procedure

Exact commands are in `rules/policy.yaml`; execute from the repository root:

1. Run `CORE-ENV-INSPECT` to report the local Python version and whether the
   environment path already exists (including a dangling symlink).
2. Only when the path is absent, run `CORE-ENV-CREATE`. If it exists, stop creation
   and inspect its configuration before any approved reuse. For the explicitly
   approved relocated-environment exception above, first run
   `CORE-ENV-PRESERVE-RELOCATED`, then `CORE-ENV-CREATE`.
3. Run `CORE-ENV-INSTALL` in the newly created or explicitly approved existing
   environment. Package downloads from the configured package index are allowed;
   do not invent a replacement index or credentials.
4. Resume the original registered checks: targeted backend pytest and the API
   contract workflow. Environment creation alone is not successful verification.
5. Record actual version, installation outcome, tests and unresolved blockers in
   the affected change's evidence. Keep failed attempts distinguishable from later
   successful verification.

The API contract workflow remains mandatory. Do not bypass publication or edit
generated contracts by hand when environment preparation fails.
