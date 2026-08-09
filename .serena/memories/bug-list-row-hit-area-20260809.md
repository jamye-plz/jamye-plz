# daisyUI list-row 전폭 선택 영역 수정 (2026-08-09)

- 증상: 데스크톱 그룹 목록에서 hover/click/focus 영역이 행 전체가 아니라 그룹 이름과 멤버 수의 콘텐츠 너비까지만 표시됨.
- 원인: daisyUI `.list-row` 기본 grid가 `minmax(0, auto) 1fr`이고 단일 버튼이 첫 auto 열에 놓여, 버튼의 `w-full`이 행이 아닌 auto 열만 채움.
- 디자인 계약: `DESIGN.md` Lists는 그룹/알림을 scan-oriented row로 사용하고 64px 최소 높이, 12px 16px 패딩, 행 전체 hover surface를 요구.
- 수정: `frontend/src/routes/groups/+page.svelte`와 `frontend/src/routes/notifications/+page.svelte`의 loading/interactive row 첫 자식에 공식 `list-col-grow` modifier 추가. daisyUI `:has(.list-col-grow:first-child)`가 열을 `1fr`로 바꿈.
- 회귀 테스트: `frontend/tests/list-row-width.test.mjs`가 두 페이지의 loading+interactive 행과 설치된 daisyUI CSS 계약을 검증. 변경 전 실패, 변경 후 통과.
- 유사 패턴: notifications 동일 오용을 함께 수정. invite 멤버 list-row는 비대화형 flex라 해당 없음.
- 검증: `bun run lint`, `bun run test`(2 pass), `bun run check`(0 errors/0 warnings), `bun run build` 성공.
- 상세 보고서: `.agents/results/bugs/bug-20260809-list-row-hit-area.md`.