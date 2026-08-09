# Task Board — Pastel Conversation Board Refactor

- **session**: session-20260806-223529
- **branch**: `fix/design-motion-system` (keep; do not create or rename)
- **workflow**: ultrawork
- **phase**: COMPLETE — SHIP approved; draft PR #23 opened; manual device matrix documented for review
- **SSOT**: `DESIGN.md`
- **baseline**: check 0/0; lint clean; build success with existing chunk/PWA warnings
- **constraints**: no GSAP, no new dependency, no API/backend/product-logic changes, keep DESIGN.md synchronized, preserve unrelated untracked files

## Authoritative design contracts

- Keep base `@plugin "daisyui"` with built-in themes disabled, then add `jamye-light` and `jamye-dark` custom theme blocks.
- `base-100` is Warm/Night Paper canvas. Use a separate `--color-surface-raised` token for Clean Sheet/Raised Night cards, dialogs, and composer.
- Radius: 8px=`rounded-sm`, 12px=`rounded-md`, 16px=`rounded-lg` fields/buttons, 24px=`rounded-xl` cards/dialogs.
- Z-index: sticky 20, dropdown 40, full-screen overlay/lightbox 60, dialog 80, toast 100, tooltip 120.
- Each route owns one `#main-content`; the global navigation shell must not introduce a nested `main`.
- Below 1024px: fixed daisyUI dock with exactly Groups, Notifications, and Settings, visible icon labels, semantic active location, and 64px page clearance plus the bottom safe area. Focused chat routes omit the dock.
- From 1024px: 264px persistent navigation rail; center content 560–720px. Chat fixed root offsets by the rail without animating the offset.
- CSS/daisyUI motion first. Conditional empty states use entrance-only Svelte motion with `prefersReducedMotion.current`; no outro may delay replacement content. No route, initial chat history, composer geometry, safe-area, scroll-anchor, or Embla transform animation.
- Do not invent data or behavior (unread counts, selected states, hash-based accents, media aspect ratios) that is absent today.

## Ownership A — foundation-shell (DONE)

Only:
- `frontend/src/app.css`
- `frontend/src/app.html`
- `frontend/vite.config.ts`
- `frontend/src/routes/+layout.svelte`
- `frontend/src/lib/components/AppHeader.svelte`
- `frontend/src/lib/components/AppNavigation.svelte`

Deliver:
- complete custom themes/tokens, raised-surface token, canonical timing/radius/type/elevation/z tokens
- 3px focus, 44px icon targets where globally safe, 150ms press, reduced-motion CSS
- PWA/meta colors
- skip link, adaptive daisyUI mobile dock and desktop rail, semantic current nav, no nested main, and no dock on focused chat routes
- 56px safe-area-aware header with center max 720px

## Ownership B — non-chat-routes (DONE)

Only:
- `frontend/src/routes/+page.svelte`
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

Deliver:
- page landmarks/gutters/max 720px
- list rows for groups/notifications; 24px raised topic/dialog cards
- 16px fields/buttons, 13px metadata, visible form labels, one primary action
- 44px icon controls, accessible states
- entrance-only guarded empty-state motion and dock-aware toast placement
- preserve every query, handler, modal lifecycle, route, and API call

## Ownership C — chat-shared (DONE)

Only:
- `frontend/src/lib/components/ChatRoom.svelte`
- `frontend/src/lib/components/ChatComposer.svelte`
- `frontend/src/lib/components/DateDial.svelte`
- `frontend/src/lib/components/UserAvatar.svelte`
- `frontend/src/lib/components/MediaLightbox.svelte`
- `frontend/src/lib/components/MessageMedia.svelte`
- `frontend/src/lib/components/PushReconciler.svelte`
- `frontend/src/routes/groups/[id]/chat/+page.svelte`
- `frontend/src/routes/groups/[id]/topics/[tid]/chat/+page.svelte`

Deliver:
- rail-aware fixed chat, inner max 720px
- 78% mobile/66% desktop bubbles, 20px/8px corners, 4/12px grouping, 13px time
- raised composer, 48–120px textarea, 44px controls, safe area preserved
- DateDial visual-only changes; Embla owns transforms
- lightbox z60; dialogs z80; media 8px corners without fabricated aspect ratios
- PushReconciler audit-only
- preserve scroll anchoring, optimistic send, IME, WebSocket, visualViewport settling, media/voice behavior

## IMPL gate

- Only owned product files changed
- `bun run check`: 0 errors/0 warnings
- `bun run lint`: clean
- `bun run build`: success
- old timing tokens: 0
- raw Svelte hex: only Kakao brand exception
- no GSAP/new dependency/docs product diff

## VERIFY gate

- Step 6 alignment: PASS
- Step 7 safety: PASS for the application diff; pre-existing build-chain audit backlog documented separately
- Step 8 regression: PASS
- Quality Score: 89.7 (Grade B)
- Browser/real-device matrix: intentionally open for manual SHIP validation because no browser session is connected

## SHIP gate

- Step 14 build gates: PASS (`check` 0/0, lint clean, build success, diff-check clean)
- Step 15 static journey trace: PASS; no runtime/browser claim
- Step 16 cascade review: PASS after canonical modal motion, bottom-dock/rail cascade verification, and visible route-focus remediations
- Step 17 deployment readiness: PASS; package/lock/API/backend/secrets/migrations unchanged
- Independent remediation re-review: PASS, no remaining source finding
- Final technical score: 90.9 (Grade A)
- User-feedback revision: mobile hamburger/drawer replaced by a three-item dock; desktop rail retained; empty-state outro removed; DESIGN.md resynchronized; all static/build gates re-passed
- Composer feedback revision: new-topic input and primary button are separate 16px-radius controls with an 8px gap; the contrasting segmented `join` was removed and all gates re-passed
- Field-focus feedback revision: input/textarea/select focus uses a primary 2px visual edge drawn inside the field; external rings remain only on non-field controls; generated cascade and all gates re-passed
- Publish: commits `be13420` and `cdcce5e` pushed on `fix/design-motion-system`; draft PR #23 targets `main`
- Remaining review note: manual viewport/iOS/Android browser and installed-PWA matrix
- Session status: COMPLETE
