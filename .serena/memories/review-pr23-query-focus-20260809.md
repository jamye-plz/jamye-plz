# PR #23 review: query navigation focus preservation (2026-08-09)

## Scope

- Unresolved review thread: `PRRT_kwDOS75RC86XnD80`
- Source: `frontend/src/routes/+layout.svelte`
- Regression test: `frontend/tests/layout-focus.test.mjs`

## Finding

- Severity: MEDIUM (review P2), fixed.
- `afterNavigate` reset focus to `#main-content` after every navigation, overriding SvelteKit `keepFocus: true` when the group date dial changed only the `?date=` query.
- Keyboard users could lose focus after one arrow-key date change and could not continue stepping through dates without tabbing back.

## Remediation

- Inspect `from` and `to` in `afterNavigate`.
- Preserve focus when route ID and pathname are unchanged, covering query-only and hash-only navigation.
- Keep the existing main/heading focus reset for initial entry and genuine page changes.
- Added a source-contract regression test that requires the same-page guard to run before `focus()`.

## Verification

- `bun run test`: 4 passed.
- `bun run check`: 0 errors, 0 warnings.
- `bun run lint`: passed.
- `bun run build`: passed with the existing large-chunk and unmatched-PWA-glob warnings.
- `git diff --check`: passed.
- Independent QA review reproduced the issue and agreed with the remediation.

## Quality review

- Security: no new injection, authentication, authorization, or sensitive-data path.
- Performance: constant-time route/path comparison only.
- Accessibility: fixes keyboard focus continuity while retaining route-change announcement behavior.
- Code quality: typed SvelteKit navigation fields; focused regression coverage.
- Diff-introduced CRITICAL/HIGH findings: none.

## Residual dependency audit

- Full `bun audit`: 12 high, 3 moderate, 2 low findings in the existing dependency graph.
- `bun audit --production`: DOMPurify reports 1 moderate and 1 low finding.
- Dependency manifests and lockfile were not changed by this fix; remediation remains separate scope.
