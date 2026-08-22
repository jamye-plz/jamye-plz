# PR #32 additional review response (2026-08-21)

Initial verdict: FAIL. Three new unresolved review findings were valid:
- HIGH: reconnect recovery could fetch history before the server had completed room subscription.
- MEDIUM: TCP open reset reconnect backoff before the socket proved application-ready.
- HIGH: a rejected reconnect join left the socket open and the UI falsely connected.

Remediation:
- The server sends a typed `joined` frame only after membership validation and `ws_hub.join`.
- The client remains `connecting` on TCP open and calls a shared stable transition only on `joined` or `pong`.
- `ChatRoom` captures known message IDs before sending join, then begins the existing paginated join-gap reconciliation from `onReady`.
- Join authorization/not-found `AppError` closes with terminal code 4001, reusing existing cache cleanup, navigation, and reconnect suppression.
- Backend tests cover ack ordering and terminal rejected joins; frontend tests cover readiness gating and backoff growth/reset.

Verification performed by Codex:
- `node --test frontend/tests/chat-socket-reconnect.test.mjs`: 7 passed.
- Python AST parsing for `backend/app/main.py` and `backend/tests/test_websocket_heartbeat.py`: passed.
- `git diff --check`: passed.
- Independent QA remediation review: PASS, no remaining CRITICAL/HIGH/MEDIUM findings.

The full Bun and uv gates were intentionally not run by Codex because the repository owner requested to run those commands personally.
