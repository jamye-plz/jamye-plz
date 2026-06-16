# Session: ultrawork — 잼얘좀 (jamye-plz)

## Meta
- Start: 2026-06-16 | Workflow: ultrawork (5-Phase, 11 reviews) | Runtime: Claude Code (Opus) | Lang: ko
- Repo: GREENFIELD. User: 상세논의→정교기획→최적스택→계획기반개발. Multi-pass.
- NOTE: SCM workflow keyword 오탐 무시. oma-voice(STT) 1차 제외로 불필요.

## PRODUCT = 잼얘좀 "재밌는 얘기 좀" / EN "anything interesting?"
지인 기반 lightweight 소셜 플랫폼. 셋로그 벤치마킹. 반응형 PWA 웹.
```
폐쇄 그룹(초대제·소수) [1차, 공개그룹 2차]
├ 일별 타임라인: 잼얘(주제) "시드" 날짜별 누적
│   └ 각 주제: 주제만 먼저(부담0) → 텍스트/사진(1차) enrich
│       └ 주제별 채팅방: 실시간 대화
└ 그룹 메인 채팅방: 일반채팅 + 리마인드 허브
🔔알림 참여유도 · 🫥폐쇄·날것 감성
```

## v1 SCOPE (1차) — LOCKED
- 그룹: 소수 폐쇄(초대제). | 콘텐츠: 텍스트+사진 "시드→enrich". | 타임라인: 일별 누적.
- 채팅: 주제별 방 + 그룹 메인방, 진짜 실시간(WS). | 알림: 리마인드 + Web Push.
- AI(WASM 온디바이스): ①자동 태깅 ②살 붙이기. STT·카드생성·추천·하이라이트 2차+.
- 인증: 카카오+구글 OAuth. | 목표: 실서비스, 지인 규모.

## STACK — self-host 분리형 [거의 확정, 살붙이기 방식만 대기]
- FE: SvelteKit(Svelte5)+Tailwind v4+shadcn-svelte, adapter-static SPA
- BE: Python FastAPI (REST + native WS, router→service→repository)
- DB: PostgreSQL | Storage: MinIO(S3) | Realtime: FastAPI WS + partysocket(socket.io 금지)
- 인증: 자체 카카오·구글 OAuth + JWT(httpOnly 쿠키), 클라가드+FastAPI401 2중
- 알림: Web Push(VAPID 자체, pywebpush, vite-pwa injectManifest). iOS=홈화면추가 PWA만 → 설치유도+인앱 fallback

### AI — WASM 온디바이스 [조사완료]
- 런타임: Transformers.js(@huggingface/transformers, WASM+WebGPU) + wllama(순수 WASM GGUF). **WebLLM 제외(WebGPU 전용=WASM원칙 위배)**. 원칙: 순수 WASM baseline + WebGPU 자동감지 가속(2026 데스크톱~85%).
- 기능1 태깅 ✅GO: multilingual-e5-small(int8 ~118MB, MIT) 임베딩 zero-shot 분류. 순수 WASM 충분.
- 기능2 살붙이기 ⚠️: 비생성(e5 재사용+질문뱅크 추천, 추가다운0, 즉각) vs 생성형(wllama+HyperCLOVAX-SEED 0.5B~1.5B Q4, 350MB~1.7GB, WebGPU권장, 한국어 상업가능 ≤10M MAU). EXAONE=비상업 불가. → **비생성 추천 확정**. 생성형은 2차(WebGPU/네이티브).
- COOP/COEP(멀티스레드 WASM SharedArrayBuffer) → Caddy 헤더. Web Worker 추론 + Cache/OPFS 모델 캐시.

