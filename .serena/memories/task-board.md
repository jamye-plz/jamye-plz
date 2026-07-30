# Task Board — ultrawork v2 (sid oma-00mrraurqqfch0nkha)

## Milestone: M0 — Object Storage Enabler
Branch: `feat/m0-object-storage` (roadmap doc included in this first PR)
Plan: `.agents/results/plan-oma-00mrraurqqfch0nkha.json`

| ID | Task | Agent | Status |
|----|------|-------|--------|
| M0-T1 | infra: MinIO service in podman compose (+infra/.env.example) | backend | done |
| M0-T2 | core/storage.py — boto3 presign_put/presign_get/ensure_bucket, env-conditional fallback | backend | done |
| M0-T3 | media.py real presign + MIME allowlist/size cap validation | backend | done |
| M0-T4 | to_topic_out read path → presigned GET | backend | done |
| M0-T5 | main.py lifespan ensure_bucket (warn-only) | backend | done |
| M0-T6 | tests: test_storage.py (stubbed boto3) + schema validation | backend | done |
| M0-T7 | docs sync (api-contract.md, .env.example), roadmap status | docs | done |

M0 게이트: PLAN ✅ / IMPL ✅ / VERIFY ✅(2차, BOLA 등 6건 수정) / REFINE ✅ / SHIP QA ✅ — 사용자 최종 승인 대기

## Queue after M0
- M1 Web Push (VAPID) — 병렬 가능
- M2 그룹 관리 → M3 채팅 미디어 → (D7 STT 비교 리서치) → M4a 음성
