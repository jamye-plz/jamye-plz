# Ultrawork Session — D7 STT 엔진 확정

- **시작**: 2026-08-04 (Asia/Seoul)
- **sid**: oma-00msejznwkjrkfruwx
- **워크플로**: ultrawork (5-Phase Gate Loop)
- **요청**: "D7 먼저 진행할게. STT 엔진을 먼저 확정하자"

## 배경 (from `mem:session-ultrawork-v2-roadmap`)

- v2 로드맵 §7 Open Decisions 중 **D7만 미확정**. 나머지 D1~D6/D8 확정 완료.
- 사용자 지정 판단 기준(kickoff 시): **sherpa-onnx vs faster-whisper 비교 —
  ① 정확도 ② 한국어 호환성 ③ jamye-plz 적합성**
- 로드맵 원래 권장안은 `faster-whisper self-host`였으나 사용자가 보류하고 비교 요구.
- 연관 확정 사항: D6 = 음성 메시지(M4a)만, WebRTC는 vNext / D8 = arq + Redis
- M0~M2 + 인프라 배선 완료·배포됨. M3(채팅 미디어) 미착수.

## 산출물 성격

이 세션의 deliverable은 **코드가 아니라 결정(D7)**이다.
PLAN 단계에서 근거 있는 비교 → PLAN_GATE에서 사용자 확정 → 로드맵 §7 반영.
M4a 구현은 별도 세션.

## 제약

- 사용자가 podman/uvicorn/bun 명령을 직접 실행 (에이전트 실행 금지)
- 배포 타깃: alfheim (NixOS 홈랩, tailnet)
- 백엔드: FastAPI + uv, Python. 비동기 job은 arq+Redis (M4a에서 도입)

## Phase Log

- Phase 0 (Init): 완료 — coordination/context-loading/memory-protocol/event-spec/
  multi-review-protocol/quality-principles/phase-gates/vendor-detection 로드,
  언어=ko, 런타임=Claude Code(native subagent), model_preset=claude
- Phase 1 (PLAN) 진행 중 — 근거 수집

## 로컬 확정 제약 (오케스트레이터 직접 검증)

- 백엔드 패키징 = **uv2nix**(`infra/backend.nix`): `python312` 고정, `sourcePreference="wheel"`,
  `pyprojectOverrides` 확장 지점 존재(선례: `http-ece`에 setuptools 주입)
- **uv2nix는 uv.lock의 PyPI 휠에서 빌드** — nixpkgs python3Packages를 쓰지 않는다.
  → nixpkgs 빌드 플래그 이슈는 "nixpkgs 패키지를 쓸 때만" 해당. 경로 선택이 갈림.
- nixpkgs(고정 rev 567a49d) 보유: sherpa-onnx 1.13.2 / faster-whisper 1.2.1 /
  ctranslate2 4.7.2 / onnxruntime 1.26.0 / av 17.0.1 / tokenizers 0.22.2 — 단 python3.13 빌드
- **ctranslate2 nixpkgs 플래그 직접 확인**: withMkl=false, withOneDNN=false,
  withOpenblas=true, **withRuy=true**. oneDNN+OpenBLAS 동시 활성은 upstream #1294로 broken.
  → Ruy는 int8 전용 GEMM이므로 "int8 무조건 float32 폴백"은 과장. x86-64 최적 경로가 아닐 뿐.
- 백엔드 의존성 현재 12개(매우 가벼움) → STT 전이 의존성 규모가 실질 비용
- `messages.type` = String(8) → "voice" 수용 OK. `body` NOT NULL(M3 빈 body 완화와 연동)
- 프로젝트 원칙 `on-device-ai.md:9` "외부 AI API 의존 제거" → 클라우드 STT 배제, 두 후보 모두 정합
- M4a는 **배치/오프라인** 전사(arq 워커). 스트리밍 불필요 → sherpa-onnx 최대 강점이 무의미
- storage.py에 AUDIO MIME 상수 없음(IMAGE/VIDEO만) → M4a에서 추가 필요

## 리서치 상태

- faster-whisper 리서치: 완료(1회 중단 후 재개). 핵심 공백 = **한국어 CER/WER 수치 전무**
- sherpa-onnx 리서치: 재개 후 대기 중
- 한국어 정확도 전용 리서치: 추가 스폰(Whisper 논문 Appendix, icefall RESULTS.md, HF 한국어 파인튜닝 모델카드 baseline 타깃)

## 리서치 결과 요약

### faster-whisper
- 라이선스 전부 MIT(faster-whisper/CTranslate2/Whisper 가중치)
- 의존성 5개(ctranslate2, huggingface-hub, tokenizers, onnxruntime, av, tqdm) — 전부 cp312 manylinux 휠
- **오프라인 배포 지원**: `WhisperModel(로컬디렉터리)` 분기 존재 + `local_files_only=True`
- **distil-whisper는 영어 전용** → 한국어 경량화 우회로 없음
- CPU 벤치 1점만: small/int8/8스레드 i7-12700K → RTF 0.131, RAM 1477MB
- Whisper 자체가 구두점·대소문자 포함 출력(디코더 생성물)
- `language="ko"` 강제로 짧은 오디오 언어 오탐 회피 가능
- 환각/반복 이슈 다수(83건 hallucination, 37건 repetition) — 완화 파라미터 5종 노출
- 유지보수: 태그 릴리스 ~9개월 정지(v1.2.1 2025-10-31), 이슈 314. CTranslate2는 활발(4.8.1 2026-07)
- nixpkgs ctranslate2는 OpenBLAS만(oneDNN/MKL off) → int8 가속 불확실. **단 uv2nix는 PyPI 휠 사용이라 별개**

