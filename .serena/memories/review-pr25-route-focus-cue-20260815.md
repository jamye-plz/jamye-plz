# PR #25 review: route-focus cue preservation (2026-08-15)

## Scope

- PR #25 `fix/route-focus-outline`
- Resolved thread: `PRRT_kwDOS75RC86ZetM4`
- New unresolved thread reviewed: `PRRT_kwDOS75RC86Ze3KN`
- Files reviewed: `frontend/src/app.css`, `frontend/src/routes/+layout.svelte`, `frontend/tests/layout-focus.test.mjs`, and the automatic invite redirect in `frontend/src/routes/invite/[code]/+page.svelte`

## Findings

### MEDIUM: blanket focus suppression

- The original `#main-content:focus-visible { outline: none; }` removed the only visible cue for keyboard route and skip-link focus.
- Remediated by scoping suppression to `#main-content[data-route-focus]:focus-visible`.

### MEDIUM: unknown modality treated as pointer input

- The first remediation initialized `lastInteractionWasKeyboard` to `false`, so initial page load and automatic redirects with no observed input were incorrectly classified as pointer-triggered.
- The new review comment is valid and reproducible from the negative boolean condition.

## Final remediation

- Replace the ambiguous boolean with `'keyboard' | 'pointer' | null`; `null` represents unknown or unobserved input.
- Set the pending modality only from capture-phase `keydown` or `pointerdown`.
- Capture and reset the pending modality at the start of every `afterNavigate` callback, including query-only early returns.
- Add `data-route-focus` only when the consumed modality equals `'pointer'`.
- Initial loads, automatic invite redirects, keyboard navigation, and skip-link focus retain the global 3px visible focus indicator.
- Remove the pointer-only suppression marker on blur.

## Verification

- `bun audit --production`: 1 moderate and 1 low pre-existing DOMPurify advisory; no dependency change in this PR.
- `bun test`: 6 passed.
- `bun run check`: 0 errors, 0 warnings.
- `bun run lint`: passed.
- `bun run build`: passed with existing large-chunk and PWA glob warnings.
- `git diff --check`: passed.
- Local server: `GET /groups` returned 200 and Korean document language was rendered.
- Interactive browser verification remains unavailable because no browser backend is connected.

## Re-review

- Security: no new injection, authorization, sensitive-data, or dependency path.
- Performance: two constant-time global listeners with matching cleanup and one scalar state reset per navigation.
- Accessibility: only an explicitly observed pointer interaction can suppress the fallback main-landmark outline.
- Code quality: unknown state, pointer equality, per-navigation consumption, and early-return ordering have regression coverage.
- Diff-introduced CRITICAL/HIGH/MEDIUM findings after remediation: none.
- Verdict: PASS locally; GitHub reply, resolution, commit, and push remain pending.
