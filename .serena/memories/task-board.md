# Task Board — 잼얘좀 v1 (session oma-00mqg32jdoyw4yp9yy)

Status legend: ⬜ todo · 🟦 in_progress · ✅ done · ⛔ blocked
Plan: `.agents/results/plan-oma-00mqg32jdoyw4yp9yy.json`

## P0 — 기반 (병렬 시작 가능: T1, T5)
- ⬜ T1 [기반] 모노레포 구조 + nix flake devshell + podman 이미지 스캐폴딩 · deps: —
- ⬜ T2 [기반] FastAPI 구조(router/service/repository) + Postgres + Alembic · deps: T1
- ⬜ T3 [기반] 데이터 모델 마이그레이션(전체 엔티티) · deps: T2
- ⬜ T4 [E1] 카카오·구글 OAuth + JWT(httpOnly) + /me + 프로필 · deps: T3
- ⬜ T5 [기반] SvelteKit(adapter-static SPA)+Tailwind+shadcn-svelte+PWA+인증가드 · deps: T1

## P1 — 핵심 기능
- ⬜ T6 [E2] 그룹 CRUD + 멤버십 + 초대코드/링크 + 권한 · deps: T4,T5
- ⬜ T7 [E3] 잼얘 시드 등록 + enrich(텍스트) + 일별 타임라인 · deps: T6
- ⬜ T8 [E3] 사진 업로드(MinIO presigned + 크롭/압축) · deps: T7
- ⬜ T9 [E5] WebSocket 인프라(FastAPI WS + partysocket + 방참여/메시지/ack) · deps: T4,T5
- ⬜ T10 [E5] 주제별 채팅방 + 그룹 메인 채팅방 + 메시지 영속/히스토리 · deps: T9,T7
- ⬜ T11 [E5] 리마인드 시스템(새주제/첫채팅→시스템메시지+알림 트리거) · deps: T10
- ⬜ T12 [E3] WASM 자동 태깅(Transformers.js+e5-small, Web Worker, 캐싱, COOP/COEP) · deps: T5,T7
- ⬜ T13 [E5] WASM 살붙이기 비생성 추천(질문뱅크+e5 임베딩, 모델 공유) · deps: T12
- ⬜ T14 [E6] Web Push(VAPID+pywebpush)+인앱 알림+iOS 설치유도 · deps: T4,T5,T11

## P2 — 배포·마감
- ⬜ T15 [배포] NixOS flake(인프라 native + 앱 podman)+agenix+Caddy+cloudflared · deps: T6,T8,T10,T14
- ⬜ T16 [QA] 통합 테스트 + 핵심 플로우 E2E + 배포 검증 · deps: T15

## IMPL 병렬 배치 (PLAN_GATE 통과 후)
- Backend 트랙: T1→T2→T3→T4 → T6 → T7 → T9 → T10 → T11 → T14(서버) → T15
- Frontend 트랙: T5 → (T6 UI) → T7 UI → T8 → T9 클라 → T10 UI → T12 → T13 → T14(클라)
- 동기 지점: T6(그룹), T10(채팅), T14(알림)에서 FE/BE 계약 합치
