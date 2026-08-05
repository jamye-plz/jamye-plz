# Ultrawork Session — M4a 음성 메시지 + STT

- **시작**: 2026-08-05 · **sid**: oma-00msfx7co4nqwu8xaa · **워크플로**: ultrawork
- **요청**: "푸시하지말고 M4a 포함시켜. 그리고 M4a 진행해."
  → main의 미푸시 커밋 2개(`3578acf` docs 정합성, `cd2bd37` notificationclick 수정)를
  **main에 푸시하지 않고 M4a 브랜치에 실어 PR에 포함**시킨다.

## 확정 결정 (선행 세션)

- **D6**: 음성 메시지(M4a)만. WebRTC는 vNext
- **D7**: **faster-whisper (CTranslate2) self-host** — 2026-08-04 비교 확정
- **D8**: **arq + Redis** (내구성 + ws_hub pub/sub 동시 해결)
- alfheim RAM 16GB+ (사용자 확인). 모델 기본 후보 large-v3-turbo int8(디스크 814MB)

## D7 세션에서 넘어온 M4a 주의사항

1. `language="ko"` 강제 — 짧은 클립 언어 오탐/영어 누출 방지
2. 환각 완화 파라미터(vad_filter 등) — 무음 구간 환각은 Whisper 알려진 실패 모드
3. 모델 로드는 로컬 경로/캐시 — 런타임 HF 다운로드 의존 최소화
4. distil-whisper 영어 전용 — 사용 불가
5. uv2nix는 PyPI 휠 사용 — nixpkgs ctranslate2의 OpenBLAS 제약과 별개.
   int8 성능 미달 시 이 지점부터 의심
6. storage.py에 AUDIO MIME 상수 추가 필요

## M4a에 묶기로 한 기술부채

- **#8** `message_media.filename` 컬럼(원본 파일명) — 이번 마이그레이션에 포함
- **#10** `partysocket` 제거 — bun.lock 변경이 어차피 발생(FOD 재해시 1회로 합침)

## 재사용 가능한 M3 산출물

- `message_media` 테이블(+position) — 오디오도 이 테이블로(содержit duration)
- presign 경로 `chat/{chatroom_id}/{uuid4}` + BOLA 가드 + 서버 재검증
- `ChatComposer`/`MessageMedia` 컴포넌트, `uploadChatMedia()` 헬퍼
- WS `send_message` media 프레임, 빈 body 완화

## Phase Log

- Phase 0: 완료 — 리소스 승계, L1 세션 생성
- Phase 1 (PLAN): 완료 — 사용자 확정: 녹음 UX=탭 토글, 모델=large-v3-turbo int8.
  설계 결정: ① type="voice" 없음(음성=오디오 첨부 1개의 일반 메시지, transcript는 message_media에)
  ② ws_hub 전면 pub/sub 전환 안 함(워커→백엔드 단방향 브리지만) ③ faster-whisper는 main deps.
  PLAN_GATE pass
- Phase 2 (IMPL): 완료 — **에이전트 미스폰, 인라인 구현**(이 세션 중단 누적 9회 + M3에서 14만 토큰/0줄 전례.
  VERIFY QA는 스폰함). 커밋: 5300c42(backend) 109b527(frontend) 705d942(infra) 010833a(docs) c0f81b3(notes).
  게이트: pytest **162 passed**(신규 20) / ruff / pyright 0 / flake check OK / 마이그레이션 up·down 렌더 OK
- Phase 3 (VERIFY): 1차 **FAIL** — qa(1회 중단→재개, 세션 10번째): HIGH 1(오디오 캡이 워커 소비 경로에서
  미집행 — byte_size optional + video로 presign한 50MiB를 audio로 재신고 → 단일 워커 10분 DoS 반복 가능),
  MEDIUM 3(enqueue 실패 시 pending 영구 고착 / publish 실패 시 arq가 전체 재작업 / getUserMedia 대기 중
  언마운트 시 마이크 누수), LOW 1(pool 이중 생성 race). **5건 전부 타당 판정 → 근본 원인 수정**(1953669):
  ① 워커 `_download`가 실제 ContentLength를 MAX_AUDIO_BYTES와 대조(권위 있는 집행) + 오디오는 byte_size 필수
  ② enqueue가 bool 반환, 실패 시 pending→NULL 되돌림 ③ 종결 행이면 publish만 재시도 ④ disposed 플래그로
  트랙 즉시 해제 ⑤ asyncio.Lock. 테스트 +3(165 passed). 2차 재검증은 오케스트레이터 인라인 스팟체크
  (각 수정이 시나리오를 막는지 코드로 확인 + 신규 테스트). **VERIFY_GATE pass**
- Phase 4 (REFINE): 인라인 — Step 9: ChatComposer 540줄(>500)은 **정당화**(녹음 상태머신이 composer 상태
  6개와 결합, svelte-check 미실행 환경에서 추출은 리스크만 증가. 더 크면 voice-recorder.svelte.ts 추출 후보).
  ChatRoom 804줄은 M3에서 기존 정당화. Steps 10-13 clean. refine-outcome 기록. **REFINE_GATE pass**
- Phase 5 (SHIP): 백엔드측 완료(165/ruff/pyright/flake). **사용자 대기**: bun remove partysocket,
  프론트 게이트 4종, 실기기 검증(iOS 녹음·전사 파이프라인). SHIP_GATE는 사용자 최종 승인 대기

## EA (Evaluator Accuracy) 이번 세션

- good_catch 1: QA가 오디오 캡 우회(HIGH)를 포착 — 구현 자가점검이 놓침
- false_positive 0 / missed_stub 0 (5건 전부 실제 결함으로 확인)

## 구현 세부 (검증·후속용)

- 마이그레이션 f6a7b8c9d0e1: transcript(TEXT)/transcript_status(16)/filename(255) — 전부 nullable
- 큐: core/queue.py — get_arq_pool(lazy)/enqueue_transcription(흡수)/parse_transcript_event/TRANSCRIPT_CHANNEL
- 워커: workers/transcribe.py — 모델 lazy 싱글턴, max_jobs=1, job_timeout=600, max_tries=3,
  실패 시 status=failed 저장(영구 pending 방지), 커밋 후 publish
- 브리지: main.py _transcript_bridge — 백오프 1→30s, CancelledError 전파, shutdown에서 cancel+close_arq_pool
- 프론트: ChatComposer 탭 토글 녹음(5분 캡, mimeType 협상, teardown에서 트랙 정지),
  MessageMedia 오디오 플레이어+transcript 상태, ChatRoom transcript 프레임 제자리 패치(스크롤 안 함)
- infra: compose redis:8.4, module.nix transcription.*(기본 enable=true), redis-jamye-plz(loopback),
  jamye-plz-stt-worker(HF 캐시 StateDirectory=jamye-plz-stt), frontend.nix fakeHash(partysocket 제거 대기)

## 사용자 실행 대기 항목

1. `cd frontend && bun remove partysocket` (부채 #10 — FOD 해시는 이미 fakeHash)
2. 프론트 게이트: `bunx prettier --write . && bunx eslint . && bun run check && bun run build`
3. 로컬 검증: compose에 redis 추가됨(podman), `uv run poe migrate`,
   워커 `uv run arq app.workers.transcribe.WorkerSettings`(REDIS_URL 설정 시), backend/.env에 REDIS_URL=redis://localhost:6379
