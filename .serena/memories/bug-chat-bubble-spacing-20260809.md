# 채팅 말풍선 간격 회귀 수정 (2026-08-09)

- 디자인 계약: `DESIGN.md`의 같은 발신자 연속 메시지 4px, 발신자 또는 표시 분 변경 12px.
- 원인: `ChatRoom.svelte` 목록의 `space-y-3`(12px)과 daisyUI `.chat`의 `padding-block: .25rem`(위아래 4px)이 중첩됨. 같은 그룹의 `-mt-2`(-8px)까지 포함하면 실제값이 12px/20px.
- 최소 수정: 목록의 `space-y-3`은 유지하고 수신·발신 `.chat` 행에 `py-0`을 적용해 daisyUI의 외부 블록 패딩만 제거. 기존 `showHeader` 및 양방향 `-mt-2`를 유지해 결과는 4px/12px이며 날짜 구분선, 시스템 알림, 로딩 행의 12px 목록 리듬도 보존됨.
- 회귀 테스트: `frontend/tests/chat-room-spacing.test.mjs`가 설치된 daisyUI chat CSS의 실제 패딩, 소스의 `py-0`, 목록 토큰을 읽어 두 최종 간격을 검증함. 변경 전 실패(12 !== 4), 변경 후 통과. `frontend/package.json`의 `test` 스크립트로 실행 가능.
- 검증: targeted Prettier/ESLint, Node test 1 pass, `bun run check` 0 errors/0 warnings, `bun run build` 성공, 유사 패턴 추가 대상 없음.
- 상세 보고서: `.agents/results/bugs/bug-20260809-chat-bubble-spacing.md`.