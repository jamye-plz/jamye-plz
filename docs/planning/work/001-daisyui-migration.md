# daisyUI 전면 마이그레이션

> frontend 전체 UI를 daisyUI 5 컴포넌트 + 빌트인 테마(light/dark)로 완전 이관한다.

**Status**: Active
**Created**: 2026-07-16
**Owner**: human (phase별 승인) + frontend-engineer

## Goal

커스텀 컬러 토큰(`app.css` `@theme`)과 수작업 컴포넌트 스타일을 전부 daisyUI 5로 대체한다.
daisyUI가 제공하는 값이 기존 커스텀 값보다 우선한다 (빌트인 테마 채택, 커스텀 테마 없음).

## Context

- SvelteKit 2 + Svelte 5 + Tailwind CSS v4 (`@tailwindcss/vite`), Bun 패키지 매니저
- 레거시 컬러 유틸리티 약 250회 / 13개 파일 (핫스팟: `groups/+page` 41, `ChatRoom` 41, `invite` 37)
- 하드코딩 색: ChatRoom prose 링크색(`#67e8f9`/`#3b82f6`), 로그인 카카오(`#FEE500` — 유지 예외)
- PWA: manifest `theme_color/background_color: #09090b`, `app.html` meta theme-color `#18181b`
- 채택 컴포넌트(22종): chat, modal, navbar, btn, input, textarea, card, list, avatar, badge,
  loading, skeleton, alert, toast, divider, status, indicator, join, fieldset, validator, swap, menu
- 미채택: carousel/tab(DateDial은 커스텀 유지), dock(하단 내비 없음), drawer/dropdown/table 등(대응 화면 없음)

## Constraints

- daisyUI 5는 Tailwind v4 필수 — 충족. CSS-only라 Svelte와 무관하게 동작
- `bun`만 사용 (frontend/CLAUDE.md), 커밋은 Conventional Commits + phase당 분리
- DateDial의 스냅/rAF/햅틱 인터랙션 로직은 변경 금지 (색상만 시맨틱 토큰화)
- ChatRoom의 스크롤 앵커링·낙관적 전송·IME Enter 처리 로직 변경 금지 (마크업/클래스만 교체)
- 카카오 브랜드색 `#FEE500`은 테마 독립 유지 (daisyUI colors rule 11)
- elevation 방향 전환: daisyUI 다크 테마는 base-200/300이 base-100보다 **어두움** (현재 앱은 밝아지는 방향) — daisyUI 시맨틱을 그대로 수용

## Color Mapping (Phase 1 치환 기준표)

| 레거시 | daisyUI | 비고 |
|---|---|---|
| `bg-background` | `bg-base-100` | 페이지 배경 |
| `bg-surface` | `bg-base-200` | 카드/표면 |
| `bg-surface-elevated` | `bg-base-300` | 상승 표면 |
| `border-border` / `border-border-subtle` | `border-base-300` (base-300 표면 위에서는 `border-base-content/10`) | |
| `text-text-primary` | `text-base-content` | |
| `text-text-secondary` | `text-base-content/70` | opacity 컨벤션 |
| `text-text-muted` | `text-base-content/50` | |
| `text-text-inverse` | `text-primary-content` 등 문맥별 | |
| `accent` / `accent-hover` (63회) | `primary` (hover는 컴포넌트가 자동, 유틸은 `hover:bg-primary/90`) | |
| `bg-brand` CTA 2곳 | `btn btn-primary` | CTA primary 통일 결정 |
| `danger` | `error` | |
| `success` / `warning` | 동명 daisyUI 토큰 | |
| `text-white` (primary 버튼 위) | `text-primary-content` | |
| `bg-black/60` 오버레이 | `modal-backdrop` (Phase 4) | |
| prose 링크 `#67e8f9`/`#3b82f6` | daisyUI 변수 연동 | 양 모드 대응 |

## Tasks

