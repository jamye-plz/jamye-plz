# Ultrawork Session — Mobile PWA UX (started 2026-07-18)

- **Workflow**: ultrawork / Runtime: Claude Code (전 에이전트 claude 네이티브)
- **User request**:
  1. 모바일 PWA 채팅방에서 키보드가 올라올 때 header(뒤로가기·주제·status)가 같이 밀려 올라감 —
     키보드와 독립적으로 상단 고정 필요
  2. DateDial이 모바일(PWA/웹)에서 정확히 드래그해도 안 넘어가는 간헐 이슈 (데스크탑은 정상).
     dial 방식 좌우 날짜 조정 유지 원함 + 모바일 특화 라이브러리 조사 요청
- **Branch**: 계획 승인 후 main(PR #12 머지 포함)에서 신규 브랜치 생성 예정
- Phase 0: 리소스는 동일 세션 선행 ultrawork에서 로드됨 (재사용), session.created emitted

## Phase Log
- [x] Phase 0 재개: 리소스 선행 세션 재사용, 언어 ko 확인
- [x] Phase 1 PLAN 검증(2026-07-18 재개): 실제 코드 대조 완료
  - ChatRoom.svelte: root `flex h-screen flex-col`, header `sticky top-0 z-10`, footer composer.
    근본원인 확정 — h-screen(고정 100vh) + iOS가 layout viewport를 pan → sticky header가 화면 밖으로 밀림.
  - DateDial.svelte: 네이티브 CSS scroll-snap + `setTimeout(onSettle, 110)` quiescence 타이머.
    근본원인 확정 — iOS 모멘텀/스냅이 110ms 초과로 scroll 이벤트를 멈춰 stale nearestIndex() 커밋 →
    시각 위치와 선택이 간헐 불일치. iOS Safari `scrollend` 부재.
  - 계약 확인: DateDial props = dates/selected/today/onselect. 사용처 1곳(groups/[id]/+page.svelte:170). 계약 불변 시 호출부 0 변경.
- [x] dial 라이브러리 조사 완료:
  - embla-carousel-svelte 8.6.0 → Svelte 5 공식 지원(peer ^5.0.0), use: 액션 패턴. 가로 dial 적합. **A안 권장**
  - 세로 wheel picker류(svelte-wheel-picker, svelte-date-picker-scroller, more-shadcn-svelte WheelPicker 등)는
    iOS 시계형 세로 스핀 → 현재 가로 좌우 dial UX와 불일치(사용자 "좌우 조정" 요구와 안 맞음). 후보 제외.
- [x] PLAN_GATE PASSED: 사용자 DateDial 접근 **A(Embla)** 선택. plan-approved/impl-plan-locked/datedial-approach emit·verify. 브랜치 fix/mobile-pwa-ux 생성.
- [x] Phase 2 IMPL: frontend-issue1(ChatRoom+app.html) / frontend-issue2(DateDial Embla) 병렬. IMPL_GATE PASSED (check 8/0, build 0, 계획 범위 파일만).
- [x] Phase 3 VERIFY: 오케스트레이터 런타임 에뮬(chrome-devtools 390×844 touch) + 정적 리뷰.
  - **CRITICAL 발견·수정**: DateDial viewport `display:flex` → Embla가 컨테이너를 콘텐츠폭(1680)으로 재어 뷰포트 오측정 → limit ±784로 edge/selected 센터링 불가 → dial 비가시. **수정**: viewport를 block으로. 검증 후 slide 0/14 모두 195px 센터, limit {-1466,102}.
  - **MEDIUM 발견·수정**: programmatic scrollTo가 select 커밋 유발(진입 시 onselect 2회, 클릭 중간 날짜 커밋 위험). **수정**: `programmatic` 플래그(init/click/외부변경 시 set, settle/pointerDown 시 clear)로 onEmblaSelect 게이트.
  - 런타임 검증: 진입 onselect 0 / 클릭·화살표 각 1 / 드래그 1(커밋==시각센터). ChatRoom 정적 리뷰 결함 0.
  - QA 서브에이전트는 result 파일 미작성·조기종료 → 오케스트레이터가 VERIFY 대행(result-qa-oma-00mrpr6b3knk60qqb8.md).
  - VERIFY_GATE: **GO** (C0/H0). check 8/0, build 0. 임시 하니스 routes/dev/datedial 제거 완료.
  - **EA 이벤트**: static review가 놓친 런타임 CRITICAL을 에뮬로 포착 → missed_stub 1 (정적 게이트만으로 불충분, 런타임 검증 필수 교훈).
- [ ] Phase 4 REFINE / [ ] Phase 5 SHIP (실기기 확인 필요 — 사용자)
- 커밋: fix/mobile-pwa-ux 브랜치 (push 미수행, 사용자 SHIP 승인 대기)

## SHIP 실기기 1차 테스트 결과 (사용자, 2026-07-18)
- **Issue 1 수정 실패 확인**: 설치된 iOS PWA(standalone)에서 입력창 포커스 시 여전히 header 사라지고 composer가 위로 뜸.
  원인: 1차 수정(정상흐름 요소 높이 조정 + scrollTo)은 문서에서 "body-height 리사이즈" 실패 패턴으로 명시됨 — iOS가 여전히 문서를 pan.
- **Issue 1 재수정 (d3c2562)**: 검증된 `ios-chat` 기법 채택 —
  문서 잠금(body `overflow:hidden`+`touch-action:none`, html `overflow:hidden`) → iOS가 pan할 대상 제거,
  chat root 높이를 `visualViewport.height`(`--vvh` CSS 변수)로 구동. iOS26 잔여(~24px) 대비 max-height 가드.
  기존 rootEl/scrollTo/focusout 방식 제거. root: `height: var(--vvh, 100dvh)`. 메시지영역 `overscroll-contain` 추가.
  → **데스크탑 검증 불가**(iOS 특유 pan은 에뮬 안 됨; 하니스는 거짓 확신). 기기 재테스트 대기.
- **Issue 2 (DateDial)**: 데스크탑 런타임 검증 완료(변동 없음). 실기기 드래그 확인만 남음.
- 별건: 사용자가 백엔드 LAN 노출 커밋(2bff4f4) + "메시지 전송 안 됨" 보고 → 우리 diff와 무관(WS/stub/env 추정), 별도 진단 대상.
- check 8/0, build 0, lint clean 유지.

## SHIP 실기기 2차 테스트 결과 (사용자, 2026-07-18)
- **d3c2562(문서잠금+--vvh)도 실패**: 스크린샷 상 키보드 시 입력창이 화면 최상단으로, header 완전히 밀림.
  근본원인 재확정: iOS는 **visual viewport를 PAN**(레이아웃 리사이즈 아님) → `overflow:hidden`으로 못 막고,
  정상흐름/컨테이너는 pan에 끌려감. 사용자 요구=카카오톡처럼 header 고정 + 메시지·입력창만 키보드 위로.
- **재수정 3차 (983cdc3)**: 검증된 PWA 해법 —
  chat root를 `position: fixed`로 만들고, visualViewport resize/scroll마다
  `height=visualViewport.height`, `top=visualViewport.offsetTop`로 능동 고정 → 항상 키보드 위 가시영역 점유.
  header에 `pt-[env(safe-area-inset-top)]`, composer에 `pb-[calc(0.75rem+env(safe-area-inset-bottom))]` 추가(노치/홈인디케이터).
  root `bind:this` 복구. body/html `overflow:hidden` 잠금 유지(스크롤 방지).
  → 데스크탑 검증 불가(iOS pan 에뮬 불가). 기기 3차 재테스트 대기.
- 커밋 순서: ea76e76(1차)→d3c2562(2차)→983cdc3(3차). PR 시 squash 권장.

## SHIP 실기기 3차 테스트 결과 (사용자, 2026-07-18)
- **983cdc3(position:fixed root + offsetTop 추적) 부분 성공/잔존이슈**: 최종 위치는 맞으나
  키보드 올릴/내릴 때 **header까지 같이 슬라이드**(불필요 스크롤). 원인: root 전체를 offsetTop에 맞춰
  매 프레임 이동 → iOS pan 애니메이션 동안 header가 흔들림. 사용자 요구=header 완전 정지, 메시지영역만 이동.
- **재수정 4차 (04292c6)**: ios-chat 검증 기법 —
  **document 자체를 부동화**: `body{position:fixed; inset:0; overflow:hidden; touch-action:none}` + `html{overflow:hidden}`
  → iOS가 pan할 대상 제거. root는 일반흐름 `height: var(--vvh, 100dvh)`로 **높이만** 축소(offsetTop 미추적).
  root top이 절대 안 움직여 header 구조적 고정, 메시지+composer만 키보드 위로. rootEl/position:fixed 제거.
  → 데스크탑 검증 불가. 기기 4차 재테스트 대기. check 8/0, build 0, lint clean.

## SHIP 실기기 5~7차 + 연구 결론 (2026-07-18) — iOS PWA 구조적 한계 확인
- 5차 transform 보정: header slide 완화됐으나 여러 사이클 후 sy(window.scrollY)가 300→59 애니메이션 → scrollTo와 싸움(피드백 루프).
- 6차 body-fixed+transform: 전체 페이지가 밑에서 슬라이딩으로 올라옴(일관 발생). 디버그값 vh/ot/iw/sy가 "한 순간에 고정".
- **핵심 진단**: iOS는 키보드 애니메이션 동안 visualViewport resize/scroll 이벤트를 **프레임별로 안 쏨**(최종값 1회) → JS 프레임 보정 구조적 불가.
- **연구 결론(웹 조사)**: iOS/WebKit 문서화된 제약. (1) 키보드는 visual viewport만 축소+layout viewport pan, (2) 애니메이션 중 per-frame 이벤트 없음, (3) `env(keyboard-inset-height)`(VirtualKeyboard API)는 **WebKit 미지원**(Chromium 전용). 순수 CSS 불가. Telegram/WhatsApp/Twitter/LinkedIn 모두 불완전 — "ideal solution 없음". iOS26 offsetTop 미리셋 회귀도 Apple 인정.
- **PWA에서 키보드 애니메이션 중 header 완벽 고정 = 구조적으로 불가.** best-effort(정착 상태만 맞추고 전환 jank 감수) 또는 Capacitor 네이티브 래퍼(Keyboard 플러그인 resize)가 실질 해법.
- 현재 코드 상태: ChatRoom에 디버그 오버레이 + body-fixed+transform(미커밋). 사용자 전략 결정 대기 → revert / best-effort / Capacitor.

## 사용자 결정 + 마무리 (2026-07-18)
- **사용자 선택: A안 best-effort PWA** — 현 상태 유지, 디버그 코드 전부 제거.
- **커밋 3f0a09a** (04292c6 amend): 디버그(vpDebug state/apply line/overlay div) 제거, 주석을 best-effort+iOS 한계 명시로 갱신.
  최종 방식 = body position:fixed(window 스크롤 차단) + fixed root height=vv.height + transform translateY(offsetTop) 보정.
  한계 명시: 정착 상태는 정상, 전환 애니메이션 slide는 iOS 자체라 JS로 못 잡음. env(keyboard-inset)은 WebKit 미지원. 완전 해법=Capacitor.
  check 8/0, build 0, eslint 0, prettier clean, 디버그 잔여 0.
- **package.json**: 사용자가 dev/preview에 `--host` 추가(LAN 테스트용) — 미커밋, 사용자 소유라 그대로 둠.
- 남은 것: Issue 2 DateDial 실기기 드래그 확인 + SHIP 마무리(PR). Issue 1은 best-effort로 종결.
- 헤더 수정 커밋 이력 지저분(ea76e76→d3c2562→3f0a09a 동일 이슈) → PR 시 squash 권장.
