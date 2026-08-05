# Ultrawork Session — M3 채팅 미디어 첨부 (사진 + 동영상)

- **시작**: 2026-08-04 · **sid**: oma-00mselrcxefpnxuuo9 · **워크플로**: ultrawork
- **요청**: "M3 진행해줘. 채팅미디어는 사진과 동영상을 말해."
- 선행: M0(스토리지 #16) / M1(푸시 #17) / M2(그룹 #18) 완료·배포. D1~D8 전부 확정
- 관련 결정: **D4 = `message_media` 전용 테이블**, **D5 = 직접 재생(mp4) + 크기 제한**

## Phase 0

리소스 8종은 동일 세션에서 D7 작업 시 로드 완료 → 승계. 런타임 Claude Code, 언어 ko.

## 앵커 재확인 결과 (2026-08-04, 로드맵 지시대로 착수 시 재검증)

### Backend
- `alembic` head = **c3d4e5f6a7b8** (group deleted_at) → 신규 마이그레이션 down_revision
- `models/message.py:16-43` — `type` String(8) default **"user"**(user|system), `body` **Text NOT NULL**
- `models/topic_media.py` — 미러 대상. 컬럼: id/topic_id/type/object_key/width/height/byte_size/created_at
- `repositories/message_repository.py:29` — `create(chatroom_id, body, sender_id, client_msg_id, type)`, flush+refresh (commit은 service)
- `services/chat_service.py:61-81` — `send_message()`가 body만 받음. commit 후 refresh
- `services/chat_service.py:120+` — `list_messages_out()` 히스토리 enrich(닉네임/아바타)
- `services/topic_service.py:195-212` — **`validate_object_key_for_topic` BOLA 가드** (prefix + 단일 세그먼트). 채팅용으로 동형 필요
- `services/topic_service.py:52` — `storage.presign_get(m.object_key)` 읽기 URL 발급 패턴
- `routers/media.py:19` — prefix `/groups/{gid}/topics/{tid}/media`, presign은 `assert_author_or_owner`
- `schemas/topic.py:82-133` — MediaPresignRequest/Out/ConfirmRequest/MediaOut + `_check_image_*` validator
- `core/storage.py:27-32` — IMAGE_MIME_TYPES(jpeg/png/webp/gif) 10MiB, **VIDEO_MIME_TYPES {video/mp4} 100MiB (미연결)**
- `main.py:~194-210` — WS `send_message`: **`if not chatroom_id or not body` → 거부** (빈 body 불가). payload에 msg_type 포함

### Frontend
- `lib/types/chat.types.ts` — `MessageType = 'text' | 'system'` ⚠️ **백엔드는 'user'** (기존 불일치, 렌더는 system만 분기해 우연히 동작). report-only
- `lib/api/topic.api.ts:34-80` — presignMedia/confirmMedia/uploadToPresignedUrl (재사용 가능)
- `lib/components/ChatRoom.svelte` — **728줄, 이미 500줄 초과**. sendMessage:441, footer/composer:704-728, 버블:640-700, `messageBody` snippet에서 renderMarkdown
- `routes/groups/[id]/topics/[tid]/+page.svelte:91-104` — 이미지 렌더 블록(`content_type.startsWith('image/')`), 일반화 대상

## 발견한 리스크

1. **Cloudflare 100MB 업로드 상한 vs MAX_VIDEO_BYTES=100MiB(104,857,600B)**
   presigned PUT이 minio.ridewithmin.com(Cloudflare Tunnel)을 통과하므로 상한에 걸린다. 캡 하향 필요.
2. **iOS HEIC** — 아이폰 기본 사진 포맷이 image/heic. IMAGE_MIME_TYPES에 없고 브라우저 렌더도 안 됨.
   `accept="image/*"`면 iOS Safari가 JPEG로 변환하는 경우가 많으나 보장 아님 → 실기기 확인 필요.
3. `ChatRoom.svelte` 728줄에 composer+미디어 렌더를 더하면 악화 → 컴포넌트 추출 필요(REFINE Step 9)

## Phase Log

- Phase 1 (PLAN): 완료. 앵커 재확인(로드맵의 main.py:182→실제 ~198, ChatRoom 688-695→704-728 낡음).
  설계 결정: **confirm 엔드포인트 없음**(FK 때문에 고아 행 → WS 프레임에 메타데이터 동봉, 원자적 생성).
  사용자 확정: 동영상 **50MiB**, 첨부 **최대 4개**. PLAN_GATE pass
- Phase 2 (IMPL): **에이전트 2개 모두 코드 0줄 생산 후 중단** → backend 에이전트 TaskStop 후
  **오케스트레이터가 백엔드/프론트 전부 인라인 구현**. (이 세션 에이전트 중단 누적 8회)

### 구현 완료 (branch `feat/m3-chat-media`)

Backend:
- `alembic/versions/d4e5f6a7b8c9_add_message_media.py` (down_revision c3d4e5f6a7b8, up/down 렌더 검증 완료)
- `models/message_media.py` + `Message.media` relationship + `models/__init__.py` 등록
- `repositories/message_media_repository.py` — create_many / list_by_message_ids(배치)
- `core/storage.py` — CHAT_MEDIA_MIME_TYPES, MAX_MEDIA_PER_MESSAGE=4, `max_bytes_for()`,
  **MAX_VIDEO_BYTES 100MiB → 50MiB**(Cloudflare 100MB 근거 주석)
- `schemas/chat.py` — ChatMediaPresignRequest/Out, MessageMediaIn/Out, MessageOut.media
  ⚠️ 함정 회피: 캡 검증을 `model_post_init`이 아니라 **`model_validator(mode="after")`**로.
  전자는 ValueError가 pydantic에 안 감싸져 **422가 아니라 500**이 남
- `routers/chat_media.py` — `/groups/{gid}/chatrooms/{cid}/media/presign`
  (초안은 `/chatrooms/{cid}/...`였으나 코드베이스 관례에 맞춰 정정)
- `services/chat_service.py` — `validate_object_key_for_chatroom` BOLA 가드,
  `send_message(media=)` 원자적 생성(반환 시그니처 `tuple[Message, list[MessageMedia], bool]`로 변경),
  `media_out()` presigned GET, `list_messages_out` 배치 enrich
- `main.py` — chat_media 라우터 등록, WS media 파싱 + 빈 body 완화.
  ⚠️ `PydanticValidationError` 별칭 import — 앱의 `ValidationError`(AppError 하위)와 혼동하면
  잘못된 예외를 잡아 소켓이 죽음
- `tests/test_chat_media.py` — 25개(BOLA 우회 5종, MIME/크기 재검증, 개수/중복, duration 처리 등)

Frontend:
- `types/chat.types.ts` — ChatMedia/ChatMediaInput, MIME·캡 상수, WsClient/ServerMessage media
- `api/upload.ts` (신규) — `uploadToPresignedUrl` 공용 추출, topic.api.ts는 re-export로 전환
- `api/chat.api.ts` — presignChatMedia + uploadChatMedia(presign→PUT→메타 반환)
- `components/ChatComposer.svelte` (신규 256줄) — 파일 피커, 미리보기, 검증, **all-or-nothing 업로드**,
  IME 229 가드 보존
- `components/MessageMedia.svelte` (신규 59줄) — img/video 렌더 + **onerror 1회 재발급**
- `components/ChatRoom.svelte` — composer 교체, sendMessage(body, media), `refreshMediaUrls()`,
  messageBody snippet이 msg 전체를 받도록 변경

### 게이트

- Backend: **pytest 139 passed** / ruff check·format clean / pyright 0 errors ✅
- Frontend: **미실행** — bun은 사용자가 직접 실행. 정적 검증만 수행
  (잔여 참조 0, 아이콘 존재 확인, 중복 구현 제거 확인)
