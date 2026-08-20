# Tech Debt Tracker

| # | Debt | Source | Priority | Status | Resolution |
|---|------|--------|----------|--------|------------|
| 1 | navbar 헤더 패턴 6+ 페이지 중복 (`navbar sticky top-0 ...` + back button + title) | 001-daisyui-migration | P2 | ✅ **Resolved** (PR #13, `8fc3449`) | `AppHeader.svelte` 공용 shell 컴포넌트 추출 — 헤더 shell·safe-area를 단일 소유. 7개 화면(6 페이지 + ChatRoom) 전부 `<AppHeader>` 사용, inline navbar shell 0 |
| 2 | `cookie <0.7.0` LOW 취약점 (@sveltejs/kit 전이 의존성, GHSA-pxg6-pf52-xh8x) | 001-daisyui-migration (QA 발견, 기존 이슈) | P3 | 🟢 **Accepted / 비취약** | **정적 SPA(`adapter-static` + `ssr=false`)라 이 앱에선 비취약**: `cookie`의 유일한 소비처인 kit **서버(SSR) 런타임**이 클라이언트 빌드에 포함·실행되지 않음(인증 쿠키는 FastAPI 백엔드가 설정). ⚠️ 버전 bump로는 **안 고쳐짐** — stable kit 2.x는 전부 `cookie ^0.6.0` 고정(2.70.0 포함), cookie 상향은 kit v3(브레이킹 prerelease `^2.0.0`)뿐. 클린 audit이 필요하면 `overrides: { cookie: "0.7.2" }` 선택 가능(해당 코드 미실행이라 저리스크) |
| 3 | svelte-check 8 pre-existing errors (virtual:pwa-register 타입 선언 1, string\|undefined 파라미터 7) | 기존 코드 (마이그레이션 무관) | P3 | ✅ **Resolved** (`chore/dep-audit-and-type-cleanup`) | `app.d.ts`에 `/// <reference types="vite-plugin-pwa/client" />` 추가(vanilla `virtual:pwa-register` 타입) + 라우트 파라미터 7곳 non-null(`!`) 처리. **`bun check` = 0 errors / 0 warnings** 달성 |
| 4 | `adm-zip` HIGH 취약점 (`@huggingface/transformers → onnxruntime-node → adm-zip`, GHSA-xcpc-8h2w-3j85) | `bun audit` (2026-07-18 발견) | P2 | ✅ **Resolved** (`chore/dep-audit-and-type-cleanup`) | `@huggingface/transformers`가 직접 의존성이나 src 미사용(중단된 ML 기능 잔재) → `bun remove`로 제거. `bun audit` HIGH **0**. bun.lock 변경 → Nix FOD 해시(`infra/frontend.nix`) 재생성 완료 |
| 5 | 백그라운드 구독 등록 실패로 **SW 푸시 구독이 제거되면 자동 복구되지 않음** | v2 M1 (PR #17 리뷰, P2로 defer) | P2 | 🔴 **Open** | `service-worker.ts`의 `pushsubscriptionchange`와 `push.api.ts`의 `requestAndSubscribe`는 등록 POST 실패 시 로컬 구독을 **되돌린다**(유령 구독 방지). 되돌린 뒤에는 사용자가 토글을 다시 켜기 전까지 복구되지 않는다. → "켜져 있었음" 마커를 영속화(`localStorage`/IndexedDB)하고 `PushReconciler`가 그 마커를 보고 재구독하도록 |
| 6 | `notificationclick`이 **이미 열린 채팅 탭을 못 찾고 새 탭을 연다** | v2 M1 (PR #17 리뷰, P2로 defer) | P2 | ✅ **Resolved** | payload의 `url`은 상대 경로(`/groups/...`)인데 `WindowClient.url`은 절대 URL이라 비교가 항상 실패했다. `new URL(url, self.location.origin).href`로 정규화 후 비교하도록 수정. 더불어 `matchAll`에 `includeUncontrolled: true`를 넣어, **아직 이 SW의 제어를 받지 않는 탭**(SW 갱신 직후 등)이 목록에서 빠져 같은 증상이 나는 경로도 막았다 |
| 7 | **ruff 실행 방식 불일치** — `uvx ruff`가 프로젝트 핀을 무시하고 최신 버전을 받음 | v2 M1/M2 품질 게이트 실행 중 발견 | P3 | ✅ **Resolved** (문서·태스크로 방어) | 정식 게이트 경로는 `uv run poe lint`/`poe format`(`pyproject.toml`의 poe 태스크)이라 **항상 `uv.lock`의 ruff**를 쓴다. 로드맵 §8도 `uv run ruff`로 통일했고, 저장소 어떤 스크립트도 `uvx ruff`를 호출하지 않는다(문서의 경고 문구뿐). ⚠️ **원래 적어둔 "`ruff==` 상한 핀"은 무효라 적용하지 않았다** — `uvx`는 프로젝트를 아예 무시하므로 `pyproject.toml`에 상한을 걸어도 `uvx ruff`의 동작을 바꾸지 못하고, 향후 ruff 업그레이드만 막는다. 남은 위험은 "사람이 손으로 `uvx ruff`를 친다" 하나뿐이며 이는 문서로만 방어 가능하다 |
| 8 | 채팅 첨부의 **원본 파일명 미저장** — 다운로드 파일명이 `jamye-{media_id}.{ext}` | v2 M3 (PR #21, 범위에서 제외) | P3 | ✅ **Resolved** (PR #22, `6ffe903`) | M4a 마이그레이션(`f6a7b8c9d0e1`)에 **묶어서 해결** — 별도 배포를 아끼려 전사 컬럼과 같은 리비전에 넣었다. nullable `filename` 컬럼 + 업로드 시 `File.name` 전달, 다운로드는 `media.filename or download_filename_for(...)`로 원본명을 복원하고 없으면 합성명으로 폴백한다 |
| 9 | 채팅 첨부 **orphan 객체 정리 없음** | v2 M3 (PR #21, 구조적) | P3 | 🔴 **Open** | 업로드는 성공했는데 WS 전송이 실패하면 MinIO 객체만 남는다. 메시지 삭제 기능 자체가 없어 지금은 누수 경로가 이것 하나뿐이고 발생 빈도도 낮다. → 메시지 삭제를 만들 때 함께 설계(예: `object_key` 기준 미참조 객체 배치 정리) |
| 10 | `partysocket` 의존성이 **설치만 되고 미사용** | 기획-구현 드리프트 (tech-stack에 문서화됨) | P3 | ✅ **Resolved** (PR #22, `6ffe903`) | M4a에 **묶어서 제거** — `bun.lock`이 어차피 바뀌는 김에 FOD 해시 재생성을 1회로 합쳤다. 실시간은 표준 `WebSocket`을 직접 쓰고 재연결은 `ChatRoom.svelte`가 관리한다 |

> **현황** (갱신 2026-08-20): #1·#3·#4·#6·#7·**#8·#10** 해소 — #8·#10은 M4a(PR #22)에서 함께 정리됐으나 표기가 누락돼 있었다. #2(cookie LOW)는 정적 SPA라 **비취약으로 수용**(문서화) — 프론트가 kit 서버 쿠키 코드를 실행하지 않음. `bun audit` = 1 low (cookie, 비취약) / 0 high.
>
> **미해결 2건과 왜 지금 안 하는가**:
> - **#5** SW 구독 자동 복구(P2) — 구현은 프론트 국한이라 작지만, "등록 실패 후 복구"를 실기기에서
>   의도적으로 재현해야 검증된다. 기능 자체는 동작 중이라 급하지 않다.
> - **#9** orphan 객체 정리(P3) — **메시지 삭제 기능이 없는 상태에서 "미참조 객체 삭제" 배치를 만들면,
>   참조 판정이 틀렸을 때 살아있는 첨부를 지운다.** 되돌릴 수 없는 작업이라 삭제 기능과 함께 설계한다.
>   현재 누수 경로는 "업로드 성공 + WS 전송 실패" 하나뿐이라 빈도가 낮다.

