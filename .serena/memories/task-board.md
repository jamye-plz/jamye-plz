# Task Board — ultrawork mobile-pwa-ux (oma-00mrpr6b3knk60qqb8)

Plan: `.agents/results/plan-oma-00mrpr6b3knk60qqb8.json` / Branch: **fix/mobile-pwa-ux (생성됨, from main)**
PLAN_GATE: PASSED (user confirm + DateDial 접근 **A: Embla** 선택). plan-approved/impl-plan-locked/datedial-approach emit·verify 완료.

| Task | Agent | Priority | Status |
|------|-------|----------|--------|
| 1 브랜치 생성 | orchestrator | P0 | DONE |
| 2 viewport meta interactive-widget | frontend-issue1 | P0 | DONE (check 8/0, build 0) |
| 3 ChatRoom visualViewport 키보드 핸들러 | frontend-issue1 | P0 | DONE (h-dvh + visualViewport, iOS26 guard) |
| 4 embla deps 설치 | frontend-issue2 | P0 | DONE (embla-carousel-svelte 8.6 + wheel-gestures 8.1) |
| 5 DateDial Embla 재구축 (계약 불변) | frontend-issue2 | P0 | DONE (select-event commit, 계약 불변, check 8/0 build 0) |
| 6 검증 check/build/에뮬 | qa+orchestrator | P0 | DONE (chrome-devtools 에뮬: 클릭/키보드/드래그 전부 정상) |
| 7 VERIFY | qa+orchestrator | P1 | DONE — GO (C0/H0, CRITICAL 1·MEDIUM 1 발견·수정) |
| 8 REFINE | orchestrator | P1 | DONE — 하니스/디버그훅 제거, eslint suppression prune |
| 9 SHIP | orchestrator+user | P1 | PENDING USER — 실기기 확인 + 최종 승인 대기 |

IMPL_GATE: PASSED. VERIFY_GATE: PASSED (GO). REFINE_GATE: PASSED (refine-outcome verified).
커밋: ea76e76 (header 키보드) + 9ea5e9e (DateDial Embla). 브랜치 fix/mobile-pwa-ux, push 미수행.
SHIP_GATE: 사용자 실기기(iOS PWA 키보드 header 고정 + 실손가락 드래그) 확인 후 승인 → merge/push.

주의: ChatRoom(이슈1)과 DateDial(이슈2)은 파일 분리 → IMPL 병렬 가능.
서브에이전트 예산 ~25-45 tool calls — 배치 작게, 파일당 1응답 규칙.
Baseline: svelte-check 8 pre-existing errors / build exit 0.
