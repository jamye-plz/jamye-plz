# Tech Debt Tracker

| # | Debt | Source | Priority | Status | Resolution |
|---|------|--------|----------|--------|------------|
| 1 | navbar 헤더 패턴 6+ 페이지 중복 (`navbar sticky top-0 ...` + back button + title) | 001-daisyui-migration | P2 | ✅ **Resolved** (PR #13, `8fc3449`) | `AppHeader.svelte` 공용 shell 컴포넌트 추출 — 헤더 shell·safe-area를 단일 소유. 7개 화면(6 페이지 + ChatRoom) 전부 `<AppHeader>` 사용, inline navbar shell 0 |
| 2 | `cookie <0.7.0` LOW 취약점 (@sveltejs/kit 전이 의존성, GHSA-pxg6-pf52-xh8x) | 001-daisyui-migration (QA 발견, 기존 이슈) | P3 | 🟢 **Accepted / 비취약** | **정적 SPA(`adapter-static` + `ssr=false`)라 이 앱에선 비취약**: `cookie`의 유일한 소비처인 kit **서버(SSR) 런타임**이 클라이언트 빌드에 포함·실행되지 않음(인증 쿠키는 FastAPI 백엔드가 설정). ⚠️ 버전 bump로는 **안 고쳐짐** — stable kit 2.x는 전부 `cookie ^0.6.0` 고정(2.70.0 포함), cookie 상향은 kit v3(브레이킹 prerelease `^2.0.0`)뿐. 클린 audit이 필요하면 `overrides: { cookie: "0.7.2" }` 선택 가능(해당 코드 미실행이라 저리스크) |
| 3 | svelte-check 8 pre-existing errors (virtual:pwa-register 타입 선언 1, string\|undefined 파라미터 7) | 기존 코드 (마이그레이션 무관) | P3 | ✅ **Resolved** (`chore/dep-audit-and-type-cleanup`) | `app.d.ts`에 `/// <reference types="vite-plugin-pwa/client" />` 추가(vanilla `virtual:pwa-register` 타입) + 라우트 파라미터 7곳 non-null(`!`) 처리. **`bun check` = 0 errors / 0 warnings** 달성 |
| 4 | `adm-zip` HIGH 취약점 (`@huggingface/transformers → onnxruntime-node → adm-zip`, GHSA-xcpc-8h2w-3j85) | `bun audit` (2026-07-18 발견) | P2 | ✅ **Resolved** (`chore/dep-audit-and-type-cleanup`) | `@huggingface/transformers`가 직접 의존성이나 src 미사용(중단된 ML 기능 잔재) → `bun remove`로 제거. `bun audit` HIGH **0**. bun.lock 변경 → Nix FOD 해시(`infra/frontend.nix`) 재생성 완료 |

> **현황**: #1·#3·#4 해소. #2(cookie LOW)는 정적 SPA라 **비취약으로 수용**(문서화) — 프론트가 kit 서버 쿠키 코드를 실행하지 않음. `bun audit` = 1 low (cookie, 비취약) / 0 high.
