# PR #32 round 3 review response (2026-08-22)

## Initial verdict

FAIL.

- HIGH — `frontend/src/lib/chat/chat-socket-lifecycle.ts`: a WebSocket attempt could remain CONNECTING indefinitely because no per-attempt deadline retired it; online, visibility, and manual recovery triggers intentionally left CONNECTING sockets alone.
- MEDIUM — `frontend/src/lib/components/ChatRoom.svelte`: reconnect history recovery scrolled newly recovered messages into a visible bottom-anchored room but did not advance the read watermark.

## Remediation

- Added a 10-second per-attempt connection deadline. Expiry uses the existing `retire -> exponential backoff` path.
- The deadline is cleared on transport open, error handoff, retirement, terminal 4001 close, and disposal. The callback validates both its timer handle and current socket so stale attempts cannot retire replacements.
- Join-gap merge detects genuinely new recovered messages. When the reader was bottom-anchored, it waits for Svelte `tick`, revalidates that the lifecycle/socket is current, scrolls, and calls the existing throttled `tryMarkRead` only while visible.
- Regression coverage verifies stalled CONNECTING expiry, open clearing the deadline, normal backoff reuse, and the guarded read-after-scroll ordering.

## QA evidence

- TDD RED: focused Node suite failed before production implementation.
- GREEN: `node --test frontend/tests/chat-socket-reconnect.test.mjs` passed 8/8.
- Direct Prettier check passed for all three changed frontend files.
- `git diff --check` passed.
- Serena diagnostics: lifecycle and test files reported no issues. Svelte diagnostics could not load the local adapter/module graph because the current environment lacks `@sveltejs/adapter-static`; the repository owner runs the full Bun check.
- Dependency files are unchanged. Bandit and Lighthouse are unavailable; npm audit was not run because this frontend is Bun-only and the owner explicitly runs Bun commands.
- Independent QA: initial FAIL, remediation WARNING for a stale deferred callback, final PASS after adding a current-lifecycle guard. No residual CRITICAL/HIGH/MEDIUM finding in the reviewed diff.
- Full browser/runtime and Bun gates were not run by Codex under the repository owner's command boundary.
