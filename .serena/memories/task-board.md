# Task Board — M4a 음성 메시지 + STT

- **session**: oma-00msfx7co4nqwu8xaa · **branch**: `feat/m4a-voice-messages` (main 분기, 미푸시 커밋 2개 포함)
- **결정**: D7=faster-whisper / D8=arq+Redis / 녹음 UX=탭 토글 / 모델 기본=large-v3-turbo int8

## 계약

### 1. 음성 메시지 = 오디오 첨부 1개를 가진 일반 메시지
- `messages.type` 신설 없음. 오디오 media가 있으면 음성 메시지
- **오디오는 다른 첨부와 혼합 불가, 메시지당 1개** (서버 강제)
- `AUDIO_MIME_TYPES` = {audio/webm, audio/mp4, audio/ogg}, `MAX_AUDIO_BYTES` = 15MiB

### 2. message_media 확장 (마이그레이션 1건)
- `transcript TEXT NULL` / `transcript_status VARCHAR(16) NULL` (pending|done|failed, null=비오디오·무전사)
- `filename VARCHAR(255) NULL` (부채 #8 — 모든 첨부 공통, 다운로드 파일명 복원)

### 3. 전사 파이프라인 (env-conditional)
- REDIS_URL 설정 시: send_message 커밋 후 `transcribe(media_id)` enqueue(arq), status=pending
- REDIS_URL 없음: status NULL 유지 = 무전사 fallback (음성 자체는 정상 동작)
- 워커: MinIO fetch → faster-whisper(language="ko", vad_filter=True, int8, to_thread) → DB 갱신
  → Redis publish `jamye:transcripts` {chatroom_id, message_id, media_id, status, transcript}
- 백엔드 lifespan 구독자 → `ws_hub.broadcast({type:"transcript", ...})`. 재연결 백오프, 종료 시 취소

### 4. WS 신규 프레임 (server→client)
`{ "type": "transcript", "chatroom_id", "message_id", "media_id", "status": "done|failed", "transcript": "..."|null }`

## 작업

- B1 마이그레이션 (down_revision = e5f6a7b8c9d0)
- B2 storage.py 오디오 상수 + max_bytes_for 확장
- B3 config(redis_url/stt_model/stt_compute_type) + deps(arq, faster-whisper) + core/queue.py(pool)
- B4 서비스: 오디오 검증(단독·1개), filename 배선, pending 마킹, 커밋 후 enqueue(실패 흡수)
- B5 workers/transcribe.py (모델 lazy 싱글턴, WorkerSettings)
- B6 lifespan Redis 구독자 브리지
- B7 테스트
- F1 types(오디오 상수, transcript 필드, WS 프레임) / F2 composer 녹음(탭 토글, MediaRecorder mimeType 협상, 5분 캡) / F3 오디오 버블+transcript / F4 transcript 프레임 반영 / F5 partysocket 제거(bun은 사용자)
- I1 docker-compose redis / I2 module.nix (queue.createLocally, stt-worker 유닛, STT_* export)
- D1 docs (api-contract, data-model, roadmap, .env.example)

## 규칙
- 편집 전 `git branch --show-current` = feat/m4a-voice-messages 확인
- bun/podman/uvicorn 실행 금지(사용자 직접). 게이트: uv run pytest/ruff/pyright
- faster_whisper import는 워커 태스크 내부에서만(lazy) — API 기동에 영향 금지
