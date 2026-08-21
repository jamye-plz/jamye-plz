# PR #32 additional review round 4

## Scope
- `frontend/src/lib/chat/chat-socket-lifecycle.ts`
- `frontend/src/lib/components/ChatRoom.svelte`
- `frontend/tests/chat-socket-reconnect.test.mjs`
- `backend/app/main.py`
- `backend/tests/test_websocket_heartbeat.py`

## Initial findings
- HIGH: a transient `reconcileReconnectHistory` REST failure was swallowed, so a healthy physical socket never retried the missing join-gap history and later read receipts could advance beyond the gap.
- MEDIUM: WebSocket policy close 1008 was treated as reconnectable. In addition, Starlette converts a close before `accept()` into an HTTP 403 denial, so the browser could not reliably observe 1008.

## Remediation
- Added a single-flight reconnect-history recovery controller using the shared 1s exponential backoff, 30s cap, and jitter. It preserves the original pre-join known-id boundary and existing `mergeJoinGap` path, retries on the same current socket, resets after success, and cancels timers and late in-flight application on replacement/disposal.
- Held read receipts behind the recovery-success barrier so a later live message cannot mark a still-missing gap as read.
- Made 1008 a terminal authentication close distinct from 4001 eviction. Terminal cleanup clears retry/connect/heartbeat/manual timers and online/offline/visibility listeners, clears client query state, and hard-redirects to `/login`.
- Accepted the WebSocket before cookie validation so missing/expired authentication is sent as an observable 1008 close without exposing room subscription or application processing.

## Verification
- Independent QA re-review: PASS; no remaining CRITICAL/HIGH/MEDIUM findings.
- `node --test frontend/tests/chat-socket-reconnect.test.mjs`: 11 passed.
- focused ESLint and Prettier on changed frontend files: passed.
- `backend/.venv/bin/pytest backend/tests -q`: 186 passed.
- Ruff check and format-check on backend: passed.
- `npx --no-install pyright --project backend/pyrightconfig.json`: 0 errors.
- `git diff --check`: passed.
- Full user-owned Bun check/lint/build gates were not run in this review round.

## Residual low-risk recommendation
- A dedicated history-controller test for repeated failures reaching the 30s cap and duplicate `start()` calls would strengthen regression specificity; shared backoff behavior and single-flight guards are already covered in implementation and adjacent lifecycle tests.