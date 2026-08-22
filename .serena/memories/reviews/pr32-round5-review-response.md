# PR #32 추가 리뷰 round 5 대응

## 범위
- PR: #32, branch `fix/websocket-auto-reconnect`
- 기준 HEAD: `4405fcfe018d82e7d578d8f81b7ad3e87b4752e6`
- 검토 대상: 미해결 추가 리뷰 스레드 2건

## 타당성 판정
1. `reconcileReconnectHistory`의 빈 `knownIds` 즉시 종료: HIGH, 타당함.
   - 실제 재연결에서 끊긴 동안 50개를 초과해 도착하면 첫 페이지 뒤의 `next_cursor`가 버려져 영구 누락될 수 있었음.
2. 동적 route 방 전환 때 이전 방 ID snapshot: HIGH, 타당함.
   - 컴포넌트 재사용 중 이전 방의 local messages가 새 socket open 시점에 남아 전체 history 순회와 일시적 혼합을 유발할 수 있었음.

## 수정
- 빈 기준점의 실제 재연결은 distinct cursor를 끝까지 순회한다.
- 최초 방 입장만 `stopAfterFirstPageWithoutKnownIds`로 첫 페이지에 제한한다.
- 첫 successful `joined` 여부를 방 lifecycle 로컬로 추적해 최초 입장과 물리 재연결을 구분한다.
- query seed effect 전에 room-key reset effect를 등록하고 `untrack`으로 route key 외 의존성을 차단한다.
- 방 전환 시 messages, pagination, initial visibility, read timer/throttle, connection UI, transcript buffer, history recovery barrier를 초기화한다.
- recovery 기준 ID를 `!pending && message.chatroom_id === roomId`로 제한한다.
- 방 전환 중 완료된 stale `loadOlder` 응답은 새 방 state/scroll을 변경하지 못한다.
- 기존 join-gap → `applyBufferedTranscripts`, 4001/1008 terminal 처리, 물리 재연결의 local state 보존은 유지한다.

## 검증
- 독립 QA 최초 판정: FAIL (두 건 HIGH)
- 독립 QA 수정 후 판정: PASS
- `node --test frontend/tests/chat-socket-reconnect.test.mjs`: 13/13 pass
- 대상 파일 ESLint: pass
- 대상 파일 Prettier check: pass
- `git diff --check`: pass
- 의존성/lockfile 변경 없음
- LOW: 방 전환 회귀 검증은 현재 Svelte mount 테스트가 아니라 source-structure assertion이다. 향후 컴포넌트 테스트 기반을 도입할 때 실제 props 전환 테스트로 보강 가능.

## 사용자 게이트
프로젝트 정책에 따라 Bun 기반 전체 `lint/check/build`는 실행하지 않았으며, push 전에 사용자에게 최신 diff 기준 재실행을 요청한다.
