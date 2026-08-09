# PR #23 review: Bun-native test runner

## Scope

- Unresolved thread: `PRRT_kwDOS75RC86Xn9dA`
- File: `frontend/package.json:11`
- Difficulty: Simple, non-UI developer-workflow change.

## Finding

- **MEDIUM — Toolchain portability:** the test script used `node --test tests/*.test.mjs` even though `frontend/AGENTS.md` requires Bun and `packageManager` pins `bun@1.3.13`.
- Reproduction: with a PATH containing Bun but no Node, `bun run test` exited 127 because `node` was unavailable.
- Remediation: change the script to `"test": "bun test"`. Bun 1.3.13 supports the existing `node:test`, `node:assert/strict`, and `node:fs` imports, so test files do not need modification.

## QA result

- Security: no new dependency or runtime code; `bun audit --production` reports the pre-existing DOMPurify moderate and low advisories, unrelated to this change.
- Performance: no production runtime impact; the Bun runner completed 4 tests across 3 files in about 24 ms.
- Accessibility: not applicable because the change only selects the test runner.
- Code quality: aligns the script with the pinned package manager and removes an undeclared external executable dependency.
- Runtime UI verification skipped under the Simple/non-UI exception.

## Verification

- `bun run test`: 4 passed, 0 failed.
- Bun-only PATH `bun run test`: 4 passed, 0 failed.
- `bun run check`: 0 errors, 0 warnings.
- `bun run lint`: passed.
- `bun run build`: passed with existing large-chunk/PWA glob warnings.
- `git diff --check`: passed.
