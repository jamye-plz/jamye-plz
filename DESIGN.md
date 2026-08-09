# Jamye Design System

## 1. Visual Theme & Atmosphere

Jamye is a warm, private conversation space for close friends. Its visual language translates Setlog's candid friendship energy from short video into text-first topic sharing: warm paper surfaces, soft pastel states, generous rounded shapes, and a few hand-drawn accents make the product feel personal without competing with the conversation.

The core interface stays calm and highly legible during long chat sessions. Playfulness appears at meaningful moments such as onboarding, empty states, newly created topics, reactions, and successful actions. Functional screens never become a scrapbook, and decorative marks never carry navigation or status meaning.

The system is mobile-first and genuinely adaptive. Mobile presents one clear path at a time. Desktop expands into a conversation board with persistent group navigation, a focused content column, and optional contextual information. Light and dark modes share the same warm, low-chroma identity rather than behaving as simple inversions.

## 2. Color Palette & Roles

### Light Theme

- Warm Paper (#FAF8F4): page canvas and primary base surface
- Clean Sheet (#FFFFFF): raised cards, dialogs, and the composer surface
- Raised Paper (#F5F1EC): secondary surfaces, hover fills, and grouped rows
- Divider Clay (#E8E0D8): decorative dividers and non-interactive card borders
- Ink Plum (#29252D): headings, body copy, and primary icon color
- Muted Aubergine (#665F6B): metadata and secondary copy; 5.8:1 on Warm Paper
- Strong Mauve Border (#918693): input and interactive boundaries requiring 3:1 contrast
- Conversation Berry (#9B3F68): primary action, current selection, focus, and own-message emphasis
- Friend Grape (#5C5595): secondary brand action, topic context, and friend-related emphasis
- Connection Teal (#237667): positive state, connected status, and optional accent action

### Light Pastel Surfaces

- Whisper Blush (#F8E8EE): new-topic and warm-emphasis surface
- Soft Lilac (#F0ECF8): selected context and group identity surface
- Quiet Mint (#E3F1ED): connected, completed, and positive surface
- Butter Note (#FBF3D6): hints, lightweight announcements, and friendly empty-state accents

Pastel surfaces always use Ink Plum text. They are not valid text or icon colors on Warm Paper.

### Dark Theme

- Night Paper (#1C1920): page canvas
- Raised Night (#252129): cards, grouped rows, and composer surface
- Night Divider (#322C36): decorative borders and separators
- Moon Ink (#F4EEF2): headings, body copy, and primary icons
- Muted Moon (#A9A0AE): metadata and secondary copy; 6.89:1 on Night Paper
- Strong Night Border (#776D7C): interactive boundaries requiring 3:1 contrast
- Petal Berry (#E39BB8): primary action and selected state with Deep Berry Ink text
- Lavender Friend (#B7A8E2): secondary brand action and friend context with Deep Grape Ink text
- Seafoam Connection (#83CDBE): connected and positive state with Deep Teal Ink text
- Deep Berry Ink (#2C141F): content on Petal Berry
- Deep Grape Ink (#201A32): content on Lavender Friend
- Deep Teal Ink (#102A25): content on Seafoam Connection

### Dark Pastel Surfaces

- Night Blush (#3C2932): new-topic and warm-emphasis surface
- Night Lilac (#302A42): selected context and group identity surface
- Night Mint (#223A34): connected, completed, and positive surface
- Night Butter (#3D351F): hints and lightweight announcements

### Status Colors

- Clear Blue (#2F6F9F light / #91BFE4 dark): informational state
- Connection Teal (#237667 light / #83CDBE dark): success and online state
- Grounded Ochre (#8B6316 light / #E8C77A dark): warning and attention state
- Clear Red (#B33C48 light / #F2A0A8 dark): error and destructive state

Every status combines color with text, an icon, or a shape. A screen has at most one primary-colored action.

## 3. Typography Rules

Font stack: Pretendard Variable, Pretendard, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif.

| Role            | Font                                          |                     Size | Weight | Line Height | Letter Spacing | Features              | Notes                                |
| --------------- | --------------------------------------------- | -----------------------: | -----: | ----------: | -------------: | --------------------- | ------------------------------------ |
| Brand wordmark  | Custom outlined SVG based on Korean lettering |    28-36px visual height |    n/a |           1 |            n/a | n/a                   | Asset only; never used for UI copy   |
| Page H1         | Pretendard Variable                           | clamp(24px, 2.2vw, 30px) |    700 |         1.3 |        -0.02em | normal                | One per page                         |
| Section H2      | Pretendard Variable                           | clamp(20px, 1.8vw, 24px) |    700 |        1.35 |       -0.015em | normal                | Major content sections               |
| Card title      | Pretendard Variable                           |                     18px |    650 |        1.45 |        -0.01em | normal                | Topic titles; wrap before truncating |
| UI title        | Pretendard Variable                           |                     16px |    650 |         1.4 |        -0.01em | normal                | App bars and dialogs                 |
| Body            | Pretendard Variable                           |                     16px |    400 |        1.65 |              0 | normal                | Minimum mobile body size             |
| Long topic body | Pretendard Variable                           |                     16px |    400 |        1.75 |              0 | normal                | Maximum measure 68ch                 |
| Chat message    | Pretendard Variable                           |                     16px |    400 |        1.55 |              0 | normal                | Preserve natural line wrapping       |
| UI label        | Pretendard Variable                           |                     14px |    600 |         1.4 |              0 | normal                | Buttons, tabs, and compact labels    |
| Dock label      | Pretendard Variable                           |                     12px |    600 |         1.2 |              0 | normal                | Always paired with a Lucide icon     |
| Metadata        | Pretendard Variable                           |                     13px |    500 |        1.45 |              0 | tabular-nums for time | Never use below 12px                 |

Korean body text uses natural tracking and generous line height. Headings may use slightly tighter tracking, but body, chat, input, and button copy never use negative tracking. Dates and times use tabular numerals. Font loading uses swap, and the existing local Fontsource package remains preferred over an additional network font.

## 4. Component Stylings

### Buttons

- Standard height: 48px on touch interfaces and 44px minimum on pointer-first desktop layouts.
- Primary action: Conversation Berry with white text in light mode; Petal Berry with Deep Berry Ink in dark mode.
- Secondary action: transparent or Raised Paper/Raised Night with Ink Plum/Moon Ink.
- Ghost action: transparent until hover or press; never loses its visible focus treatment.
- Radius: 16px for standard buttons, full radius only for compact reaction pills and true circular controls.
- Horizontal padding: 20px standard, 16px compact.
- Icon-only controls: 20px icon inside a minimum 44 by 44px hit target with an accessible name.
- Motion: 150ms color/opacity transition and optional transform scale to 0.98 on press. The press state must not shift surrounding layout.
- Focus: 3px primary ring with a 2px canvas offset.
- Async actions: disable repeated submission, retain the label when possible, and show progress within 100ms.

### Topic Cards and Containers

- Default topic card: Clean Sheet/Raised Night surface, 1px decorative divider, 24px radius, 16px mobile padding, 20px desktop padding.
- Card title appears first; author, time, reaction count, and unread state form a single metadata row.
- A selected or unread card uses a 2px semantic outline plus a text label or dot with an accessible name. Color alone is insufficient.
- Pastel fills are reserved for selected, newly created, or intentionally highlighted cards. Ordinary lists use neutral surfaces.
- The four pastel surfaces may be assigned consistently by group identity, never randomly on each render.
- Cards use natural content height. Do not force equal heights and do not nest complete cards inside other cards.

### Lists

- Groups, members, and notifications use compact scan-oriented rows rather than full content cards.
- Row height: 64px minimum; 72px when an avatar and two text lines are present.
- Row padding: 12px 16px; row gap: 8px.
- Hover uses Raised Paper/Raised Night. Selected rows add a semantic surface plus a visible indicator.
- Text truncation is limited to secondary metadata. Group and topic names wrap where the surrounding layout allows it.

### Badges, Reactions, and Status

- Height: 24px compact, 28px standard.
- Padding: 4px 10px; full radius; label size 13px and weight 600.
- Soft semantic fills are preferred over solid saturated fills.
- User-authored emoji may appear as reaction content. Emoji never replaces a structural navigation or action icon.
- Online state uses a status dot plus visible text or an accessible label.

### Inputs and Composer

- Input and textarea minimum height: 48px.
- Composer textarea grows from 48px to 120px, then scrolls internally.
- Radius: 16px. Resting interactive border uses Strong Mauve Border/Strong Night Border.
- Inline text-and-submit forms keep the input and solid action button as separate controls with an 8px gap and independent 16px radii. This applies to topic creation, nickname changes, and group-name changes; do not join contrasting borders into one segmented pill.
- Placeholder uses Muted Aubergine/Muted Moon and must remain legible.
- Focused inputs, textareas, and selects activate their existing edge with the primary color plus a 1px inset stroke, producing a stable 2px visual border without an outer outline or layout shift. Non-field controls keep the 3px external focus ring. Error uses Clear Red, an inline message, and recovery guidance.
- Labels remain visible for forms. The chat composer may use an accessible name instead of a persistent visible label when surrounding context is unambiguous.
- The composer reserves bottom safe-area space and never hides the final message behind fixed UI.

### Chat

- Incoming messages use neutral raised surfaces; outgoing messages use the primary semantic treatment.
- Bubble radius: 20px with one 8px conversation-side corner. Bubble width: maximum 78% on mobile and 66% on desktop.
- Consecutive messages from one sender use a 4px gap; sender changes use a 12px gap.
- Avatar size: 32px in the conversation, 40px in member lists.
- Message body stays at 16px. Timestamp is 13px with tabular numerals.
- Pending, failed, and sent states include text or an accessible label, not opacity alone.
- System notices are centered compact pills and never imitate user messages.

### Navigation

- Mobile top app bar: 56px content height plus the top safe-area inset.
- Mobile bottom dock: 64px content height plus the bottom safe-area inset. Reserve the same 64px in page content so the dock never covers the final row.
- The dock contains exactly three top-level destinations: Groups, Notifications, and Settings. Every destination uses a 20px Lucide icon plus a persistent 12px label in a minimum 44px hit target.
- Desktop navigation rail: 264px. Optional context panel: 304px. The dock disappears and the rail appears from 1024px.
- Navigation uses solid or nearly opaque surfaces. Backdrop blur up to 8px is allowed only when needed to separate a sticky app bar from scrolling content.
- Current location uses weight, semantic color, and an indicator. Icons always have visible text labels; anchors expose `aria-current` without imitating tab semantics.
- Groups and topics remain hierarchical within the Groups destination and use explicit back navigation. The focused chat route hides the mobile dock so it cannot collide with the software keyboard or composer; its back control remains the exit path.

### Dialogs and Sheets

- Mobile dialogs enter as bottom sheets; desktop dialogs are centered.
- Radius: 24px; padding: 20px mobile and 24px desktop.
- Scrim: rgba(20, 16, 22, 0.52).
- The first heading receives programmatic focus when appropriate, Escape closes non-destructive dialogs, and destructive dialogs always provide a clear cancel action.
- Unsaved content requires confirmation before dismissal.

### Decorative Elements

- Doodles are custom monochrome or one-pastel SVG assets with 1.5-2px strokes.
- Use no more than two decorative marks in one viewport and keep them outside the reading path.
- Decorative assets are hidden from assistive technology.
- The Setlog logo, proprietary illustrations, and exact sticker artwork are not copied.

### Feedback and System States

- Show a content-shaped skeleton when loading is expected to exceed 300ms; reserve final dimensions to prevent layout shift.
- Use an inline, non-blocking offline banner with status text, a Lucide connectivity icon, and a retry action when recovery is possible.
- Empty states explain what belongs on the screen and offer one next action. Error states describe the failure and a concrete recovery path.
- Toasts are reserved for brief confirmations, remain visible for 3-5 seconds, and never contain the only copy of critical information.
- Optimistic messages expose pending and failed states. A failed message keeps its text and offers retry rather than disappearing.

### Motion and Interaction

#### Motion Philosophy and Stack

- Motion explains state change, hierarchy, or continuity. It is never ambient decoration and never delays content or input.
- Use CSS and existing daisyUI state transitions first for hover, focus, press, color, border, and opacity changes.
- Use Svelte-native motion when an element enters or leaves the DOM, a small keyed list changes order, or one continuous value needs interpolation.
- Approved Svelte primitives are `fade`, `fly`, and `scale` from `svelte/transition`; `animate:flip` from `svelte/animate`; and the Svelte 5 `Spring`, `Tween`, and `prefersReducedMotion` APIs from `svelte/motion`.
- `crossfade` is exceptional and limited to a clear same-screen source-to-destination replacement. It is not a default navigation pattern.
- `Spring` and `Tween` are limited to one or two isolated visual values. Do not drive chat lists, scrolling, composer geometry, or continuous gesture updates with them.
- GSAP and comparable general-purpose animation runtimes are outside this system. Do not add one unless a future product requirement cannot be met with CSS or Svelte-native primitives and a measured prototype justifies the bundle and maintenance cost.
- Prefer Svelte transitions that generate CSS/Web Animations. Avoid custom `tick` transitions and frame-by-frame JavaScript unless no declarative primitive can express the interaction.

#### Motion Tokens

| Token                 |                         Value | Primary use                                                |
| --------------------- | ----------------------------: | ---------------------------------------------------------- |
| `--duration-fast`     |                         150ms | press feedback, reaction feedback, exits, and simple fades |
| `--duration-standard` |                         200ms | toast, banner, dialog, and sheet entrances                 |
| `--duration-emphasis` |                         300ms | one-time onboarding or empty-state emphasis only           |
| `--ease-jamye`        | cubic-bezier(0.16, 1, 0.3, 1) | all spatial entrances and exits                            |
| Micro travel          |                         4-8px | badges, toasts, and compact feedback                       |
| Surface travel        |                        8-16px | sheets and dialogs; never full-screen travel               |

- Entrances may use Standard duration; exits use Fast duration so the interface never feels blocked.
- Components consume these canonical tokens instead of declaring arbitrary durations. Do not maintain a second timing scale when the design tokens are integrated into the app.
- Spatial motion uses transform and opacity. Color, background, and border transitions may use CSS but must not be combined with expensive filter effects.
- No more than two or three independently moving elements should be visible at once. Do not apply `will-change` without profiling evidence.

#### Product Motion Matrix

| Moment                           | Primitive                      | Specification                                                                                                     | Reduced-motion behavior                                                         |
| -------------------------------- | ------------------------------ | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Button press                     | CSS                            | scale to 0.98 for 150ms; no layout movement                                                                       | remove scale; keep immediate color or border feedback                           |
| Reaction added                   | Svelte `scale`                 | 0.92 to 1 with its built-in opacity transition for 150ms                                                          | appear immediately with the final selected state                                |
| Toast or offline banner          | Svelte `fly`                   | 8px travel with its built-in opacity transition; 200ms in, 150ms out                                              | zero travel and zero duration; keep status text visible for the same dwell time |
| Mobile bottom sheet              | Svelte `fly`                   | 12-16px vertical travel with its built-in opacity transition; 200ms in, 150ms out                                 | open and close immediately; preserve focus management                           |
| Desktop dialog                   | Svelte `scale`                 | 0.98 to 1 with its built-in opacity transition; 200ms in, 150ms out                                               | open and close immediately; preserve focus management                           |
| Small topic-list reorder         | `animate:flip`                 | 200ms on a keyed list with no more than 30 rendered items                                                         | reorder immediately                                                             |
| New chat message                 | optional Svelte `fade`         | 150ms opacity only; content and status appear immediately                                                         | appear immediately                                                              |
| Date dial                        | Embla-owned transform          | Embla owns gesture and track transforms; an optional single-value `Spring` may move only the selection indicator  | snap the indicator immediately                                                  |
| Onboarding or empty-state doodle | Svelte `in:fade` or `in:scale` | one 300ms entrance, once per view; conditional empty states have no outro so replacement content is never delayed | render the final static illustration immediately                                |
| Route change                     | none by default                | browser navigation, focus, and scroll restoration take priority                                                   | same behavior                                                                   |

`animate:flip` is progressive enhancement and handles reorder only; additions and removals need separate transitions. The final order must be correct without animation. Keep it off the unbounded chat log and any virtualized list. `slide` and `blur` are not approved for chat, topic feeds, or large surfaces because they animate layout or paint-heavy properties.

#### Interaction Reliability and Ownership

- One system owns a moving property. Never let Embla, daisyUI CSS, and a Svelte transition compete for the same `transform` or `opacity`.
- Do not animate composer height, composer bottom position, safe-area insets, `visualViewport` corrections, chat scroll anchoring, or optimistic-message placement. Those values settle immediately from layout and state.
- Do not stagger the chat history, animate every message on initial load, add repeating doodle motion, or introduce route-wide page transitions by default.
- Application correctness never depends on an `introend`, `outroend`, or animation callback. `requestAnimationFrame` can pause when a browser tab or installed PWA is backgrounded, so data and navigation state must complete independently.
- Progress indicators pair motion with visible text or an accessible label. In reduced-motion mode, a static progress treatment is valid.

#### Reduced Motion Contract

- CSS transitions and keyframes remain covered by the global `prefers-reduced-motion: reduce` rule.
- Svelte transitions and Web Animations must also read `prefersReducedMotion.current`; the global CSS duration override is not sufficient for JavaScript-created animation.
- When reduction is requested, pass zero duration and zero travel to transitions, use `{ instant: true }` for `Spring.set`, and use `{ duration: 0 }` for `Tween.set`.
- Respond to preference changes while the app is open. Do not require a reload.
- Reduced motion preserves immediate state feedback, focus movement, status text, and final layout. It removes spatial travel, scale, stagger, and decorative entrances.

#### Mobile and PWA Validation

- Validate every approved pattern in iOS Safari, installed iOS PWA mode, Android Chrome, and installed Android PWA mode on real devices.
- Test while the software keyboard is open, while the conversation is scrolling, after background and resume, and with reduced motion enabled at the operating-system level.
- Profile low-end Android hardware before expanding the matrix. Remove an effect if it causes dropped frames, delayed input, or unstable scroll anchoring.

## 5. Layout Principles

### Spacing System

- Base unit: 4px; primary rhythm: 8px.
- Allowed scale: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 96, 128px.
- Use 4px only for tight internal relationships, 8-12px for component internals, 16-24px for groups, and 32-64px for major sections.
- Prefer gap-based layout over child margins.

### Grid and Containers

- Mobile gutters: 16px.
- Tablet gutters: 24px.
- Desktop gutters: 24-32px.
- Application maximum width: 1360px.
- Primary conversation/topic column: 560-720px, with 720px as the maximum readable width.
- Desktop navigation rail: 264px.
- Desktop context panel: 304px.
- Two-panel gap: 16px. Three-panel gap: 16-24px.

### Adaptive Conversation Board

- Mobile topic views: one active view at a time, ordered as app bar, date/topic controls, topic list, then the bottom dock.
- Mobile chat: app bar, messages, then composer. The bottom dock is intentionally absent while the focused conversation is open.
- Tablet: main content remains dominant and the mobile bottom dock persists until the desktop breakpoint.
- Desktop: persistent navigation rail plus central content.
- Wide desktop: navigation rail, central topic/chat column, and contextual member/topic panel.
- The central conversation column never stretches simply because more viewport width exists.

### Whitespace

- Conversation screens are compact but never cramped.
- Discovery, onboarding, invite, and empty states receive more vertical space and may use one decorative illustration.
- Pastel blocks separate meaning; they do not replace spacing.

### Radius Scale

- Small: 8px for media corners and compact inner elements.
- Medium: 12px for small controls.
- Large: 16px for fields and buttons.
- Extra large: 24px for cards, dialogs, and sheets.
- Full: reactions, status pills, and circular controls only.

## 6. Depth & Elevation

### Shadow Scale

- Elevation 0: none; default lists, chat bubbles, and embedded surfaces.
- Elevation 1: 0 1px 2px rgba(41, 37, 45, 0.06), 0 4px 12px rgba(41, 37, 45, 0.04); topic cards and raised controls.
- Elevation 2: 0 8px 24px rgba(41, 37, 45, 0.10); sticky composer and floating menus.
- Elevation 3: 0 16px 40px rgba(20, 16, 22, 0.18); dialogs and bottom sheets.
- Dark mode uses black at 0.20, 0.28, and 0.40 for the corresponding levels.

All light is treated as coming from above. Do not use double shadows, inset clay effects, or raised 3D text.

### Z-Index Scale

- Base content: 0
- Sticky app bar and composer: 20
- Dropdown and desktop rail overlay: 40
- Full-screen lightbox and temporary overlay: 60
- Dialog and bottom sheet: 80
- Toast: 100
- Tooltip: 120

### Blur and Texture

- Content cards never use glassmorphism.
- Sticky navigation may use up to 8px backdrop blur with a nearly opaque semantic surface.
- No gradient blobs, mesh gradients, or continuous background animation.
- Optional paper texture is limited to onboarding or empty-state artwork and must not reduce text contrast.

## 7. Do's and Don'ts

- DO: Translate Setlog's friendship energy into topic cards, reactions, and lightweight doodles.
- DON'T: Copy Setlog's logo, stickers, camera interaction, or video-first layout.
- DO: Use daisyUI semantic colors and theme tokens in application components.
- DON'T: Place raw hex colors in Svelte templates.
- DO: Keep pastel colors on broad surfaces with Ink Plum or Moon Ink text.
- DON'T: Use low-contrast pastel text or color alone for status.
- DO: Keep one visually dominant action per screen.
- DON'T: Make every button, badge, and icon primary-colored.
- DO: Use Lucide for structural icons and user emoji only as reaction content.
- DON'T: Use emoji for navigation, settings, sending, sharing, or system state.
- DO: Use 16-24px functional radii and deterministic accent assignments.
- DON'T: Randomly rotate functional cards or vary every corner for decoration.
- DO: Use neutral lists for scan-heavy content and cards for shareable topics.
- DON'T: Put cards inside cards or turn every row into a floating panel.
- DO: Use CSS and daisyUI transitions first, then the approved Svelte-native primitives for lifecycle motion and bounded list reordering.
- DON'T: Add GSAP, page-wide transition frameworks, or custom frame loops for the current product scope.
- DO: Keep spatial motion at 150-200ms, reserve 300ms for one-time emphasis, and animate transform or opacity.
- DON'T: Bounce every control, run decorative loops, stagger chat history, or animate layout properties.
- DO: Apply `prefersReducedMotion.current` to Svelte transitions, `Spring`, and `Tween` in addition to the global CSS media query.
- DON'T: Assume the CSS reduced-motion override disables JavaScript-created Web Animations.
- DO: Give each animated property one owner and keep state completion independent from animation completion.
- DON'T: Animate composer geometry, safe-area or keyboard offsets, chat scroll anchors, or Embla-owned transforms.
- DO: Preserve browser back behavior, chat scroll anchoring, optimistic sending, and IME handling.
- DON'T: Trade interaction reliability for visual novelty.
- DO: Design light and dark states together.
- DON'T: Invert the light palette mechanically.

## 8. Responsive Behavior

### Breakpoints

- Mobile: 320-639px; single column, 16px gutters, bottom-sheet dialogs.
- Large phone and small tablet: 640-767px; single column with wider gutters and centered form content.
- Tablet: 768-1023px; single-column content with the bottom dock, 24px gutters, and centered dialogs.
- Desktop: 1024-1279px; persistent 264px navigation rail plus central content.
- Wide desktop: 1280px and above; 264px navigation rail, 560-720px central column, and optional 304px context panel.

### Required Behaviors

- No horizontal page scrolling at any breakpoint.
- Every app shell starts with a keyboard-visible skip link targeting the main content region.
- Touch targets remain at least 44 by 44px.
- Body and chat copy remain at least 16px on mobile.
- App bars, composers, and sheets include safe-area insets.
- Non-chat authenticated pages reserve 64px above the bottom safe-area for the fixed mobile dock. The dock is hidden from 1024px, when the 264px desktop rail becomes persistent.
- The focused chat route never renders the mobile dock; its composer owns the bottom safe-area and visual-viewport correction.
- Lists reserve space for loading media to avoid layout shift.
- Images and video use explicit aspect ratios and responsive sizing.
- Dialogs switch from bottom placement to centered placement at 640px.
- Desktop rails collapse before the central conversation column falls below 560px.
- At 200% browser zoom, optional rails collapse and all primary actions remain reachable without two-dimensional scrolling.
- Landscape mobile keeps the header and composer reachable and prioritizes the message area.
- iOS PWA keyboard handling remains best-effort: the settled state must be correct, and visualViewport-driven code must not be replaced without real-device validation.
- Reduced-motion mode removes spatial travel, scale, stagger, and decorative entrances while preserving immediate state feedback, focus, status text, and final layout. Svelte-native motion must consult `prefersReducedMotion.current`; CSS alone is insufficient.
- Route changes move focus to the main content heading while browser history and prior scroll state remain predictable.

## 9. Agent Prompt Guide

### Quick Color Reference

- Light page canvas: Warm Paper #FAF8F4
- Light raised surface: Clean Sheet #FFFFFF
- Light secondary surface: Raised Paper #F5F1EC
- Light text: Ink Plum #29252D
- Light metadata: Muted Aubergine #665F6B
- Light interactive border: Strong Mauve Border #918693
- Light primary CTA: Conversation Berry #9B3F68
- Light secondary brand: Friend Grape #5C5595
- Light positive accent: Connection Teal #237667
- Dark page canvas: Night Paper #1C1920
- Dark raised surface: Raised Night #252129
- Dark text: Moon Ink #F4EEF2
- Dark metadata: Muted Moon #A9A0AE
- Dark interactive border: Strong Night Border #776D7C
- Dark primary CTA: Petal Berry #E39BB8 with #2C141F text
- Error: #B33C48 light / #F2A0A8 dark
- Focus ring: primary theme color, 3px with 2px canvas offset

### daisyUI Component Selection

- Use navbar for the mobile app bar.
- Use dock for the mobile Groups, Notifications, and Settings destinations; use native anchor semantics, visible icon labels, and `aria-current` for the active location.
- Use a fixed aside with menu-like links for the persistent 264px desktop navigation rail. Keep the dock and rail mutually exclusive at the 1024px breakpoint.
- Do not render the dock on the focused chat route, where the composer and software keyboard own the bottom edge.
- Use card for topics because each topic is a shareable content object.
- Use list and list-row for groups, members, and notifications because those screens prioritize scanning.
- Use chat with chat-start/chat-end for message alignment, avatar for people, badge for reactions and unread labels, and status for connectivity.
- Use textarea plus button for the composer.
- Use native dialog with modal-bottom on mobile and centered placement from the small breakpoint upward.
- Use primary color only for the single most important action; default, ghost, and soft variants carry secondary actions.

### Example Component Prompts

1. Build the adaptive app shell with daisyUI navbar and dock. Use #FAF8F4 light and #1C1920 dark page canvases. On mobile, show a fixed 64px dock plus bottom safe-area with exactly Groups, Notifications, and Settings; pair 20px Lucide icons with visible 12px labels and reserve dock height in page content. Hide the dock on the focused chat route. From 1024px, replace it with a persistent 264px navigation rail; keep a 560-720px center column and add an optional 304px context panel from 1280px. Use 16px mobile gutters and 24px desktop gaps.

2. Build a topic card with daisyUI card. Use #FFFFFF light or #252129 dark, a 1px semantic divider, 24px radius, 16px mobile and 20px desktop padding, and elevation 1. Title uses Pretendard 18px weight 650 line-height 1.45. Metadata uses 13px weight 500. Show author, time, reaction count, and unread state. Use a 2px primary outline plus text for unread or selected state; never use color alone. For a small keyed topic list, use `animate:flip` at 200ms only for reorder and switch to immediate reorder when `prefersReducedMotion.current` is true.

3. Build the conversation with daisyUI chat. Incoming bubbles use a neutral raised surface; outgoing bubbles use #9B3F68 with white text in light mode and #E39BB8 with #2C141F text in dark mode. Use 20px bubble radius with one 8px conversation-side corner, 16px text at line-height 1.55, maximum width 78% mobile and 66% desktop, 4px same-sender gaps, and 12px sender-change gaps. A newly appended message may fade for 150ms, but it appears immediately in state; never stagger history, fly messages vertically, or animate scroll anchoring.

4. Build the composer with daisyUI textarea and button. The textarea grows from 48px to 120px and uses a 16px radius. On focus, recolor its existing border to the primary semantic color and add a 1px inset stroke; do not draw an external field outline. Icon controls have 20px Lucide icons inside 44px hit targets with aria-labels. The send button is the only primary action and may scale to 0.98 for 150ms on press. Reserve bottom safe-area padding and preserve IME composition, optimistic sending, and chat scroll anchoring. Do not animate textarea height, bottom position, safe-area values, or keyboard corrections.

5. Build a responsive dialog with the native dialog element and daisyUI modal. Use bottom placement below 640px and centered placement at 640px and above. The modal surface is #FFFFFF light or #252129 dark, 24px radius, 20px mobile padding, 24px desktop padding, elevation 3, and a rgba(20,16,22,0.52) scrim. Use Svelte `fly` with 12-16px travel on mobile or `scale` from 0.98 on desktop; both primitives already include opacity. Use 200ms in and 150ms out. Set travel and duration to zero when `prefersReducedMotion.current` is true. Include a clear close path, Escape behavior, focus management, and confirmation before discarding unsaved work.

6. Build a playful empty state on the semantic page canvas. Use one custom hand-drawn SVG and one pastel surface only. Heading uses Pretendard 20px weight 700, body uses 16px weight 400, and the primary action is #9B3F68 with white text. Decorative SVGs use 1.5-2px strokes, have empty alt text or aria-hidden, and never substitute for a Lucide action icon. One optional 300ms `fade` or `scale` entrance is allowed per view; never loop it, and render the final static state immediately when reduced motion is requested.

### Iteration Guide

1. Preserve the warm paper canvas and accessible ink contrast in both themes.
2. Keep Pretendard as the only UI font; brand lettering is an SVG asset, not a second font family.
3. Use pastel color for surfaces and state emphasis, never as low-contrast body text.
4. Follow the radius ladder: 8px inner media, 12px compact controls, 16px fields and buttons, 24px cards and dialogs, full radius only for pills.
5. Use cards for topics and lists for scan-heavy rows; use Lucide for structural icons and never create triple-nested surfaces.
6. Use CSS and daisyUI first, then Svelte `fade`, `fly`, `scale`, or bounded `animate:flip`; use 150ms Fast, 200ms Standard, and 300ms Emphasis tokens, and do not add GSAP.
7. Apply `prefersReducedMotion.current` to Svelte-native motion and keep state, focus, keyboard, IME, and scroll behavior independent from animation completion.
8. Mobile is single-path; desktop expands navigation and context without widening the conversation beyond 720px.
