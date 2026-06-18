# ultrawork session — Nix deployment pipeline (pre-M1)

- Started: 2026-06-18
- Workflow: ultrawork (PLAN phase first — user asked for a proposal before implementation)
- User request: build a Nix-based deploy pipeline to ship FE/BE/infra to an existing
  NixOS homelab server, from the current minimal state. Propose method first.

## Project facts (verified)
- Frontend: SvelteKit + adapter-static (fallback: index.html) → pure static output (frontend/build/).
  Bun 1.3.13. PWA service worker (@vite-pwa/sveltekit).
- Backend: FastAPI, Python >=3.12, uv + uv.lock present. Entry: uvicorn app.main:app.
  Serves /api/* + WebSocket /api/ws. Alembic migrations (poe migrate = alembic upgrade head).
  Deps include asyncpg, boto3 (MinIO), pywebpush, python-jose.
- Infra today: dev-only Postgres 18 via infra/docker-compose.yml (podman). MinIO + VAPID
  deferred to M1+ (oma-deferred markers in backend/.env.example).
- Secrets needed: JWT_SECRET, KAKAO_*, GOOGLE_*, MINIO_*, VAPID_*, DATABASE_URL.
- Target: single homelab host already running NixOS.

## Status: PLAN — awaiting user decisions on architecture forks (PLAN_GATE).