### Deploy — NixOS 하이브리드 [조사완료, 이견 없으면 확정]
- 인프라(PostgreSQL/MinIO/Caddy/Redis) = NixOS native services (services.postgresql+postgresqlBackup / services.minio rootCredentialsFile / services.caddy 자동ACME+WS패스스루 / services.redis).
- 앱(FastAPI/SvelteKit) = podman OCI (virtualisation.oci-containers backend=podman). nix 패키징 마찰 회피. (대안 native: uv2nix/poetry2nix + buildNpmPackage, 마찰 큼)
- 시크릿 agenix→sops-nix(/run tmpfs, EnvironmentFile/rootCredentialsFile로 경로주입, store에 평문금지). 외부=cloudflared 터널. 배포=nixos-rebuild switch --flake --target-host.
- flake 구조: nix/{hosts,modules(postgres/minio/caddy/redis/app/secrets),overlays} + frontend/ + backend/ + packages(jamye-frontend buildNpmPackage, jamye-api).

### FE 라이브러리: adapter-static / @vite-pwa/sveltekit / shadcn-svelte 1.2.x+Bits UI / @tanstack/svelte-query v6 / zod→superforms / partysocket / svelte-easy-crop v5 + browser-image-compression + MinIO presigned / @lucide/svelte / date-fns / paraglide-js.

## Benchmark: 셋로그 [2026-06-16]
친구 비공개 2~4초 영상→자동 하루로그. BeReal 한국형. 알림참여유도·폐쇄그룹·날것감성. → 잼얘좀=얘기본체+채팅대화 핵심(영상 아님).

## Phase progress
- [x] Phase 0: Init.
- [~] Phase 1: PLAN — 스택 FINAL 확정(살붙이기=비생성). PM 정식기획 작성 완료(`.agents/results/plan-oma-00mqg32jdoyw4yp9yy.json` + `task-board` memory). 3종 리뷰(completeness/meta/over-eng) PASS. **PLAN_GATE 사용자 승인 완료**("기획 훌륭해"). docs/ 문서화 완료(README + 8문서: product 2 / architecture 5 / planning 1, 3 에이전트 병렬 작성). PLAN 워크플로우 키워드 오탐 무시. SCM 완료: 브랜치 `docs/v1-plan`, 커밋 `5549c3c`(docs 9파일/1388줄), PR #1(https://github.com/jamye-plz/jamye-plz/pull/1, base main) 생성. docs add 규칙 준수(.serena·plan.json 제외). **구현 미착수(사용자 명시 요청)**. PR 리뷰 반영(REVIEW): Codex 봇 지적 3건 수정 — P1 /api prefix 불일치(api-contract 전 경로 /api 통일 + WS /api/ws), P1 WS 인증(쿼리토큰→httpOnly 쿠키, ADR-4 정합), P2 client_msg_id(messages 컬럼+UNIQUE(sender_id,client_msg_id) 멱등성). + features/tasks /api/me 일관화. 커밋 3e829ad push, 답글 3 + 스레드 resolve 3 완료. PR #1 squash 머지(main `4050bc8`) + 브랜치 정리(로컬/원격 docs/v1-plan 삭제, prune) + 로컬 main 동기화 완료. 이제 docs/가 main에 정식 반영(git상 SSOT). 향후 구현은 새 feat 브랜치에서. 다음: (PR 처리 후) 사용자 go 확인 → `oma_emit plan-approved` + `impl-plan-locked` → Phase 2 IMPL(backend-engineer/frontend-engineer 병렬). 주의: `.agents/results/` gitignored → plan.json은 로컬 전용, docs/가 git상 SSOT.
  - PM PLAN: req명세→데이터모델→REST+WS API계약→task분해→completeness/meta/over-eng 3리뷰 → plan-{sid}.json + task-board.md → PLAN_GATE(user) → emit plan-approved & impl-plan-locked.
- [ ] Phase 2 IMPL / 3 VERIFY / 4 REFINE / 5 SHIP.

## Still open (PM PLAN)
- 데이터모델(user/group/membership/invite/topic/topic_media/tag/chatroom/message/push_subscription), REST API 계약, WS 프로토콜(메시지타입/방참여/presence), 권한정책(서비스레이어), AI web worker 통합, Docker/podman 이미지, flake 작성, FastAPI 구조, monorepo(frontend/+backend/+nix/) 단일 repo 권장.