| # | Task | Agent | Priority | Status | Dependencies |
|---|------|-------|----------|--------|--------------|
| **Phase 0 — 설치 & 기반** | | | | | |
| 1 | `bun add -D daisyui` 설치 | frontend | P0 | DONE | — |
| 2 | `app.css`에 `@plugin 'daisyui' { themes: light --default, dark --prefersdark; logs: false; }` 추가 | frontend | P0 | DONE | 1 |
| 3 | `bun run check` + `bun run build` 통과, 양 모드 스모크 (rootscrollgutter 시프트 확인) | qa | P0 | DONE | 2 |
| **Phase 1 — 컬러 토큰 전면 이관** | | | | | |
| 4 | `app.css` 재작성: 레거시 컬러 토큰 블록 삭제, body/focus/scrollbar/prose를 daisyUI 변수 기반으로 | frontend | P0 | DONE | 3 |
| 5 | 13개 파일 ~250개 클래스 매핑 치환 (위 기준표) | frontend | P0 | DONE | 4 |
| 6 | `prose-invert` 제거 + prose 색상을 daisyUI 변수로 (라이트/다크 양 모드) | frontend | P0 | DONE | 4 |
| 7 | 검증: 레거시 토큰 grep 0건, 양 모드 렌더 확인 | qa | P0 | DONE | 5, 6 |
| **Phase 2 — 프리미티브 컴포넌트** | | | | | |
| 8 | `btn` 계열 전환 (전 화면 버튼) + CTA `btn-primary` 통일 (`bg-brand` 2곳 포함), 점선 버튼 → `btn-dash` | frontend | P1 | DONE | 7 |
| 9 | `input` / `textarea` 전환 (composer auto-grow 로직 유지) | frontend | P1 | DONE | 7 |
| 10 | `badge` / `loading` / `skeleton` / `avatar`(+placeholder) / `status` 전환 | frontend | P1 | DONE | 7 |
| 11 | 검증: 커스텀 버튼/인풋 스타일 잔존 0, focus 가시성 | qa | P1 | DONE | 8, 9, 10 |
| **Phase 3 — 구조 컴포넌트 + 아이콘** | | | | | |
| 12 | 5개 헤더 → `navbar` (`navbar-start/end`, sticky+backdrop-blur 유지) | frontend | P1 | DONE | 11 |
| 13 | 목록 → `list`/`list-row`, 토픽/초대 카드 → `card card-border`, 폼 → `join`/`fieldset`(+`validator`) | frontend | P1 | DONE | 11 |
| 14 | 커스텀 div 모달 2곳 → `<dialog class="modal modal-bottom sm:modal-middle">` | frontend | P1 | DONE | 11 |
| 15 | 이모지 아이콘 → lucide (`Bell` `Settings` `MessageCircle` `UserPlus` `ArrowLeft` `ArrowUp`) + `btn btn-ghost btn-square` | frontend | P1 | DONE | 12 |
| 16 | a11y 검증: dialog focus trap/ESC, aria 레이블 보존 | qa | P1 | DONE | 14, 15 |
| **Phase 4 — ChatRoom 전환** | | | | | |
| 17 | 말풍선 → `chat chat-start/end` + `chat-bubble`(-primary) + `chat-image avatar` + `chat-header/footer` | frontend | P1 | DONE | 16 |
| 18 | 날짜 구분선 → `divider`, 시스템 메시지 → `badge badge-ghost`, 연결 점 → `status`, 복사 아이콘 → `swap swap-rotate`, 저장/복사 피드백 → `toast`+`alert` | frontend | P1 | DONE | 16 |
| 19 | 채팅 회귀 검증: 히스토리 페이징 앵커, 낙관적 전송 치환, IME Enter, 읽음 처리 | qa | P1 | WIP | 17, 18 |
| **Phase 5 — 정리 & QA** | | | | | |
| 20 | PWA 대응: manifest `theme_color/background_color` 라이트 기준값 + `app.html` meta theme-color 듀얼(media query) | frontend | P2 | DONE | 19 |
| 21 | 최종 스윕: 잔존 레거시 grep 0, 양 모드 × 주요 5화면 시각 검증, `bun run check`/`build` | qa | P2 | DONE | 20 |
| 22 | tracker Status → Completed, tech-debt 기록 | frontend | P2 | WIP | 21 |

