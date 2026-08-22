# PR #32 추가 리뷰 round 6 대응

## 범위
- PR: #32, branch `fix/websocket-auto-reconnect`
- 기준 HEAD: `be93458fd37fc02d894a12ca9b5a8b6e1d0c8259`
- 새 미해결 스레드: `PRRT_kwDOS75RC86bO7UG`
- 대상: 초기 messages query와 첫 WebSocket joined 사이의 recovery boundary 레이스

## 타당성
- 판정: HIGH, 타당함.
- 첫 query가 local messages에 적용되기 전에 joined 되면 captured IDs가 비고, 이전 first-page cap 때문에 50개 초과 join gap이 영구 누락될 수 있었다.
- query seed가 local messages를 교체하면 그 사이의 WS/recovery 결과도 사라질 수 있었다.
- 첫 수정안의 joined 후 새 refetch도 성공-empty 초기 snapshot을 최신 50개 false boundary로 바꿀 수 있어 독립 QA에서 거부했고, 새 fetch를 전혀 시작하지 않는 설계로 보완했다.

## 최종 수정
- unsafe `stopAfterFirstPageWithoutKnownIds` 옵션을 제거했다.
- 첫 join은 captured known IDs가 있으면 즉시 사용한다.
- exact query-key cached page를 우선 사용하며 `items: []`도 유효한 pre-subscription snapshot으로 취급한다.
- cache가 없을 때만 이미 실행 중인 exact Query의 공개 `promise`를 기다린다. 새 refetch는 시작하지 않는다.
- 기존 query 실패/부재는 empty boundary로 fallback해 distinct cursor 끝까지 복구한다.
- await 뒤 socket과 room key를 다시 검증한다.
- query seed와 recovery가 공통 `mergeChatMessageRecords`를 사용해 ID de-dup, canonical client_msg_id 치환, WS/optimistic 보존을 수행한다.
- seed effect는 current room을 필터하고 transcript/current messages/read throttle 접근을 `untrack`해 query page 외 반응 의존성을 만들지 않는다.
- `refetchOnReconnect: false`, read barrier, room-switch reset, stale loadOlder guard, 4001/1008 terminal 처리, join 재전송, transcript buffer 4경로를 유지했다.

## QA
- 독립 초기 검토: FAIL, HIGH 재현
- 첫 수정 후 검토: FAIL, success-empty 후 post-subscription refetch false boundary 재현
- 최종 검토: PASS
- 대상 Prettier: pass
- 대상 ESLint: pass
- `node --test frontend/tests/chat-socket-reconnect.test.mjs`: 17/17 pass
- `git diff --check`: pass
- 의존성/lockfile 변경 없음
- 수동 보안 검토: 변경 경로에 injection/secret 추가 없음. 기존 `{@html}` 경로는 `renderMarkdown`의 DOMPurify allowlist로 정제됨.
- 접근성: 렌더링 markup 변경 없음.
- LOW: boundary helper와 pagination은 실행 테스트하지만 실제 Svelte scheduler에서 query 완료, joined, recovery를 한 번에 구동하는 component integration test는 아직 없다.

## 사용자 게이트
프로젝트 정책에 따라 Bun 전체 prettier/eslint/check/build는 사용자가 최신 diff에서 실행한다.
