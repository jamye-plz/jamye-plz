# Frontend — Claude Guide

This package uses **Bun** as its package manager and script runner
(`bun@1.3.13`, pinned via `packageManager`). Use `bun install` / `bun run dev`
/ `bun add` here — never `npm`/`pnpm`/`yarn`. `bun.lock` is the committed
lockfile; do not introduce a `package-lock.json`.

See [`AGENTS.md`](./AGENTS.md) for the full command list, dev backend wiring
(vite `/api` proxy), and architecture notes.

> Root `CLAUDE.md` / `AGENTS.md` remain the project SSOT — do not edit them.
