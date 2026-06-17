# 잼얘좀 (jamye-plz) — 기획 문서

> **재밌는 얘기 좀** — anything interesting?
> 지인 폐쇄 그룹에서 일상의 재밌는 얘기(주제)를 가볍게 시드로 던지고, 언제든 살을 붙이며, 그 주제로 실시간 채팅하며 노는 lightweight 소셜 플랫폼.

> 버전 v1 · 2026-06-16 · 본 문서 세트가 잼얘좀 v1의 정식 기획 문서다. (기계 판독용 기획 원본 `plan.json`은 로컬 세션 산출물이라 git에 포함되지 않으며, 본 `docs/`가 단일 진실 원천이다.)

---

## 한눈에

| 구분 | 내용 |
|---|---|
| **컨셉** | 셋로그(Setlog)의 폐쇄·날것·알림 참여유도 감성 차용 + 콘텐츠는 "얘기", 핵심 가치는 "그것에 대한 대화" |
| **플랫폼** | 반응형 PWA 웹 (1차) → 네이티브 앱 + 온디바이스 AI (2차+) |
| **프론트엔드** | SvelteKit (Svelte 5) + Tailwind v4 + shadcn-svelte · `adapter-static` SPA |
| **백엔드** | Python FastAPI (REST + native WebSocket) · `router→service→repository` |
| **데이터·저장** | PostgreSQL · MinIO (S3 호환) |
| **실시간** | FastAPI native WebSocket ↔ `partysocket` |
| **인증** | 자체 카카오·구글 OAuth + JWT (httpOnly 쿠키) |
| **AI** | WASM 온디바이스 (자동 태깅 + 비생성 후속질문 추천) — 서버·외부 API 의존 0 |
| **배포** | NixOS 홈랩 하이브리드 (인프라 = nix native services, 앱 = podman OCI) |

**v1 핵심 기능**: 폐쇄 그룹 · 잼얘 시드→enrich(텍스트+사진) · 일별 타임라인 · 주제별/그룹 메인 2층 실시간 채팅 · 리마인드 · Web Push · 온디바이스 AI · PWA

---

## 문서 맵

### 📦 제품 (`product/`)
| 문서 | 내용 |
|---|---|
| [vision-and-scope.md](product/vision-and-scope.md) | 비전·컨셉, 시드→enrich 모델, 셋로그 벤치마킹·차별점, v1 스코프, 로드맵 |
| [features.md](product/features.md) | 기능 명세 — 7개 에픽(E1~E7), 유저 스토리, 수용 기준 |

### 🏗️ 아키텍처 (`architecture/`)
| 문서 | 내용 |
|---|---|
| [tech-stack.md](architecture/tech-stack.md) | 전체 기술 스택 + 결정 근거(ADR 요약 6건) |
| [data-model.md](architecture/data-model.md) | 데이터 모델 — 11개 테이블, ERD, 권한 모델 |
| [api-contract.md](architecture/api-contract.md) | REST 24개 엔드포인트 + WebSocket 프로토콜 |
| [on-device-ai.md](architecture/on-device-ai.md) | WASM 온디바이스 AI — 태깅·비생성 추천, 모델·라이선스 |
| [deployment.md](architecture/deployment.md) | NixOS 하이브리드 배포 — nix 모듈·podman·시크릿·flake |

### 🗂️ 실행 (`planning/`)
| 문서 | 내용 |
|---|---|
| [milestone.md](planning/milestone.md) | 마일스톤(M0~M4+배포) + 태스크 매핑(T1~16)·의존성·트랙 |

---

## 진행 상태

- ✅ **디스커버리** — 제품 정체성·스코프 확정 (셋로그 벤치마킹, "얘기+대화" 차별화)
- ✅ **기술 스택 선정** — SvelteKit/FastAPI 생태계, WASM 온디바이스 AI, NixOS 배포 조사 완료
- ✅ **정식 기획** — 요구사항·데이터모델·API·태스크 + 3종 리뷰(완전성/메타/과설계) PASS
- ✅ **문서화** — 본 문서 세트
- ⏭️ **다음** — Phase 2 구현 (Backend/Frontend 병렬) → 검증 → 정제 → 배포

---

## 읽는 순서 (추천)

1. [product/vision-and-scope.md](product/vision-and-scope.md) — 무엇을, 왜 만드는가
2. [product/features.md](product/features.md) — 무엇이 동작하는가
3. [architecture/tech-stack.md](architecture/tech-stack.md) — 무엇으로 만드는가 + 왜 그 선택인가
4. [architecture/data-model.md](architecture/data-model.md) · [api-contract.md](architecture/api-contract.md) · [on-device-ai.md](architecture/on-device-ai.md) — 어떻게 설계되는가
5. [architecture/deployment.md](architecture/deployment.md) — 어디에 어떻게 올리는가
6. [planning/milestone.md](planning/milestone.md) — 어떤 순서로 만드는가
