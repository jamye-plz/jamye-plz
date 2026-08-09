# Final design direction: Pastel Conversation Board

- User selected direction B, Pastel Conversation Board.
- Product remains a Korean-only closed-group text topic and chat PWA for desktop, iOS browser/PWA, and Android browser/PWA.
- Setlog is a mood benchmark only: warm paper canvas, soft pastels, large rounded surfaces, sparse doodles, and close-friend energy. Do not copy its logo, proprietary stickers, video layout, or camera gestures.
- Core interaction translation: text topic card -> quick friend reaction -> real-time conversation.
- Mobile uses one active path. Desktop expands to a 264px group rail, 560-720px central conversation column, and optional 304px context panel at 1280px+.
- WCAG 2.2 AA is the target. Keep 44px touch targets, visible focus, skip link, non-color status cues, reduced motion, 200% zoom behavior, and real-device PWA checks.
- Keep Pretendard, Lucide, daisyUI semantic components, safe areas, IME handling, optimistic send, chat scroll anchoring, and best-effort settled-state iOS visualViewport behavior.
- Handoff artifacts: `DESIGN.md`, `.design-context.md`, `design-system/tokens.css`, and `design-system/AUDIT.md`.
- Proposed custom daisyUI themes are `jamye-light` (default) and `jamye-dark` (prefersdark). The token file is not imported into the app yet.
