# Work Session — Extend input focus style to 4 inputs (2026-07-18)

- **Request**: Apply the chat composer's focus style to 4 more inputs (the "전체 확장"
  that the prior composer session — commit e248b32 — explicitly deferred).
- **Reference style** (ChatRoom.svelte:632 composer): `focus:border-primary focus:outline-none!`
  - `!` on outline-none is REQUIRED: app.css has a global UNLAYERED `:focus-visible` outline
    rule that plain utilities can't override (confirmed by prior session).
- **Domain**: frontend only (single domain → direct implementation, no PM/spawn overhead).

## Targets (add `focus:border-primary focus:outline-none!`)
| # | 입력창 | 파일:줄 | 현재 class |
|---|--------|---------|-----------|
| 1 | 새 주제 던지기 input | routes/groups/[id]/+page.svelte:152 | `input join-item flex-1` |
| 2 | 채팅방 본문 추가/수정 textarea | routes/groups/[id]/topics/[tid]/chat/+page.svelte:89 | `textarea w-full resize-none` |
| 3 | 마이페이지 닉네임 input | routes/settings/+page.svelte:101 | `validator input join-item flex-1` |
| 4 | 새 그룹 만들기 그룹 이름 input | routes/groups/+page.svelte:117 | `validator input w-full` |

## Phase Log
- [x] Step 1 analyze: reference style + 4 targets located (native grep; serena unavailable this runtime)
- [x] Full input sweep: found 1 EXTRA input (onboarding nickname) beyond the listed 4 → 5 total.
      Confirmed complete: login = OAuth buttons only, invite pages = no text inputs.
- [x] Step 3 user confirmation ("진행해") + plan-approved emitted.
- [x] Implement: added `focus:border-primary focus:outline-none!` to all 5 inputs (each +1/−1).
- [x] Verify: 6 files now carry the utility (composer + 5); prettier clean; check 8/0 baseline;
      build exit 0; generated CSS confirms `.focus\:outline-none → outline-style:none!important`.
- [x] Inline QA: WCAG 2.4.7 focus-visible preserved (border-color indicator, same as composer);
      no logic/security/perf impact.
- **Commit `0ae63f6`** style(frontend): apply composer focus border style to remaining inputs (5 files).
- Status: COMPLETED. Left for user: visual confirm on device (border→primary, no blue ring).

---

# Work Session 2 — Topic body → header toggle (2026-07-18)

- **Request**: Make topic (pinned) body a toggle. No body/first-created → show "본문 추가"
  button in the header next to the WS indicator. Body exists → chevron next to title;
  press to reveal body right below. File: ChatRoom.svelte (per-topic chat only).
- **Domain**: frontend, single file. User confirmed ("진행해"). plan-approved emitted.
- **Implementation** (ChatRoom.svelte):
  - import ChevronDown; `let bodyOpen = $state(false)` (collapsed default) + reset on room change
    via `if (chatroomId !== bodyOpenRoom)` guard (NOT a bare `chatroomId;` expr — avoids no-unused-expressions).
  - Header: chevron toggle next to title `{#if pinnedBody}` (rotates 180° on open, aria-expanded/controls);
    "본문 추가" button before the status dot `{#if canEditPinned && !pinnedBody}`.
  - Body panel below header only `{#if pinnedBody && bodyOpen}` (id=topic-body) → rendered body + "수정"
    (canEditPinned). Removed the "아직 본문이 없어요" empty state.
  - Group main chat unaffected (no pinnedBody/canEditPinned passed).
- **Verify**: prettier clean, eslint exit 0 (no suppression drift), check 8/0 baseline, build exit 0.
- **Commit `3f49930`** feat(frontend): toggle topic body from the chat header (1 file).
- Status: COMPLETED. Left for user: device verify 4 states (no-body author / no-body non-author /
  body author expand+수정 / body non-author expand).

---

# Work Session 3 — Composer initial height = 1 line (2026-07-18)

