# Tech Debt Tracker

| # | Debt | Source | Priority | Status | Resolution |
|---|------|--------|----------|--------|------------|
| 1 | navbar 헤더 패턴 6+ 페이지 중복 (`navbar sticky top-0 ...` + back button + title) | 001-daisyui-migration | P2 | ✅ **Resolved** (PR #13, `8fc3449`) | `AppHeader.svelte` 공용 shell 컴포넌트 추출 — 헤더 shell·safe-area를 단일 소유. 7개 화면(6 페이지 + ChatRoom) 전부 `<AppHeader>` 사용, inline navbar shell 0 |
| 2 | `cookie <0.7.0` LOW 취약점 (@sveltejs/kit 전이 의존성, GHSA-pxg6-pf52-xh8x) | 001-daisyui-migration (QA 발견, 기존 이슈) | P3 | 🟢 **Accepted / 비취약** | **정적 SPA(`adapter-static` + `ssr=false`)라 이 앱에선 비취약**: `cookie`의 유일한 소비처인 kit **서버(SSR) 런타임**이 클라이언트 빌드에 포함·실행되지 않음(인증 쿠키는 FastAPI 백엔드가 설정). ⚠️ 버전 bump로는 **안 고쳐짐** — stable kit 2.x는 전부 `cookie ^0.6.0` 고정(2.70.0 포함), cookie 상향은 kit v3(브레이킹 prerelease `^2.0.0`)뿐. 클린 audit이 필요하면 `overrides: { cookie: "0.7.2" }` 선택 가능(해당 코드 미실행이라 저리스크) |
| 3 | svelte-check 8 pre-existing errors (virtual:pwa-register 타입 선언 1, string\|undefined 파라미터 7) | 기존 코드 (마이그레이션 무관) | P3 | ✅ **Resolved** (`chore/dep-audit-and-type-cleanup`) | `app.d.ts`에 `/// <reference types="vite-plugin-pwa/client" />` 추가(vanilla `virtual:pwa-register` 타입) + 라우트 파라미터 7곳 non-null(`!`) 처리. **`bun check` = 0 errors / 0 warnings** 달성 |
| 4 | `adm-zip` HIGH 취약점 (`@huggingface/transformers → onnxruntime-node → adm-zip`, GHSA-xcpc-8h2w-3j85) | `bun audit` (2026-07-18 발견) | P2 | ✅ **Resolved** (`chore/dep-audit-and-type-cleanup`) | `@huggingface/transformers`가 직접 의존성이나 src 미사용(중단된 ML 기능 잔재) → `bun remove`로 제거. `bun audit` HIGH **0**. bun.lock 변경 → Nix FOD 해시(`infra/frontend.nix`) 재생성 완료 |
| 5 | 백그라운드 구독 등록 실패로 **SW 푸시 구독이 제거되면 자동 복구되지 않음** | v2 M1 (PR #17 리뷰, P2로 defer) | P2 | 🔴 **Open** | `service-worker.ts`의 `pushsubscriptionchange`와 `push.api.ts`의 `requestAndSubscribe`는 등록 POST 실패 시 로컬 구독을 **되돌린다**(유령 구독 방지). 되돌린 뒤에는 사용자가 토글을 다시 켜기 전까지 복구되지 않는다. → "켜져 있었음" 마커를 영속화(`localStorage`/IndexedDB)하고 `PushReconciler`가 그 마커를 보고 재구독하도록 |
| 6 | `notificationclick`이 **이미 열린 채팅 탭을 못 찾고 새 탭을 연다** | v2 M1 (PR #17 리뷰, P2로 defer) | P2 | 🔴 **Open** | `service-worker.ts:57` — payload의 `url`은 **상대 경로**(`/groups/...`)인데 `WindowClient.url`은 **절대 URL**이라 `c.url === url` 비교가 항상 실패한다. → `new URL(url, self.location.origin).href`로 정규화한 뒤 비교 |
| 7 | **ruff 실행 방식 불일치** — `uvx ruff`가 프로젝트 핀을 무시하고 최신 버전을 받음 | v2 M1/M2 품질 게이트 실행 중 발견 | P3 | 🔴 **Open** | `pyproject.toml`은 `ruff>=0.8.0`(락 0.15.17)인데 `uvx ruff`는 0.16.0을 받아와 **무관한 기존 파일까지 무더기로 지적**한다. `uv run ruff`는 clean. → 게이트 문서·스크립트를 `uv run ruff`로 통일하고(로드맵 §8 반영 완료), 필요하면 `ruff==` 상한 핀 |

> **현황**: #1·#3·#4 해소. #2(cookie LOW)는 정적 SPA라 **비취약으로 수용**(문서화) — 프론트가 kit 서버 쿠키 코드를 실행하지 않음. `bun audit` = 1 low (cookie, 비취약) / 0 high.
> **미해결**: #5·#6(v2 M1 푸시 P2 — 기능은 동작하나 엣지 케이스), #7(ruff 게이트 정합성).
