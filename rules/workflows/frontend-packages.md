# Workflow: frontend library packages

## Scope and approval

The user approved independent UI Kit and App Shell packaging on 2026-11-21.
Keep existing package names, public subpaths, peer ranges, CSS behavior and
application/domain boundaries. No registry publication, repository move, new
runtime dependencies or business/auth changes are included.

## Authoring and artifacts

Sources are `frontend/ui-kit/src/**`, `frontend/app-shell/src/**`, their package
manifests and `frontend/scripts/**`. Build each package with the installed
TypeScript compiler, emitting ESM, declarations and copied CSS into its own
`dist/`. Dependencies stay external. Build UI Kit before App Shell. Generated
outputs and tarballs are read-only by hand and ignored by Git.

Preserve root shell bootstrap CSS imports and declare CSS side effects. Preserve
the current global CSS and external font loading; this is a full-page shell,
not a newly specified embeddable widget.

## Reconciliation and verification

1. Inspect `FRONTEND-PACKAGE-STATE`; preserve existing changes.
2. Reconcile manifest metadata with `FRONTEND-LOCK-RECONCILE`. Do not install tools.
3. Run `FRONTEND-PACKAGES-BUILD` and `FRONTEND-PACKAGES-VERIFY`.
4. The verifier packs both packages into a fresh temporary directory, installs
   their archive payloads without workspace links, and makes existing installed
   third-party dependencies available as symlinks (no network or dependency
   installation). Verify every public entry, declarations with strict library
   checking, and a Vite consumer production build outside the repository.
   Third-party declaration diagnostics are printed separately, not suppressed;
   package-owned and consumer diagnostics block verification. The existing host
   uses `skipLibCheck`, so a fully clean third-party type graph is not claimed.
   This proves archive isolation, not a fresh registry dependency resolution.
5. Run `FRONTEND-BUILD` against built library exports and
   `FRONTEND-PACKAGES-PACK` to produce transferable archives.
6. Run `FRONTEND-PACKAGE-DIFF` and document actual evidence and limitations.

If installed prerequisites are unavailable, report `MISSING_EVIDENCE`; do not
substitute tools or install dependencies. HTTP contracts are unchanged; API
regeneration is not required solely for library packaging. Browser interaction,
registry publication and a clean online consumer installation are not claimed
by these checks.