## Done When

- [ ] 레거시 컬러 토큰/클래스 grep 0건 (`(bg|text|border|outline)-(background|surface|surface-elevated|text-primary|text-secondary|text-muted|text-inverse|brand|accent|accent-hover|danger)`)
- [ ] `app.css` `@theme`에 컬러 정의 없음 (daisyUI 테마가 유일한 컬러 소스)
- [ ] light/dark가 `prefers-color-scheme`에 따라 자동 전환되고 양 모드 모두 WCAG AA 대비 유지
- [ ] 채택 22종 daisyUI 컴포넌트가 대상 화면에 적용됨
- [ ] `bun run check` + `bun run build` 통과
- [ ] 채팅 핵심 UX(페이징/앵커/낙관 전송/IME) 회귀 없음
- [ ] DateDial 인터랙션 회귀 없음 (색상만 변경)

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-16 | 빌트인 `dark` 테마 채택 (커스텀 테마 없음) | 사용자 방침: daisyUI 제공 값이 기존 설정값보다 우선 |
| 2026-07-16 | `light --default, dark --prefersdark` — 시스템 설정 따라 양 모드 지원 | 사용자 선택: system default 기준 다크+라이트 |
| 2026-07-16 | CTA는 `btn-primary`로 통일 (투톤 폐지) | daisyUI 컬러 규칙(페이지당 primary 1곳)과 합치, 유지보수 단순화 |
| 2026-07-16 | 이모지 아이콘 → lucide 교체 | `@lucide/svelte` 기존 의존성, btn-ghost와 조합 시 일관성 |
| 2026-07-16 | elevation 방향은 daisyUI 시맨틱 수용 (base-100 페이지, 200/300 어두운 쪽) | daisyUI 우선 방침의 자연스러운 귀결 |
| 2026-07-16 | 카카오 `#FEE500` 하드코딩 유지 | 테마 독립 브랜드색 (daisyUI colors rule 11 예외) |
| 2026-07-16 | DateDial은 daisyUI 미적용(색상만 토큰화) | carousel/tab 검토 후 탈락 — 중앙 스냅+rAF+햅틱은 라이브러리 범위 밖 |

## Progress Notes

- [2026-07-16] Plan created. 사용자 결정 4건 확정(테마/라이트 모드/CTA/아이콘). Phase 0 승인 대기.
- [2026-07-16] /ultrawork 세션(oma-00mrnfuw0trni9gnb8)으로 전환 실행. PLAN→IMPL→VERIFY→REFINE→SHIP
  전 게이트 통과. 9 commits (e5fe737..35ffded). VERIFY MEDIUM 2건 발견·수정(b70ae7e),
  REFINE UserAvatar 추출(35ffded), tech-debt 3건 기록. 런타임 스모크(라이트/다크 전환) 정상.
  task 19(채팅 런타임 회귀)·양 모드 실화면 검증은 백엔드 필요 — 사용자 확인 권장 항목으로 이관.
  SHIP_GATE 사용자 최종 승인 대기.
- [2026-07-16] SHIP 런타임 사용자 검토 후 그룹 목록 카드가 가용 폭을 채우도록 수정하고
  중복 accessible name을 제거함(`678f65b`). 라이트 모드 내 메시지 Markdown 대비 문제는
  primary surface용 prose variant와 AA 대비 말풍선 배경으로 수정함(`5b0da5c`). 두 수정 모두
  light/dark·반응형·Lighthouse·build 검증을 통과했으며 SHIP_GATE 최종 승인은 계속 대기.
