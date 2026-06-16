# Frontend — Agent Guide

SvelteKit (Svelte 5) SPA. Scope: `frontend/` only. Root `AGENTS.md` / `CLAUDE.md`
are the project SSOT — do not edit them from here.

## Package Manager: Bun (required)

This package uses **Bun** as the package manager and script runner.
`bun@1.3.13` is pinned via the `packageManager` field in `package.json`.

- **Lockfile**: `bun.lock` is the single source of truth. Commit it.
- **Do NOT** use `npm` / `pnpm` / `yarn` here, and do not commit a
  `package-lock.json` / `pnpm-lock.yaml` / `yarn.lock` — mixing lockfiles
  causes dependency drift across machines.
- Bun ignores `.npmrc`'s `engine-strict` (npm-only); registry settings still apply.

## Commands

| Task | Command |
|------|---------|
| Install deps | `bun install` |
| Add a dependency | `bun add <pkg>` / `bun add -d <pkg>` (dev) |
| Remove a dependency | `bun remove <pkg>` |
| Dev server (port 5173) | `bun run dev` |
| Production build | `bun run build` |
| Preview built SPA | `bun run preview` |
| Type/Svelte check | `bun run check` |

> The bundler is still **Vite** — Bun only manages packages and spawns the
> scripts, so build output is identical to an npm-based run. If a script ever
> misbehaves under Bun, fall back to `bunx vite <cmd>`.

## Dev Backend Wiring

- `vite.config.ts` proxies `/api` (incl. WebSocket, `ws: true`) to the FastAPI
  backend at `http://localhost:8000`, so the httpOnly auth cookie stays
  same-origin (`localhost:5173`). Start the backend before `bun run dev`.
- All client calls go through `src/lib/api/client.ts`, which prefixes `/api`
  and sends `credentials: 'include'`.

## Architecture

- SvelteKit + `adapter-static` (SPA fallback to `index.html`).
- Tailwind v4 (`@tailwindcss/vite`) + Pretendard.
- Data fetching via `@tanstack/svelte-query`; realtime chat via `partysocket`.
- PWA is temporarily disabled (vite 8 / `@vite-pwa/sveltekit` incompatibility —
  see the TODO in `vite.config.ts`).
