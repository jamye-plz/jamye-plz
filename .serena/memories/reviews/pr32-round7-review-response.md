# PR #32 추가 리뷰 round 7 대응

## 범위
- 기준 HEAD: `5f9ca78451252b65d34da7df637fe2e054404711`
- 스레드: `PRRT_kwDOS75RC86bQDVI`
- 코멘트: initial messages query 실패 뒤 recovery가 성공해도 `initialReady`가 false로 남아 recovered messages가 `opacity-0`인 문제

## 판정
- MEDIUM, 타당함.
- `initialReady = true`가 query seed의 rAF에만 있었으므로 initial query가 실패하면 recovery가 messages를 병합해도 렌더 게이트가 영구 유지됐다.
- empty recovery 뒤 첫 WS message도 같은 hidden wrapper 조건에 걸릴 수 있었다.

## 수정
- guarded `revealInitialMessages` helper로 tick, first bottom scroll, rAF, second bottom scroll, reveal 순서를 통합했다.
- tick과 rAF 각 단계에서 supplied current-room/socket guard를 다시 확인한다.
- query seed는 helper를 사용하고 recovery가 이미 reveal한 경우 다시 스크롤하지 않는다.
- recovery success는 최초 렌더가 아직 닫혀 있을 때만 reveal/scroll을 기다린다.
- 이미 visible인 physical reconnect는 scroll을 강제하지 않고 DOM tick만 기다려 사용자의 읽던 위치를 보존한다.
- reveal/DOM settle 및 current guard 확인 뒤에 `historyRecoveryPending = false`와 read receipt 처리를 수행한다.
- room switch 시 pending reveal reference를 버리고 이전 async callback은 guard에서 false로 종료한다.

## 검증
- 독립 초기 검토: WARNING, MEDIUM
- 독립 최종 검토: PASS
- 대상 Prettier/ESLint: pass
- focused Node reconnect tests: 17/17 pass
- `git diff --check`: pass
- markup/dependency 변경 없음
- LOW: 실제 Svelte component와 requestAnimationFrame scheduler를 함께 구동하는 integration test는 아직 없고 source contract로 고정했다.

## 사용자 게이트
round7 변경 뒤 전체 Bun prettier/eslint/check/build를 다시 실행한 후 commit/push/reply/resolve한다.
