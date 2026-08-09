# Progress — frontend-routes — session-20260806-223529

## Status: completed

## Agent: frontend-routes

## Task
Visual/accessibility refactor of 11 non-chat route files. Branch: fix/design-motion-system.

## Actions taken
1. Confirmed branch: fix/design-motion-system ✓
2. Read task-board.md ✓
3. Read DESIGN.md ✓
4. Read all 11 owned files ✓
5. Implementing changes — in progress

## Files to modify
- `frontend/src/routes/+page.svelte` — redirect-only, no markup change needed
- `frontend/src/routes/groups/+page.svelte`
- `frontend/src/routes/groups/[id]/+page.svelte`
- `frontend/src/routes/groups/[id]/topics/[tid]/+page.svelte`
- `frontend/src/routes/groups/[id]/settings/+page.svelte`
- `frontend/src/routes/groups/[id]/invite/+page.svelte`
- `frontend/src/routes/invite/[code]/+page.svelte`
- `frontend/src/routes/login/+page.svelte`
- `frontend/src/routes/onboarding/+page.svelte`
- `frontend/src/routes/notifications/+page.svelte`
- `frontend/src/routes/settings/+page.svelte`

## Key changes per file
- id="main-content" on each <main>
- max-w-[720px], px-4 sm:px-6 gutters
- bg-[var(--color-surface-raised)] for cards/dialogs
- rounded-xl (24px) cards/dialogs, rounded-lg (16px) fields/buttons, rounded-sm (8px) media
- min-h-16 (64px) for list rows (groups, notifications)
- Topic cards: 18px/650 title, 13px tabular metadata, elevation 1 (shadow-sm)
- Remove btn-sm from icon-only controls (min 44px)
- Empty-state fade with prefersReducedMotion guard
- Toast fly transition with prefersReducedMotion guard
- Preserve all queries, mutations, handlers, API calls
