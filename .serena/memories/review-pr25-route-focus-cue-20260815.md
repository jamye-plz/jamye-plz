# PR #25 review: route-focus cue preservation (2026-08-15)

## Scope

- PR #25 `fix/route-focus-outline`
- Unresolved thread: `PRRT_kwDOS75RC86ZetM4`
- Files reviewed: `frontend/src/app.css`, `frontend/src/routes/+layout.svelte`, `frontend/tests/layout-focus.test.mjs`

## Finding

- Severity: MEDIUM (P2 accessibility), valid.
- The blanket `#main-content:focus-visible { outline: none; }` selector removed the only visible focus indicator when keyboard users activated the skip link or navigated to a route whose heading was outside `main`.
- This conflicted with the project's WCAG 2.2 AA focus-visible requirement.

## Remediation

- Track the most recent input modality using capture-phase `keydown` and `pointerdown` listeners.
- Add `data-route-focus` only when a pointer-triggered route navigation programmatically focuses the main landmark.
- Scope outline suppression to `#main-content[data-route-focus]:focus-visible`.
- Remove the temporary marker on blur.
- Keyboard-triggered route focus and skip-link focus retain the global 3px visible indicator.

## Verification

- `bun audit --production`: 1 moderate and 1 low pre-existing DOMPurify advisory; no dependency changes in this PR.
- `bun test`: 5 passed.
- `bun run check`: 0 errors, 0 warnings.
- `bun run lint`: passed.
- `bun run build`: passed with existing large-chunk and PWA glob warnings.
- `git diff --check`: passed.
- Local server: `GET /groups` returned 200 and Korean document language was rendered.
- Interactive browser verification was unavailable because no browser backend was connected; iOS PWA keyboard/skip-link behavior remains a manual check.

## Re-review

- Security: no new injection, auth, data, or dependency path.
- Performance: two constant-time global listeners with matching cleanup; no render loop or allocation growth.
- Accessibility: the reported focus-visible regression is fixed while preserving the original pointer-route visual cleanup.
- Code quality: input-modality state, temporary marker lifecycle, CSS scoping, and regression coverage are explicit.
- Diff-introduced CRITICAL/HIGH/MEDIUM findings after remediation: none.
- Verdict: PASS with manual-device verification remaining.
