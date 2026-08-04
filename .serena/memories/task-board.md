# Task Board — M3 채팅 미디어 첨부 (사진 + 동영상)

- **session**: oma-00mselrcxefpnxuuo9 · **branch**: `feat/m3-chat-media` (main 분기)
- **결정**: D4 = `message_media` 전용 테이블 / D5 = 직접 재생(mp4) + 크기 제한
- **사용자 확정**: 동영상 상한 **50MiB**, 메시지당 첨부 **최대 4개**

## 공유 API 계약 (BE/FE 동일 준수 — 변경 시 상대에게 알릴 것)

### 1. presign (신규 REST)
```
POST /api/chatrooms/{chatroom_id}/media/presign
auth : require_member_access(chatroom_id, user_id)
body : { "content_type": "image/jpeg", "byte_size": 123456 }
200  : { "object_key": "chat/{chatroom_id}/{uuid4}",
         "upload_url": "...", "expires_in": 900 }
422  : 허용 외 MIME / 크기 초과
```

### 2. WS send_message (확장, client → server)
```jsonc
{ "type": "send_message", "chatroom_id": "...", "client_msg_id": "...",
  "body": "",            // media가 있으면 빈 문자열 허용, 없으면 필수
  "media": [             // 선택. 있으면 1~4개
    { "object_key": "chat/{cid}/{uuid4}", "content_type": "image/jpeg",
      "width": 1024, "height": 768, "byte_size": 123456, "duration": null } ] }
```

### 3. WS message (server → client) 및 히스토리 MessageOut
기존 필드 + `media` 배열:
```jsonc
"media": [ { "id": "...", "url": "<presigned GET>", "content_type": "image/jpeg",
             "width": 1024, "height": 768, "byte_size": 123456, "duration": null } ]
```
`media`는 없으면 `[]`(빈 배열)로 내려간다. 프론트는 항상 배열로 가정해도 된다.

### 4. 허용 MIME / 크기
- 이미지: `image/jpeg`, `image/png`, `image/webp`, `image/gif` — **최대 10MiB**
- 비디오: `video/mp4` — **최대 50MiB** (Cloudflare 100MB 상한 대응으로 하향)

---

## Backend (agent: backend-engineer)

- **B1** 마이그레이션 `message_media` — `down_revision = "c3d4e5f6a7b8"` (현재 head). `message_id` 인덱스. up/down 검증
- **B2** `models/message_media.py` + `Message.media` relationship (`lazy="noload"`, topic_media 미러)
- **B3** `repositories/message_media_repository.py` — `create_many`, `list_by_message_ids`(배치 — N+1 금지)
- **B4** `core/storage.py` — 이미지∪비디오 허용목록 + 종류별 캡 헬퍼. **`MAX_VIDEO_BYTES`를 50MiB로 하향**
- **B5** `schemas/chat.py` — presign req/out, `MessageMediaIn`, `MessageMediaOut`, `MessageOut.media`
- **B6** `routers/chat_media.py` — presign 엔드포인트 (+ main.py 라우터 등록)
- **B7** `services/chat_service.py`
  - `validate_object_key_for_chatroom()` — **BOLA 가드**. `topic_service.validate_object_key_for_topic:195-212`와 동형
    (prefix `chat/{chatroom_id}/` + 단일 세그먼트). 이게 없으면 타 그룹 오브젝트를 자기 메시지에 붙일 수 있음
  - `send_message(..., media=[...])` — 메시지 + 미디어 행을 **한 트랜잭션**에서 생성
  - `list_messages_out()` — 미디어 배치 조회 + `storage.presign_get()` URL 발급
- **B8** `main.py` WS `send_message` (~194-210) — `media` 수용, **`if not chatroom_id or not body` → body OR media 로 완화**,
  응답 payload에 `media` 포함. 서버가 content_type/byte_size **재검증**(클라이언트 값 불신)
- **B9** 테스트 — BOLA 우회 시도, MIME/크기 거부, 4개 초과 거부, 빈 body+미디어 허용, 빈 body+미디어 없음 거부, 히스토리 media 포함

게이트: `uv run pytest` · `uv run ruff check/format` · `npx pyright --project pyrightconfig.json` = 0

## Frontend (agent: frontend-engineer)

- **F1** `lib/types/chat.types.ts` — `ChatMedia` 타입, `ChatMessage.media`, `WsClientMessage`/`WsServerMessage`에 media
- **F2** `lib/api/chat.api.ts` — `presignChatMedia()`. 업로드 헬퍼는 `topic.api.ts:67`의 `uploadToPresignedUrl`을
  **공용 모듈로 추출해 재사용**(중복 구현 금지). `Content-Type` 헤더는 presign 서명과 반드시 일치
- **F3** `lib/components/ChatComposer.svelte` (신규) — 파일 피커(`accept="image/*,video/mp4"`), 최대 4개,
  미리보기 썸네일 + 개별 제거, 클라이언트 사전 검증(MIME/크기), 업로드 오케스트레이션(스피너),
  **일부 실패 시 전송하지 않고 사용자에게 고지**, 업로드 중 전송 버튼 비활성
- **F4** `lib/components/MessageMedia.svelte` (신규) — 버블 내 `<img>` / `<video controls>` 렌더.
  **presigned GET은 600초 TTL이라 채팅을 오래 열어두면 만료됨** → `onerror` 시 히스토리 재조회로 URL 재발급
- **F5** `ChatRoom.svelte` (현재 728줄) — 위 2개 컴포넌트 배선. sendMessage:441에서 media 동봉,
  낙관적 메시지에 로컬 `URL.createObjectURL` 미리보기 → ack 시 교체(`revokeObjectURL` 누수 주의)

게이트: `bunx eslint .` = 0 · `bun run check` = 0/0 · `bunx prettier --check .` · `bun run build` = 0
**주의: bun 명령은 사용자가 직접 실행한다. 에이전트는 bun/podman/uvicorn을 실행하지 말 것.**
프론트 게이트는 사용자에게 실행을 요청하고, 그 전까지는 코드 정확성에 집중할 것.

## 공통 규칙

- 브랜치 `feat/m3-chat-media`에서만 작업. 편집 전 `git branch --show-current` 확인
- 클린 아키텍처: router → service → repository → model. 라우터에 비즈니스 로직 금지
- raw `HTTPException` 금지 — `app/core/exceptions.py`의 커스텀 예외 사용
- UI 문자열 한국어. 내부 네비는 `resolve()` (`$app/paths`)
- 범위 밖 리팩터링 금지. 발견한 무관한 문제는 보고만 할 것

## 알려진 제약 / report-only

- `chat.types.ts`의 `MessageType = 'text' | 'system'`인데 백엔드는 `'user'` — 기존 불일치. 이번에 고치지 말고 보고만
- iOS HEIC(`image/heic`)은 허용목록에 없음. `accept="image/*"`로 iOS Safari가 JPEG 변환하는 경우가 많으나 미보장 → 실기기 확인 항목
- 메시지 삭제 기능이 없어 orphan 미디어 정리는 범위 밖