- **Request**: Fix chat composer initial size to 1 line. User confirmed ("진행해").
- **Root cause**: daisyUI `.textarea` sets `min-height:5rem` (~4 lines), overriding `rows={1}` and
  the auto-grow effect (which sets inline `height` but can't beat the min-height floor).
- **Fix**: add `min-h-0` to the composer textarea class (ChatRoom.svelte) → utilities layer beats
  daisyUI component min-height → rows=1 + auto-grow govern height → starts 1 line, still grows to max-h-40.
- **Verify**: prettier clean, eslint 0, check 8/0 baseline, build 0, `min-height:0` present in generated CSS.
- **Commit `82bd0da`** style(frontend): start chat composer at a single line (1 file, +1/−1).
- Status: COMPLETED. Left for user: device visual confirm (composer opens 1 line, grows on typing).

---

# Work Session 4 — Chat screen safe-area spacing (2026-07-18)

- **Request**: (1) composer input+send too close to display bottom (home indicator intrudes) →
  move up, keep width. (2) header back button + status indicator too close to L/R edges →
  inset a little, responsive edge spacing (not fixed width). User confirmed ("진행해").
- **Root cause**: viewport meta lacked `viewport-fit=cover` → iOS returns 0 for env(safe-area-inset-*),
  so the composer's existing `pb-[calc(0.75rem+env(safe-area-inset-bottom))]` and header
  `pt-[env(safe-area-inset-top)]` were inert.
- **Fix** (2 files):
  - app.html: viewport meta += `viewport-fit=cover` → activates safe-area env everywhere → composer
    lifts above home indicator (width unchanged), header top clears status bar.
  - ChatRoom.svelte header: `pl/pr = max(0.75rem, env(safe-area-inset-left/right))` (responsive edge
    spacing) + removed back button `-ml-2` (was pulling it flush) → back/status inset from edges.
- **Verify**: prettier clean, check 8/0 baseline, build 0, safe-area-inset-{bottom,left,right} present in CSS.
- Note: viewport-fit=cover is global; only chat has a fixed bottom element (handled). Other pages scroll
  → minimal impact; add safe-area to them later if needed.
- **Follow-up (device test)**: with the keyboard OPEN, the safe-area-inset-bottom padding left a big gap
  between the composer and the keyboard. Fix: derive `keyboardOpen` (window.innerHeight vs
  visualViewport.height > 100) in the viewport effect; footer pb = `pb-3` when open, else
  `pb-[calc(0.75rem+env(safe-area-inset-bottom))]` → input flush on keyboard when open, above home
  indicator when closed.
- **Commit `5bc63fe`** (amended 357c439) fix(frontend): respect device safe areas on the chat screen (2 files).
- Verify: prettier clean, eslint 0, check 8/0 baseline, build 0.
- Status: COMPLETED. Left for user: device confirm (keyboard-open = input flush on keyboard;
  keyboard-closed = input above home indicator; header inset from edges).

---

# Work Session 5 — Header edge spacing on all screens (2026-07-18)

- **Request**: The header L/R edge spacing was applied only to ChatRoom. Apply the same to the other
  screens (group list, topic list, notifications, settings, etc.).
- **Finding**: no shared header component — each page inlines an identical
  `<header class="navbar sticky top-0 z-10 border-b border-base-300 bg-base-100/80 backdrop-blur">`.
  Anchor `bg-base-100/80 backdrop-blur` appears in exactly 6 headers, nowhere else (ChatRoom differs).
- **Fix** (6 files): added `pl-[max(0.75rem,env(safe-area-inset-left))] pr-[max(0.75rem,env(safe-area-inset-right))]`
  to all 6 headers (settings, groups, groups/[id], groups/[id]/invite, groups/[id]/topics/[tid],
  notifications) + removed the back button `-ml-2` (5 pages that have one; groups list has none) —
  matching ChatRoom. Applied via perl cross-file replace (identical strings, verified scope).
- **Verify**: prettier clean, eslint 0 (no suppression drift), check 8/0 baseline, build 0, 6/6 headers confirmed.
- **Commit `e325c0c`** style(frontend): inset all screen headers from the display edges (6 files).
- Note: top safe-area (pt) intentionally NOT copied — those pages are normal-flow (different top context
  than the fixed ChatRoom); user asked for L/R only.
- Status: COMPLETED. Left for user: device visual confirm across screens.

---

# Work Session 6 — Header top safe-area alignment (2026-07-18)

- **Request**: headers still "제각각"; not just L/R but top/bottom must align.
- **Diagnosis**: after viewport-fit=cover, the 6 page headers (normal-flow) went full-bleed UNDER the
  notch (no pt), while ChatRoom's header had `pt-[env(safe-area-inset-top)]` → top position mismatch.
  On mobile that was the only remaining diff (shrink-0 irrelevant; inner max-w-2xl mobile-invisible).
- **Fix** (6 files): added `pt-[env(safe-area-inset-top)]` to all 6 page headers (perl insert after
  `bg-base-100/80 ` anchor + prettier). Now every header shell = ChatRoom's (pt+pl+pr safe-area,
  navbar vertical padding, border-b) → top/bottom/left/right aligned on mobile.
