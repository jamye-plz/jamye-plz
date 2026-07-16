# Tech Debt Tracker

| # | Debt | Source Plan | Priority | Proposed Resolution |
|---|------|-------------|----------|---------------------|
| 1 | navbar 헤더 패턴 6+ 페이지 중복 (`navbar sticky top-0 ...` + back button + title) | 001-daisyui-migration | P2 | `PageHeader.svelte` 공용 컴포넌트 추출 (별도 refactor 사이클) |
| 2 | `cookie <0.7.0` LOW 취약점 (@sveltejs/kit 전이 의존성, GHSA-pxg6-pf52-xh8x) | 001-daisyui-migration (QA 발견, 기존 이슈) | P3 | `bun update @sveltejs/kit` 별도 유지보수 태스크 |
| 3 | svelte-check 8 pre-existing errors (virtual:pwa-register 타입 선언 1, string\|undefined 파라미터 7) | 기존 코드 (마이그레이션 무관) | P3 | pwa-register 타입 선언 추가 + 라우트 파라미터 non-null 처리 별도 fix |
