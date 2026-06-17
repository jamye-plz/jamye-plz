# 온디바이스 AI (WASM)

브라우저에서 WASM으로 추론하는 온디바이스 AI 설계다. 자동 태깅과 살 붙이기(후속 질문 추천)를 서버·외부 API 없이 클라이언트에서 처리한다.

> 버전 v1 · 2026-06-16 · SSOT: plan.json

## 원칙

- **WASM 온디바이스**: 모든 추론을 브라우저 안에서 한다. 글 내용이 사용자 기기를 떠나지 않으므로 프라이버시를 지키고, 추론 서버가 없으니 서버 비용이 0이며, 외부 AI API 의존도 제거한다.
- **순수 WASM baseline + WebGPU 가속**: 모든 기기에서 순수 WASM으로 동작하는 것을 기준선으로 삼고, WebGPU가 감지되면(2026년 데스크톱 약 85% 지원) 자동으로 가속한다.
- **WebLLM 제외**: WebLLM은 WebGPU 전용이라 순수 WASM baseline 원칙에 어긋나므로 채택하지 않는다.

스택 전반은 [tech-stack](./tech-stack.md), 헤더·배포는 [deployment](./deployment.md), 데이터 모델(`topic_tags` 등)은 [data-model](./data-model.md), 제품 개요는 [README](../README.md)를 참고한다.

## 런타임

| 런타임 | 패키지 | 용도 |
|---|---|---|
| Transformers.js | `@huggingface/transformers` | 1차 임베딩 추론 (자동 태깅 + 살 붙이기). WASM + WebGPU 백엔드 |
| wllama | `wllama` | 2차 생성형 살 붙이기용 (순수 WASM GGUF) |

## 기능 1 — 자동 태깅

주제를 올리면 자동으로 태그가 붙는다.

- **모델**: `multilingual-e5-small` (int8 양자화, 약 118MB, MIT)
- **방식**: 주제 텍스트를 e5-small로 임베딩한 뒤, 사전 정의된 태그 집합과의 **코사인 유사도**로 zero-shot 분류해 상위 N개를 태그로 단다.
- **저장**: 결과 태그는 `source=ai`로 저장하며 사용자가 수정할 수 있다 (`PUT /topics/{id}/tags`).
- **런타임**: 순수 WASM으로 충분하다. WebGPU는 있으면 더 빠른 정도다.

## 기능 2 — 살 붙이기 (1차: 비생성)

대화를 이어가도록 후속 질문을 추천한다. **1차는 생성 없이** 동작한다.

- **모델 재사용**: 자동 태깅과 **같은 e5-small 모델**을 그대로 쓴다. 추가 다운로드가 0이다.
- **방식**: "질문 뱅크"(사전 작성된 후속 질문 모음)를 임베딩해 두고, 현재 주제/대화 임베딩과의 유사도로 **상위 3개**를 추천한다. 추천 질문은 사용자가 편집할 수 있다.
- **장점**: 추가 다운로드 0, 즉각적이고 안정적인 응답. "가벼운 기능만 1차"라는 원칙과 일치한다.

질문 뱅크 초기 시드 문항은 미정 항목이다 ([tasks](../planning/milestone.md)의 open questions 참고).

## 2차 — 생성형 살 붙이기 (deferred)

진짜로 문장을 생성하는 살 붙이기는 2차 범위다.

- **런타임/모델**: wllama + `HyperCLOVAX-SEED` (0.5B~1.5B, Q4 양자화, 약 350MB~1.7GB).
- **권장 환경**: WebGPU(데스크톱). 한국어 품질이 좋고 상업 라이선스가 가능하다(MAU 1천만 이하 조건).
- **EXAONE 제외**: EXAONE은 비상업 라이선스라 사용할 수 없다.

## 통합

- **Web Worker 추론**: 추론은 Web Worker에서 돌려 메인 스레드를 막지 않는다. 태깅은 백그라운드 비차단으로 처리한다.
- **모델 캐싱**: Cache Storage / OPFS에 모델을 영구 캐시한다. 2회차부터 추가 다운로드가 0이다.
- **COOP/COEP 헤더**: 멀티스레드 WASM(SharedArrayBuffer)을 켜려면 cross-origin isolation이 필요하다. 이 헤더는 **Caddy**에서 설정한다 ([deployment](./deployment.md) 참고). `self.crossOriginIsolated` 스모크 체크로 활성화 여부를 검증한다.

## 모델·라이브러리 라이선스

| 항목 | 라이선스 | 상업 사용 |
|---|---|---|
| multilingual-e5-small | MIT | 가능 |
| HyperCLOVAX-SEED | 상업 라이선스 (MAU 1천만 이하) | 가능 (조건부) |
| EXAONE | 비상업 | **불가** |
| Transformers.js | Apache-2.0 | 가능 |
| wllama | MIT | 가능 |

## 리스크와 완화

| 리스크 | 완화 |
|---|---|
| 첫 모델 로딩(~118MB) 체감 | Web Worker 비동기 + Cache/OPFS 영구 캐시(2회차 0) + 진행률 UI + 태깅 백그라운드 비차단 |
| COOP/COEP 헤더 누락 시 멀티스레드 WASM 비활성·외부 리소스 차단 | Caddy에서 헤더 강제 + `self.crossOriginIsolated` 스모크 체크 + credentialless 모드 |
| iOS 환경 제약(WebGPU·메모리·SharedArrayBuffer) | 순수 WASM baseline으로 폴백 동작 보장. 무거운 생성형은 2차로 미룸 |