- **Verify**: check 8/0 baseline, eslint 0, build 0, 6/6 headers have pt.
- **Commit `68901df`** style(frontend): align header top safe-area across all screens.
- **Recurring drift note**: headers are duplicated across 7 files (6 pages + ChatRoom) with no shared
  component → each safe-area addition had to be propagated manually (2 sessions of "headers inconsistent").
- **User chose: extract shared AppHeader component** → done in Session 7.
- Commits `e325c0c` (L/R) + `68901df` (top) — later superseded by the AppHeader shell (single source).

---

# Work Session 7 — Extract shared AppHeader (2026-07-18)

- **Decision**: user picked "공용 AppHeader 컴포넌트 추출" to end recurring header drift.
- **Done**: created `lib/components/AppHeader.svelte` = the sole navbar shell (sticky top-0 z-10 shrink-0
  border-b bg-base-100/80 backdrop-blur + pt/pl/pr device safe-area insets) with a `children` Snippet slot.
  Refactored all 7 headers (6 pages via perl multi-line replace + import; ChatRoom via Edit) to
  `<AppHeader><div inner-row>…</div></AppHeader>`. Each screen keeps its own inner row layout; the shell
  is defined once.
- **Verify**: only AppHeader.svelte matches `class="navbar sticky top-0"` now (single source confirmed);
  prettier clean, check 8/0 baseline, eslint 0, build 0.
- **Commit `8fc3449`** refactor(frontend): extract shared AppHeader for one header shell (8 files).
- Status: COMPLETED. Future header/safe-area changes = edit AppHeader once → all screens.

---

# Work Session 8 — Header inner content consistency (2026-07-18)

- **Request**: group-list "내 그룹" title looks more left than back-button pages; icons look different size.
- **Findings**: (1) group-list h1 was `text-lg` — all other titles `text-base`. (2) group-list action
  wrapper `gap-2` vs others `gap-1`. (3) icons ALL h-5 w-5 (no real size diff — the perceived diff was
  title size + icon gap). (4) back buttons had lost `-ml-2` (removed 2 sessions ago) so the back icon sat
  right of the title's left margin, making "내 그룹" (at content-left) look comparatively further left.
- **Fix** (7 files): group-list title text-lg→text-base + gap-2→gap-1; restore `-ml-2` on all 6 header
  back buttons (perl, targeted via `aria-label="뒤로 가기"`) so the back icon aligns with the content-left
  margin = where titles/"내 그룹" sit → leftmost header content aligns across screens. `-ml-2` still inset
  from screen edge (header pl-safe-area 0.75rem provides the inset).
- **Verify**: 7/7 titles text-base (0 text-lg), prettier clean, check 8/0 baseline, eslint 0, build 0.
- **Commit `e795abe`** style(frontend): unify header title size, icon gap, and back-button alignment.
- Status: COMPLETED. Left for user: device confirm titles/icons align across screens.
