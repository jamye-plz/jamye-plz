# Task Board
## Session: session-20260815-151541
## Status: COMPLETED
## Clarification Debt: 0

### BE-1
- **Agent**: backend
- **CLI / Model**: claude / sonnet-4.6
- **Title**: Implement creator-only topic title update API and tests
- **Status**: completed
- **Priority**: P0
- **Dependencies**: frozen API contract
- **File Ownership**:
  - backend/app/schemas/topic.py
  - backend/app/repositories/topic_repository.py
  - backend/app/services/topic_service.py
  - backend/app/routers/topics.py
  - backend/tests/ topic rename tests
- **Description**: Extend the existing topic PATCH path with title updates, preserve body-driven enriched status transitions, enforce group membership and topic authorship server-side, and add meaningful authorization and validation tests.
- **Acceptance Criteria**:
  - PATCH accepts a trimmed non-empty title up to 256 characters
  - title-only changes do not set status to enriched
  - non-author group members receive 403
  - non-members receive 403
  - existing body update behavior remains compatible
  - backend checks pass
- **Domain Tags**: oma-backend, oma-qa
- **Exposed Skill Set**: oma-backend, oma-qa
- **Exposure Fallback**: false
- **Progress**: 6/6

### FE-1
- **Agent**: frontend
- **CLI / Model**: claude / sonnet-4.6
- **Title**: Implement topic-title edit dialog in topic chat and tests
- **Status**: completed
- **Priority**: P0
- **Dependencies**: frozen API contract
- **File Ownership**:
  - frontend/src/lib/api/topic.api.ts
  - frontend/src/lib/components/ChatRoom.svelte
  - frontend/src/routes/groups/[id]/topics/[tid]/chat/+page.svelte
  - frontend/tests/ topic rename tests
- **Description**: Add the rename API call, opt-in creator-only title edit trigger in ChatRoom, and a dedicated dialog matching the existing body editor modal pattern. Preserve generic group chat behavior and invalidate topic-list cache after success.
- **Acceptance Criteria**:
  - only the topic author sees the 44px title edit trigger
  - dialog uses daisyUI modal, input, and button patterns already used by body editing
  - draft initializes from the current title and sends trim()
  - blank titles cannot submit and maxlength is 256
  - success updates the header immediately and invalidates the group topic list
  - Korean accessible labels and error messages are present
  - frontend test, check, lint, and build pass
- **Domain Tags**: oma-frontend, daisyui, oma-qa
- **Exposed Skill Set**: oma-frontend, daisyui, oma-qa
- **Exposure Fallback**: false
- **Progress**: 7/7

### QA-1
- **Agent**: qa
- **CLI / Model**: claude / sonnet-4.6
- **Title**: Cross-review security, accessibility, cache, and regressions
- **Status**: completed
- **Priority**: P1
- **Dependencies**: BE-1, FE-1
- **File Ownership**: read-only review
- **Description**: Review the combined diff and reproduce creator authorization, membership denial, Svelte accessibility, dialog behavior, cache refresh, and generic group-chat regression expectations.
- **Acceptance Criteria**:
  - no authorization bypass
  - no regression in body editing or group main chat
  - accessible 44px trigger and labeled dialog/input
  - all automated checks pass
  - reproducible findings only
- **Domain Tags**: oma-qa, oma-backend, oma-frontend
- **Exposed Skill Set**: oma-qa, oma-backend, oma-frontend
- **Exposure Fallback**: false
- **Progress**: 5/5