### sherpa-onnx
- 전용 한국어 모델 2개(streaming/offline Zipformer, KsponSpeech 969h) — **둘 다 2024-06 커뮤니티 기여 후 갱신 0**
- KsponSpeech CER 10.35~10.60(eval_clean) / 11.35~11.56(eval_other) — **전부 in-domain**(학습=평가 동일 코퍼스)
- **치명적**: issue #2886 (2025-12-10 개설, ~8개월 미해결) — 한국어 streaming 모델이 실제 마이크 경로
  오디오에서 **빈 결과 반환**. 번들 테스트 WAV에서만 동작
- **한국어 구두점 복원 모델 없음** — punctuation zoo에 영어/중영만. 출력이 raw 무구두점
- **API가 float32 PCM 배열만 수용**(`accept_waveform`) → webm/opus 디코딩용 ffmpeg/PyAV 별도 필요(Nix 클로저 증가)
- 한국어 Zipformer 모델 **라이선스 표기 없음** + KsponSpeech/AIHub 이용약관 미확인 → 법적 리스크
- SenseVoice(다국어 ko 포함)가 더 잘 관리됨: MIT, int8 239MB, 2025-09 갱신
- 런타임 Apache-2.0, cp312 휠 O(onnxruntime 26MB 번들, 컴파일러 불필요)
- **한국어 모델 CPU RTF/RAM 데이터 전무**

### 교차 비교 가능한 유일 지점 (SenseVoice README 차트, CommonVoice_ko, ±0.3~0.5)
- Whisper-Large-V3 ~5.6 < SenseVoice-Small ~8.3 < Whisper-Small ~10.5
- → 정확도 순위: Whisper large-v3 > SenseVoice-Small(sherpa 배포 가능) > Whisper small

### Whisper 크기별 곡선 (1차 출처: arXiv:2212.04356 Table 13, FLEURS ko WER, out-of-domain)
tiny 36.1 / base 27.8 / small 19.6 / medium 16.4 / large 15.2 / large-v2 14.3
- large-v3는 OpenAI가 한국어 지표를 WER→CER로 바꿔서 같은 곡선으로 이어붙일 수 없음(정확값 NOT FOUND)
- icefall에 **zeroth_korean 레시피 없음**(ksponspeech만) — sherpa 한국어는 KsponSpeech 단일 도메인

## Phase Log (이어서)

- Phase 1 (PLAN): 완료 — 리서치 3건(엔진별 2 + 한국어 정확도 전용 1, **전부 1회씩 중단→SendMessage 재개**).
  Steps 2-4 리뷰: 완전성(놓친 프레이밍 = sherpa-onnx도 Whisper ONNX 실행 가능 → "런타임×모델" 선택),
  메타(공백 3건: 실측 RTF·large-v3 한국어 CER·turbo 한국어 품질), 과설계(엔진 추상화 레이어 금지).
  **PLAN_GATE pass — 사용자 확정: D7 = faster-whisper, alfheim RAM 16GB+**
- Phase 2 (IMPL): 완료 — 산출물이 문서라 에이전트 미스폰(과설계 리뷰 준수). 로드맵 갱신:
  §0 상태헤더/표, §1 시퀀싱, §6 M4a STT 상세(모델크기·호출옵션·배포·nixpkgs 주의), §7 D7 행 + "D7 비교 결과" 절
- Phase 3 (VERIFY): D7 표기 일관성 점검에서 §0 표 1건 누락 발견→수정. docs verify broken=2(기존 오탐:
  bun run check/build는 frontend/package.json에 실존, 검증기가 루트 package.json을 찾음)
- Phase 4 (REFINE): 스킵(문서 변경이라 Steps 9-13 해당 없음). refine-outcome 기록

## 결정 (D7)

**faster-whisper (CTranslate2) self-host 확정.** 모델 크기는 M4a 착수 시 실측으로 확정
(large-v3-turbo int8 814MB 기본 후보, large-v3와 실제 한국어 샘플 비교). small은 부적합(19.6% WER).

## M4a 착수 시 주의사항 (이 세션에서 확보)

1. `language="ko"` 강제 — 짧은 클립 언어 오탐/영어 누출 방지 + 언어감지 패스 절약
2. 환각 완화 파라미터 검토(무음 구간 환각은 Whisper 알려진 실패 모드, 이슈 83건)
3. 모델 가중치 Nix store vendoring + `WhisperModel("<로컬경로>")` → 런타임 네트워크 의존 제거
4. distil-whisper는 영어 전용 — 경량화 우회로 없음
5. nixpkgs ctranslate2는 OpenBLAS만(int8 가속 제한). **uv2nix는 PyPI 휠이라 별개** — int8 성능
   미달 시 이 지점부터 의심
6. storage.py에 AUDIO MIME 상수 추가 필요, `messages.body` NOT NULL 완화(M3와 연동)
