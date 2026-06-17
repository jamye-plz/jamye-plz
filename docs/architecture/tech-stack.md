# 기술 스택

잼얘좀(jamye-plz)은 홈랩에서 self-host하는 FE/BE 분리형 PWA다. 프론트는 SvelteKit SPA, 백엔드는 FastAPI, AI는 브라우저 안에서 WASM으로 돈다.

> 버전 v1 · 2026-06-16 · SSOT: plan.json

---

## 1. 전체 스택 한눈에

| 영역 | 선택 | 핵심 |
|------|------|------|
| Frontend | SvelteKit (Svelte 5) + Tailwind v4 + shadcn-svelte 1.2.x | `adapter-static` SPA (`ssr=false`) |
| Backend | Python FastAPI | REST + native WebSocket, router→service→repository |
| Database | PostgreSQL | Alembic 마이그레이션 |
| Storage | MinIO | S3 호환, presigned PUT 업로드 |
| Realtime | FastAPI native WebSocket ↔ partysocket | 재연결·백오프 + 직접 heartbeat |
| Auth | 자체 카카오·구글 OAuth + JWT | httpOnly 쿠키, 클라 가드 + FastAPI 검증 2중 |
| AI | WASM 온디바이스 | Transformers.js + multilingual-e5-small(int8 ~118MB) |
| Push | Web Push (VAPID) | 자체 키 생성, pywebpush 발송, vite-pwa injectManifest |
| Deploy | NixOS 홈랩 하이브리드 | 인프라=nix native services / 앱=podman OCI |
| Repo | 단일 모노레포 | `frontend/` + `backend/` + `nix/` |

---

## 2. Frontend 라이브러리

| 라이브러리 | 용도 |
|------------|------|
| `@vite-pwa/sveltekit` | PWA manifest + service worker(injectManifest 커스텀 SW) |
| `@tanstack/svelte-query` v6 | 서버 상태·캐싱·무한 스크롤 |
| `zod` (→ `sveltekit-superforms`) | 폼·입력 검증 |
| `partysocket` | WebSocket 재연결·백오프 클라이언트 |
| `svelte-easy-crop` v5 | 이미지 크롭 |
| `browser-image-compression` | 업로드 전 클라 압축 |
| `@lucide/svelte` | 아이콘 |
| `date-fns` | 날짜 처리(타임라인 일별 그룹핑) |
| `paraglide-js` | i18n |

AI 런타임은 별도 Web Worker에서 Transformers.js(`@huggingface/transformers`)를 구동한다. 상세는 [`./on-device-ai.md`](./on-device-ai.md)를 참고.

---

## 3. 결정 근거 (ADR 요약)

각 결정의 대안과 채택 이유만 핵심으로 정리한다.

### ADR-1. 외부 매니지드(Supabase 올인원) 거부 → self-host + FE/BE 분리

- **대안**: Supabase 같은 BaaS로 인증·DB·스토리지·실시간을 한 번에 묶기.
- **선택**: 자체 self-host, 프론트(SvelteKit)와 백엔드(FastAPI)를 분리.
- **이유**:
  - 홈랩 인프라를 이미 보유 → 운영 통제권과 프라이버시를 직접 쥔다.
  - BaaS의 RLS(Row Level Security)는 서비스 레이어 권한 검증으로 대체한다(상세 [`./data-model.md`](./data-model.md)).
  - 2차 네이티브 앱을 대비해 백엔드를 UI 의존 없는 순수 API로 유지한다.

### ADR-2. 백엔드 FastAPI 채택

- **대안**: Node/NestJS, Django 등.
- **선택**: Python FastAPI, router→service→repository clean architecture.
- **이유**: REST와 native WebSocket을 한 프레임워크에서 다루고, Pydantic 검증과 타입 힌트로 계약을 명확히 한다. 비즈니스 로직은 service, 데이터 접근은 repository로 분리한다.

### ADR-3. 프론트엔드 SvelteKit 채택

- **대안**: Next.js/React.
- **선택**: SvelteKit(Svelte 5), `adapter-static`로 SPA 빌드(`ssr=false`).
- **이유**:
  - 사전 조사 결과 GO. 백엔드가 별도 API이므로 SSR 서버가 불필요 → 정적 SPA로 단순화하고 CDN/정적 서빙에 얹는다.
  - 실시간은 **`socket.io-client` 금지** — FastAPI native WebSocket과 프로토콜이 호환되지 않는다. 대신 표준 WebSocket 위에서 재연결·백오프를 주는 `partysocket`을 쓴다.

### ADR-4. 인증 2중화 (클라 가드 + 서버 검증)

- **대안**: 클라 라우팅 가드만, 혹은 서버 검증만.
- **선택**: SPA 클라 가드(UX) + FastAPI JWT 검증(실보안)의 2중 구조. 토큰은 **httpOnly 쿠키**.
- **이유**: 클라 가드는 비로그인 사용자를 매끄럽게 로그인으로 보내는 UX용일 뿐이고, 실제 보안은 서버가 모든 요청에서 JWT를 검증하고 401을 돌려주는 데 있다. httpOnly 쿠키로 토큰을 JS에서 분리해 XSS 노출을 줄인다. OAuth 제공자는 자체 구현한 카카오·구글.

### ADR-5. WASM 온디바이스 AI

- **대안**: 서버 측 임베딩 API, 외부 LLM API(OpenAI 등).
- **선택**: 브라우저 안 WASM. Transformers.js + multilingual-e5-small(int8) 임베딩, 순수 WASM baseline + WebGPU 자동 감지 가속.
- **이유**:
  - 프라이버시 — 사용자 텍스트가 서버나 외부로 나가지 않는다.
  - 서버 비용 0, 외부 API 의존 제거.
  - 1차 기능(자동 태깅, 살 붙이기 추천)은 임베딩 유사도만으로 충분 → 비생성 방식. 생성형은 다운로드·WebGPU 부담으로 2차로 미룸.

### ADR-6. NixOS 하이브리드 배포

- **대안**: 전부 컨테이너, 혹은 전부 nix 패키징.
- **선택**: 인프라(PostgreSQL/MinIO/Caddy/Redis)는 NixOS native services, 앱(FastAPI/SvelteKit)은 podman OCI 컨테이너.
- **이유**: 인프라는 nix 모듈이 성숙하고 선언적 백업·ACME를 그대로 누린다. 앱은 nix 패키징 시 `uv.lock`/`npmDepsHash` 재해시 마찰이 커 컨테이너로 우회한다. 상세 [`./deployment.md`](./deployment.md).

---

## 4. 관련 문서

- 데이터 모델·권한·마이그레이션 → [`./data-model.md`](./data-model.md)
- API 계약(REST·WebSocket) → [`./api-contract.md`](./api-contract.md)
- 온디바이스 AI 상세 → [`./on-device-ai.md`](./on-device-ai.md)
- 배포 전략 → [`./deployment.md`](./deployment.md)
- 제품 비전·범위 → [`../product/vision-and-scope.md`](../product/vision-and-scope.md)
- 기능 명세 → [`../product/features.md`](../product/features.md)
- 태스크 → [`../planning/milestone.md`](../planning/milestone.md)
