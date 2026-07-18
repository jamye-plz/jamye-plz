# Tech Debt Tracker

| # | Debt | Source | Priority | Status | Resolution |
|---|------|--------|----------|--------|------------|
| 1 | navbar 헤더 패턴 6+ 페이지 중복 (`navbar sticky top-0 ...` + back button + title) | 001-daisyui-migration | P2 | ✅ **Resolved** (PR #13, `8fc3449`) | `AppHeader.svelte` 공용 shell 컴포넌트 추출 — 헤더 shell·safe-area를 단일 소유. 7개 화면(6 페이지 + ChatRoom) 전부 `<AppHeader>` 사용, inline navbar shell 0 |
| 2 | `cookie <0.7.0` LOW 취약점 (@sveltejs/kit 전이 의존성, GHSA-pxg6-pf52-xh8x) | 001-daisyui-migration (QA 발견, 기존 이슈) | P3 | Open → 후속 브랜치 | `bun update @sveltejs/kit` (cookie ≥0.7 유입). 앱이 사용자 입력으로 쿠키 속성을 만들지 않아 실노출 미미 |
| 3 | svelte-check 8 pre-existing errors (virtual:pwa-register 타입 선언 1, string\|undefined 파라미터 7) | 기존 코드 (마이그레이션 무관) | P3 | Open → 후속 브랜치 | `app.d.ts`에 `/// <reference types="vite-plugin-pwa/client" />` 추가(vanilla `virtual:pwa-register` 타입) + 라우트 파라미터 7곳 non-null 처리. 빌드/런타임 무영향(타입체커만) |
| 4 | `adm-zip` HIGH 취약점 (`@huggingface/transformers → onnxruntime-node → adm-zip`, GHSA-xcpc-8h2w-3j85) | `bun audit` (2026-07-18 발견) | P2 | Open → 후속 브랜치 | `@huggingface/transformers`가 **직접 의존성이나 src 어디에서도 미사용**(중단된 ML 기능 잔재) → `bun remove @huggingface/transformers`로 제거. HIGH 취약점 제거 + 무거운 의존성 트리 정리. 실런타임 위험은 낮음(adm-zip은 Node 전용 전이 의존성이라 브라우저 SPA 미실행) |

> **Note**: #2·#3·#4는 이번 PR(모바일 UX) 스코프와 무관한 기존/의존성 이슈라 별도 유지보수 브랜치에서 처리. #2·#4는 `bun.lock` 변경 → Nix FOD 해시(`infra/frontend.nix`) 재생성 필요.
