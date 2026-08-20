# 잼얘좀 (jamye-plz) — 기획 문서

> **재밌는 얘기 좀** — anything interesting?
> 지인 폐쇄 그룹에서 일상의 재밌는 얘기(주제)를 가볍게 시드로 던지고, 언제든 살을 붙이며, 그 주제로 실시간 채팅하며 노는 lightweight 소셜 플랫폼.

> 최초 v1 2026-06-16 · 갱신 2026-08-20(v2 전체 완료). 본 문서 세트가 잼얘좀의 정식 기획 문서다. (기계 판독용 기획 원본 `plan.json`은 로컬 세션 산출물이라 git에 포함되지 않으며, 본 `docs/`가 단일 진실 원천이다.)

---

## 한눈에

| 구분 | 내용 |
|---|---|
| **컨셉** | 셋로그(Setlog)의 폐쇄·날것·알림 참여유도 감성 차용 + 콘텐츠는 "얘기", 핵심 가치는 "그것에 대한 대화" |
| **플랫폼** | 반응형 PWA 웹 (1차) → 네이티브 앱 + 온디바이스 AI (2차+) |
| **프론트엔드** | SvelteKit (Svelte 5) + Tailwind v4 + daisyUI · `adapter-static` SPA |
| **백엔드** | Python FastAPI (REST + native WebSocket) · `router→service→repository` |
| **데이터·저장** | PostgreSQL · MinIO (S3 호환) |
| **실시간** | FastAPI native WebSocket ↔ 브라우저 표준 `WebSocket` |
| **인증** | 자체 카카오·구글 OAuth + JWT (httpOnly 쿠키) |
| **AI** | WASM 온디바이스 (자동 태깅 + 비생성 후속질문 추천) — 서버·외부 API 의존 0 |
| **배포** | NixOS 홈랩 — 인프라·앱 전부 nix native (uv2nix + 정적 SPA) |

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
| [data-model.md](architecture/data-model.md) | 데이터 모델 — 13개 테이블, ERD, 권한 모델 |
| [api-contract.md](architecture/api-contract.md) | REST 엔드포인트 + WebSocket 프로토콜 계약 |
| [on-device-ai.md](architecture/on-device-ai.md) | WASM 온디바이스 AI — 태깅·비생성 추천, 모델·라이선스 |
| [deployment.md](architecture/deployment.md) | NixOS 배포 설계 — nix 모듈·시크릿·flake |

### 🗂️ 실행 (`planning/`)
| 문서 | 내용 |
|---|---|
| [002-v2-roadmap.md](planning/002-v2-roadmap.md) | v2 로드맵 — M0~M4a **전부 완료**, M4b는 vNext. Open Decisions·품질 게이트 |
| [milestone.md](planning/milestone.md) | v1 마일스톤(M0~M4+배포) + 태스크 매핑(T1~16) — **완료·기록용** |
| [001-daisyui-migration.md](planning/001-daisyui-migration.md) | shadcn-svelte → daisyUI 마이그레이션 기록 |
| [tech-debt-tracker.md](planning/tech-debt-tracker.md) | 기술 부채 추적 |

### 🚀 배포 (`deployment/`)
| 문서 | 내용 |
|---|---|
| [nixos-alfheim.md](deployment/nixos-alfheim.md) | alfheim 실제 배포 절차 — homelab 배선·시크릿·MinIO·인그레스 |

---

## 진행 상태

> 갱신 2026-08-20

- ✅ **디스커버리 · 기술 스택 · 정식 기획 · 문서화** — 위 문서 세트로 확정
- ✅ **v1 구현 완료**
- ✅ **배포 완료** — NixOS 홈랩(alfheim), `https://jamye-plz.ridewithmin.com` 운영 중
- ✅ **v2 4대 기능 완료** — M0 스토리지(#16) · M1 Web Push(#17) · M2 그룹 관리(#18) ·
  M3 채팅 미디어(#21) · M4a 음성 메시지 + STT(#22). Open Decisions D1~D8 전부 확정.
  **M4b(실시간 음성 통화, WebRTC)는 도입 계획 없음**.
- 🔄 **진행 중: M5 — WebSocket 자동 재연결** — 모바일에서 앱을 백그라운드로 보냈다 돌아오면
  소켓이 끊긴 채 복구되지 않아 채팅을 재개할 수 없다. v2 범위에 포함.
- 🔄 **그 밖** — 로드맵 밖의 UI·기능 다듬기가 이어지는 중이다(대화 디자인 시스템 #23,
  토픽 컴포저 단순화 #24, 토픽 이름 변경 #26, 포커스 아웃라인 #25·#28,
  Tailwind 토큰 정규화 #29). 이 작업들은 별도 로드맵 문서를 두지 않고 PR 단위로 진행한다.
  상세: [002-v2-roadmap.md](planning/002-v2-roadmap.md)

---

## 에이전트 스킬 운영 메모

- `.agents/`는 기본적으로 oh-my-agent의 SSOT로 취급한다.
- 다만 이 저장소는 OMA 기본 배포에 없는 프로젝트 전용 디자인 스킬을 `.agents/skills/` 아래에 함께 벤더링한다.
- 현재 예외 범위는 `banner-design`, `brand`, `design-system`, `design`, `slides`, `ui-styling`, `ui-ux-pro-max`다.
- 이 스킬들은 잼얘좀 저장소에서 직접 유지하는 로컬 자산이며, OMA 재생성이나 업그레이드 작업 시 자동 산출물로 간주해 덮어쓰면 안 된다.
- OMA를 갱신할 때는 위 디렉터리가 보존되는지 확인하고, 필요한 경우 수동으로 재벤더링한다.

---

## 읽는 순서 (추천)

1. [product/vision-and-scope.md](product/vision-and-scope.md) — 무엇을, 왜 만드는가
2. [product/features.md](product/features.md) — 무엇이 동작하는가
3. [architecture/tech-stack.md](architecture/tech-stack.md) — 무엇으로 만드는가 + 왜 그 선택인가
4. [architecture/data-model.md](architecture/data-model.md) · [api-contract.md](architecture/api-contract.md) · [on-device-ai.md](architecture/on-device-ai.md) — 어떻게 설계되는가
5. [architecture/deployment.md](architecture/deployment.md) — 어디에 어떻게 올리는가(설계)
   · [deployment/nixos-alfheim.md](deployment/nixos-alfheim.md) — 실제 배포 절차
6. [planning/002-v2-roadmap.md](planning/002-v2-roadmap.md) — 무엇을 만들었고 무엇이 vNext로 남았는가
