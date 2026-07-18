# Tech Debt Tracker

| # | Debt | Source | Priority | Status | Resolution |
|---|------|--------|----------|--------|------------|
| 1 | navbar 헤더 패턴 6+ 페이지 중복 (`navbar sticky top-0 ...` + back button + title) | 001-daisyui-migration | P2 | ✅ **Resolved** (PR #13, `8fc3449`) | `AppHeader.svelte` 공용 shell 컴포넌트 추출 — 헤더 shell·safe-area를 단일 소유. 7개 화면(6 페이지 + ChatRoom) 전부 `<AppHeader>` 사용, inline navbar shell 0 |
| 2 | `cookie <0.7.0` LOW 취약점 (@sveltejs/kit 전이 의존성, GHSA-pxg6-pf52-xh8x) | 001-daisyui-migration (QA 발견, 기존 이슈) | P3 | ⚠️ **Partial** (`chore/dep-audit-and-type-cleanup`) | `@sveltejs/kit` 2.70.0로 bump 완료. 그러나 **cookie LOW 잔존** — kit가 여전히 `cookie ^0.6.0`로 고정해 0.7이 안 들어옴. 강제 override는 auth 쿠키 경로 리스크 > LOW 이득이라 보류. kit가 cookie 상향 시 자동 해소 |
| 3 | svelte-check 8 pre-existing errors (virtual:pwa-register 타입 선언 1, string\|undefined 파라미터 7) | 기존 코드 (마이그레이션 무관) | P3 | ✅ **Resolved** (`chore/dep-audit-and-type-cleanup`) | `app.d.ts`에 `/// <reference types="vite-plugin-pwa/client" />` 추가(vanilla `virtual:pwa-register` 타입) + 라우트 파라미터 7곳 non-null(`!`) 처리. **`bun check` = 0 errors / 0 warnings** 달성 |
| 4 | `adm-zip` HIGH 취약점 (`@huggingface/transformers → onnxruntime-node → adm-zip`, GHSA-xcpc-8h2w-3j85) | `bun audit` (2026-07-18 발견) | P2 | ✅ **Resolved** (`chore/dep-audit-and-type-cleanup`) | `@huggingface/transformers`가 직접 의존성이나 src 미사용(중단된 ML 기능 잔재) → `bun remove`로 제거. `bun audit` HIGH **0**. bun.lock 변경 → Nix FOD 해시(`infra/frontend.nix`) 재생성 완료 |

> **잔여**: cookie LOW(#2)만 열려 있으며 kit의 cookie 상향에 의존. 나머지(#1·#3·#4)는 해소. `bun audit` 현재 = 1 low (cookie) / 0 high.
