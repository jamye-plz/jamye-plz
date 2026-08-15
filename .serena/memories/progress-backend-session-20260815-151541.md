# Progress: BE-1 — Creator-only topic title update

**Session**: session-20260815-151541
**Agent**: backend
**Started**: 2026-08-15

## Status: completed

## Plan
1. [x] CHARTER_CHECK — read task-board and API contract
2. [x] Inspect existing schema / repository / service / router with Serena
3. [ ] Patch `TopicPatch` schema — add title with strip+validate
4. [ ] Patch `TopicRepository.update` — add title param
5. [ ] Patch `TopicService.update_topic` — add title param
6. [ ] Patch router `patch_topic` — pass title, keep status semantics
7. [ ] Write `backend/tests/test_topic_rename.py`
8. [ ] Run lint + tests

## Files to modify
- backend/app/schemas/topic.py
- backend/app/repositories/topic_repository.py
- backend/app/services/topic_service.py
- backend/app/routers/topics.py
- backend/tests/test_topic_rename.py (new)
