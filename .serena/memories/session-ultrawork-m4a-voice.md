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
