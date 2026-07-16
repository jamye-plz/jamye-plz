# Task Board — ultrawork daisyUI migration (oma-00mrnfuw0trni9gnb8)

Plan: `.agents/results/plan-oma-00mrnfuw0trni9gnb8.json` / tracker `docs/planning/work/001-daisyui-migration.md`
Runtime handoff: Claude Code → Codex (`019f6af3-0936-7a20-8aa4-2850dddd33aa`)

| Task | Owner | Priority | Status | Dependencies | exposed_skill_set | exposure_fallback |
|---|---|---:|---|---|---|---|
| IMPL-A: 설치·컬러 토큰 | frontend | P0 | completed | none | oma-frontend, daisyui, daisyui-colors | false |
| IMPL-B: 프리미티브·구조·모달·아이콘 | frontend | P1 | completed | IMPL-A | oma-frontend, daisyui, daisyui-usage | false |
| IMPL-C: ChatRoom·PWA 컬러 | frontend | P1 | completed | IMPL-B | oma-frontend, daisyui, daisyui-colors | false |
| VERIFY: 정렬·안전·회귀 | qa | P1 | completed | IMPL-C | oma-qa, oma-frontend, daisyui | false |
| REFINE: 재사용·영향·정리 | debug | P1 | completed | VERIFY | oma-debug, oma-refactor, oma-frontend | false |
| SHIP 정적 QA | qa | P2 | completed | REFINE | oma-qa, oma-frontend, daisyui | false |
| SHIP 런타임 검증 | orchestrator | P2 | in_progress | SHIP 정적 QA | oma-qa, oma-frontend, daisyui | false |
| FIX-1: 그룹 목록 항목 full-width | orchestrator-inline | P1 | completed | SHIP 런타임 검증 finding | oma-frontend, daisyui, daisyui-usage | false |
| FIX-1 재검증·SHIP 재개 | qa | P1 | completed | FIX-1 | oma-qa, oma-frontend, daisyui | false |
| FIX-2: 내 채팅 Markdown 대비 | orchestrator-inline | P1 | completed | SHIP 런타임 검증 finding | oma-debug, oma-frontend, daisyui-colors | false |
| FIX-2 독립 재검증·SHIP 재개 | qa | P1 | completed | FIX-2 | oma-qa, daisyui | false |
| Tracker 종료·세션 종료 | orchestrator | P2 | blocked | SHIP 재검증 + 사용자 최종 승인 | oma-pm, oma-qa, oma-scm | false |

## SHIP 런타임 수용 기준

- 실제 채팅: 이전 메시지 페이징 후 스크롤 앵커 유지
- 낙관 전송이 서버 메시지로 한 번만 치환
- 한글 IME Enter가 중복 전송을 만들지 않음
- 읽음 처리/안읽음 표시가 기대대로 갱신
- 주요 화면의 light/dark 자동 전환 및 가독성
- 네이티브 dialog ESC/백드롭 닫기 후 상태 초기화
- 콘솔 CRITICAL/HIGH 오류 0
- 사용자 최종 승인 전에는 push·SHIP_GATE·session.ended를 수행하지 않음

## 증거

- `.agents/results/result-frontend-{a,b,c}-oma-00mrnfuw0trni9gnb8.md`
- `.agents/results/result-qa-oma-00mrnfuw0trni9gnb8.md`
- `.agents/results/result-debug-oma-00mrnfuw0trni9gnb8.md`
- `.agents/results/result-qa-ship-oma-00mrnfuw0trni9gnb8.md`
- `.agents/results/bugs/bug-20260716-chat-primary-contrast.md`
