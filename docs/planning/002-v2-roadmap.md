# jamye-plz v2 Roadmap

> **목적** — v1 이후 4대 기능(그룹 관리 고도화 · 채팅 미디어 첨부 · 음성/STT · Web Push)을
> 구현하기 위한 실행 로드맵. 새 세션에서 이 문서를 읽고 `ultrawork`로 마일스톤별 구현을
> 시작할 수 있도록, **각 기능의 "이미 있는 것(EXISTS) vs 새로 만들 것(GAP)"을 파일 앵커와
> 함께** 정리했다.
>
> **작성일** 2026-07-19 · **갱신** 2026-08-04 · **기준 커밋** `main` (PR #15 머지 후)
>
> **상태** 진행 중 — **M0·M1·M2 완료**(main 머지 + alfheim 프로덕션 배포, 실기기 푸시 수신 검증).
> 다음은 **M3(채팅 미디어)**. M4a는 **D7(STT 프로바이더) 미확정**으로 대기, M4b는 vNext(§7 D6).
>
> 이 로드맵은 v1 코드베이스 4개 영역 정찰(reconnaissance) 결과에 근거한다. 파일:라인
> 앵커는 작성 시점 기준이며 구현 전 재확인할 것.

---

## 0. Executive Summary

v1은 놀랄 만큼 많은 부분이 **이미 스캐폴딩**돼 있다. v2의 상당량은 "새로 짓기"가 아니라
"deferred stub 완성 + 확장"이다.

"착수 전 정찰" 열은 2026-07-19 스냅샷이라 그대로 두고, 진행 상황만 "현재" 열에 갱신한다.

| 기능 | 착수 전 정찰 (2026-07-19) | 현재 |
|------|--------------------------|------|
| **Web Push (VAPID)** | 모델·엔드포인트·SW 핸들러·pywebpush 의존성까지 완비, send 경로만 stub | ✅ **완료 — M1 (PR #17)**. 배포 후 실기기 수신 검증 |
| **그룹 관리 고도화** | owner 개념·`role` 컬럼·`require_owner` 인가 존재, 멤버 목록 완성. write 경로 전무 | ✅ **완료 — M2 (PR #18)** |
| **채팅 미디어 첨부** | topic presign→confirm 흐름 존재, 채팅 메시지는 text-only | 🟩🟩⬜⬜⬜ **M0 완료 (PR #16) — M3 미착수** |
| **음성 채팅 + STT** | 음성 코드 전무. WS·메시지 `type`·미디어 스캐폴드만 재사용 가능 | ⬜⬜⬜⬜⬜ **미착수 — M4a는 D7 확정 대기** |
| *(기반) 오브젝트 스토리지* | boto3 선언만 있고 `import` 0건 (stub) | ✅ **완료 — M0 (PR #16)** + NixOS 배선(PR #19·#20) |

**가장 중요한 통찰 2가지**
1. **오브젝트 스토리지(boto3/S3·MinIO)는 미디어 첨부와 음성 둘 다의 선결 조건**이다. `boto3`는
   의존성에 있으나 `import`조차 없다(stub). → **M0 enabler로 먼저 완성**하면 두 기능이 동시에 열린다.
2. **비동기 job 메커니즘이 완전히 부재**하다(`celery`/`arq`/`BackgroundTasks`/`create_task` 0건).
   음성 transcription의 최대 선결 과제. WS hub도 단일 프로세스 in-memory라, 워커에서 결과를
   broadcast하려면 Redis pub/sub 전환이 필요하다(`ws_hub.py` 도크스트링도 이를 예고).

---

## 1. 권장 마일스톤 & 시퀀싱

의존성·리스크 기준 권장 순서 (사용자 우선순위와 매핑):

```
M0  오브젝트 스토리지 enabler   ─┐ (M3·M4 선행)   [작음·기반]        ✅ 완료 (#16)
M1  Web Push (VAPID)          ─┼─ M0와 병렬 가능   [라스트 마일·고가치·저위험] ✅ 완료 (#17)
M2  그룹 관리 고도화            ─┘ (독립)          [CRUD·중간]        ✅ 완료 (#18)
M3  채팅 미디어 첨부 (img/video)  ← M0 필요          [중상]             ◀ 다음
M4  음성 메시지 + STT            ← M0 + 비동기 job   [최대·최고위험 → 분할]
    M4a 비동기 음성 메시지 (v2 범위 확정)                              ⏸ D7 대기
    M4b 실시간 음성 채팅 WebRTC                                       ⏭ vNext (D6에서 제외)
```

- **M0 + M1**은 서로 독립이라 병렬 착수 가능. M1은 신규 인프라가 없어 **가장 빠른 win**.
- **M2**는 완전 독립(스토리지·비동기 불필요) — 언제든 끼워 넣을 수 있음.
- **M3**는 M0 완료가 전제.
- **M4**는 M0 + 비동기 job(+선택적 Redis)이 전제이며, 범위가 커 **M4a/M4b로 분할** 권장.

> **kickoff에서 확정된 순서** (2026-07-19): M0+M1 → M2 → M3 → M4a. M4b는 vNext.
> 사용자가 처음 제시한 순서(그룹→미디어→음성→푸시) 대신 **스토리지 enabler와 푸시를 먼저**
> 두는 권장안이 채택됐고, M0·M1·M2까지 그대로 실행됐다.

---

## 2. M0 — 오브젝트 스토리지 Enabler (기반)

**목표**: deferred된 presign 실경로를 구현해 실제 파일 업로드/조회를 가능케 한다. 미디어 첨부(M3)·음성(M4)의 공통 기반.

> ✅ **완료 — PR #16 머지** (2026-07-19). 아래 "현재 상태"·"작업"은
> 착수 전 정찰 스냅샷이라 그대로 두고, 실제 배송 내용만 요약한다:
> - `backend/app/core/storage.py` 신설: `minio_enabled`(access/secret key 존재)일 때 실 presign PUT/GET,
>   아니면 결정적 로컬 fallback URL(backend.md 규칙 11).
> - 읽기 경로를 접근 정책 B로 전환 — `GET /api/topics/{id}` 응답의 미디어 URL이 멤버십 확인 후 발급되는
>   단기(600초) presigned GET(`topic_service.py`).
> - `MediaPresignRequest`/`MediaConfirmRequest`에 이미지 MIME allowlist + 10MiB cap 검증 추가(위반 시 422),
>   confirm에는 `object_key`가 `topics/{topic_id}/{uuid4}` 형식인지 검사하는 BOLA 가드 추가(위반 시 422).
> - presign PUT 서명에 `ContentType`/`ContentLength`를 바인딩해 업로드 시점에도 크기 cap을 강제.
> - FastAPI lifespan에서 startup 시 버킷 ensure(`head_bucket`→없으면 `create_bucket`, warn-only).
> - `infra/docker-compose.yml`에 MinIO 서비스 추가(버전 고정, `mc ready` healthcheck), `infra/.env.example`에
>   `MINIO_ROOT_USER/PASSWORD/PORT` 추가.
> - `config.py`가 `APP_ENV=production`에서 MinIO 키 미설정 시 fail-closed(평문 미서명 URL이 프로덕션에서
>   조용히 활성화되는 것을 방지).
>
> **프로덕션 배선 (PR #19·#20, 2026-08-04)** — M0는 앱 코드만 다뤘고 로컬은 `infra/docker-compose.yml`로
> 충분했으나, alfheim 배포에는 MinIO 자체가 없었다. `infra/module.nix`에 `services.minio`(S3 `:9000`,
> 콘솔은 loopback) + `storage.*` 옵션(`createLocally`/`port`/`publicUrl`/`bucket`/`rootCredentialsFile`)을
> 추가해 flake 하나로 풀스택이 뜨도록 했고, 버킷 프로비저닝을 tmpfs(`RuntimeDirectory`) 기반 재시도
> 유닛으로 만들어 실패 시 실제 curl/mc 오류가 로그에 남게 했다(크리덴셜 미노출). 배포 절차는
> [nixos-alfheim.md](../deployment/nixos-alfheim.md) 참고.
>
> **후속 작업(범위 밖, 다음 마일스톤)**: 프론트엔드 첫 호출처는 M3(채팅 미디어 첨부)에서 배선한다(§5).
> `storage.py`의 `VIDEO_MIME_TYPES`/`MAX_VIDEO_BYTES`는 M3/M4용 확장 포인트로 정의만 돼 있고 아직 어떤
> validator에도 연결돼 있지 않다.
>
> 상세는 [api-contract.md](../architecture/api-contract.md)의 미디어 업로드/조회 흐름 절 참고.

### 현재 상태
- `backend/app/routers/media.py` — presign(`:20-46`)/confirm(`:49-70`)/list(`:73-84`) 흐름 존재.
  `minio_enabled`면 `NotImplementedError("MinIO presign real path not implemented")`(`:37-39`),
  아니면 **가짜 URL**(`http://localhost:9000/{bucket}/{key}`, `:42-46`) 반환. `# TODO(oma-deferred)`(`:4`).
- `backend/app/core/config.py:62-67` — `minio_endpoint/access_key/secret_key/bucket`,
  `minio_enabled`(`:94-95`, 키 있으면 True). `boto3>=1.35.0` 선언됐으나 **`import boto3` 0건**.
- URL은 **읽기 시 조합**(`topic_service.py:48`), 저장 안 함.
- 프론트 업로드 3종(`presignMedia`/`confirmMedia`/`uploadToPresignedUrl`, `topic.api.ts:34-80`)
  존재하나 **호출처 없음**(재사용 가능한 준비된 패턴).

### 작업
1. `backend/app/core/storage.py`(신규): boto3 S3 클라이언트. `presign_put(key, content_type)`,
   `presign_get(key)`(단기 TTL). **S3 호환**(MinIO/AWS S3/Cloudflare R2 공용). startup에서
   `head_bucket`→없으면 `create_bucket`(idempotent, dev/prod 공통).
2. `media.py` presign 실경로 구현 — stub 브랜치 제거하되 **backend.md 규칙 11 준수**:
   키가 있으면 실 presign, 없으면 결정적 로컬 fallback 유지(데모 무중단). `# TODO(oma-deferred)` 제거.
3. **읽기 경로를 presigned GET으로 전환** — `topic_service.py:48`의 평문 `{endpoint}/{bucket}/{key}`
   조합(퍼블릭 버킷 전제)을 **멤버십 확인 후 단기 presigned GET 발급**으로 교체(접근 정책 B, 아래 참조).
4. presign을 **topic 국한이 아닌 범용**으로 리팩터(또는 storage 모듈로 승격)해 M3·M4가 재사용.
5. 검증: `MediaPresignRequest`에 **MIME allowlist + 최대 크기 cap** 추가(`schemas/topic.py:67-69`는
   길이/양수만 검사 — 취약).

### 수용 기준
- 실 키 세팅 시: presign PUT으로 업로드 → 저장 → **멤버십 확인 후 발급된 presigned GET**으로 조회(무서명 요청은 403).
- 키 미설정 시: 로컬 fallback으로 데모 동작(기존 UX 회귀 없음).
- `uv run pytest` 통과(스토리지 mock), `ruff`/`pyright` clean.

### 환경별 배포 & 접근 정책

**env 주입 — 소비자 2곳** (MinIO 서비스 vs 백엔드 앱, Postgres와 동일 구조):

| 환경 | MinIO 서비스 (루트 크리덴셜) | 백엔드 앱 (`MINIO_*`) |
|------|------------------------------|------------------------|
| 로컬 (podman compose) | `infra/.env` (`MINIO_ROOT_USER/PASSWORD/PORT`) | `backend/.env` (`MINIO_ENDPOINT=http://localhost:9000`, `MINIO_ACCESS_KEY`=root user, `MINIO_SECRET_KEY`, `MINIO_BUCKET`) |
| 프로덕션 (alfheim) | `services.minio.rootCredentialsFile` = homelab sops secret | `services.jamye-plz.environmentFile` = homelab sops template (JWT·OAuth와 동일 경로) |

- `podman compose`는 `infra/.env`만 자동 로드(컨테이너 기동용), 백엔드는 `backend/.env`를 읽음 —
  **파일 2벌, 값은 관례로 일치**시킴(로컬 `MINIO_ACCESS_KEY`=`MINIO_ROOT_USER`).
- prod 보안 권장: 백엔드엔 루트 대신 **`jamye` 버킷 전용 access key(service account)** 주입(최소권한).
  홈랩 단순화 시 루트 재사용 수용 가능.
- 배포 구조: 홈랩 ingress 노드(Caddy + Cloudflare Tunnel) → alfheim. MinIO는 alfheim 내부(loopback/tailnet),
  열린 공개 포트 없음.

**미디어 접근 정책 — B: 프라이빗 버킷 + presigned GET (확정)**

폐쇄 그룹의 사적 미디어이므로 **익명 퍼블릭 개방 금지**. "네트워크 도달성 ≠ 익명 읽기"를 분리한다:

- **버킷은 프라이빗** — 서명 없는 요청은 403. ingress에 **미디어 서브도메인**(예: `media.jamye.example`)을
  열어 MinIO S3 엔드포인트에 **도달만** 가능케 함(내용 개방 아님).
- **읽기**: 백엔드가 **멤버십 확인 후 단기(5~15분) presigned GET** 발급 → 브라우저가 그 URL로 MinIO에서
  직접 로드. 유출 창은 TTL로 한정. 비디오 `<video>` seek(Range)도 presigned GET에서 그대로 동작.
- **업로드**: 기존 presign PUT — `media.py`가 `require_membership`로 인가된 멤버에게만 서명(이미 안전).
- `MINIO_ENDPOINT`는 **브라우저가 닿는 주소**여야 함(presigned URL에 호스트가 박힘):
  로컬 `http://localhost:9000`, prod `https://media.jamye.example`(ingress 프록시).
- (대안 C) 최대 프라이버시 필요 시 백엔드 프록시(`GET /api/media/*`, 매 요청 멤버십 인가, MinIO 완전 내부)
  — 대역폭·Range 구현 비용 감수. **기본은 B.**

### Open Decision → **[D1] 스토리지 프로바이더 + 미디어 접근 정책** (§7)

---

## 3. M1 — Web Push (VAPID)

**목표**: 실제 브라우저 푸시 알림. 스캐폴딩이 거의 완성이라 **라스트 마일만** 채운다.

> ✅ **완료 — PR #17 머지** (2026-08-04). **프로덕션 배포 후 실기기 푸시 수신까지 검증 완료.**
> 아래 "현재 상태"·"작업"은 착수 전 정찰 스냅샷이라 그대로 두고, 실제 배송 내용만 요약한다:
> - `notification_service.send_push` 실경로: `pywebpush`로 `{title,body,url}` 발송, 404/410 구독 자동 prune,
>   사용자당 최신 N개(10)만 로드, 네트워크 I/O 전 DB 트랜잭션 해제.
> - `push_dispatch.py` 신설 — fire-and-forget 디스패치를 세마포어(동시 4)와 in-flight 상한(64)으로 제한,
>   포화 시 이벤트를 흘려보내 요청 경로를 절대 블로킹하지 않음(D2 = BackgroundTasks 계열 확정).
> - `GET /api/push/vapid-public-key` 추가(키 미설정 시 빈 문자열 → 프론트가 조용히 비활성).
> - `DELETE /api/push/subscribe`가 선택적 `{endpoint}`를 받아 **기기 단위 해지** 지원.
> - **SSRF 방어**: `core/push_endpoint.py`가 엔드포인트 검증 단일 소스. IDNA 정규화 후 IP 리터럴·수치 별칭
>   (`127.1`/`2130706433`/`0x7f000001`)·비-global/멀티캐스트/예약 대역·`/etc/hosts` IPv6 별칭을 차단하고,
>   구독 시점에는 DNS 해석까지 확인(발송 경로는 리졸버를 타지 않음). 리다이렉트는 세션 레벨에서 비활성.
> - **구독 키 검증**: `p256dh`는 strict base64 디코딩 + 실제 P-256 곡선 위의 점인지까지 파싱해 검증.
> - 프론트: 마이페이지 알림 토글, `urlBase64ToUint8Array`, VAPID 키 회전 인지 재구독(`reconcileOrRecreate`),
>   로그아웃 시 구독 detach, 로그인 계정 전환 시 구독 소유권 재귀속(`PushReconciler.svelte`, 루트 레이아웃 상주).
> - SW: `pushsubscriptionchange`가 **현재** 서버 키를 다시 받아 재구독하고, 등록 POST 실패 시 방금 만든
>   로컬 구독을 되돌림.
>
> **배포 중 발견·수정** (`94deabb`): `manifest.webmanifest`가 두 경로(vite-plugin-pwa 자체 엔트리 +
> `@vite-pwa/sveltekit` glob)로 **이중 precache**되어 workbox `addToCacheList`가 SW 최상위 평가에서 throw →
> **서비스워커 등록 자체가 실패**했다. 등록이 없으니 `getActiveRegistration()`이 null이 되고 토글은 이를
> "알림 권한 차단"으로 잘못 표시했다. `injectManifest.globIgnores: ['**/*.webmanifest']`로 해소
> (`manifestTransforms`로는 SvelteKit 통합의 `client/` prefix 제거가 같이 사라져 불가).
>
> **후속(P2, 미해결)**: (a) 백그라운드 등록 실패로 SW 구독이 제거된 경우 자동 복구 없음 — "켜져 있었음"
> 마커 영속화 필요. (b) `notificationclick`이 payload의 **상대 경로**를 `WindowClient.url`(절대)과 비교해
> 이미 열린 채팅 탭을 못 찾고 새 탭을 연다. → [tech-debt-tracker.md](./tech-debt-tracker.md)

### 현재 상태 (거의 완성)
- **완성**: `push_subscription` 모델, `POST/DELETE /api/push/subscribe`(`routers/push.py`),
  `PushSubscriptionRepository`(`notification_repository.py:163-195`), config VAPID 3키
  (`config.py:69-73`, `vapid_enabled` `:98-99`), SW `push`(`service-worker.ts:40-52`)/
  `notificationclick`(`:54-64`) 핸들러, `pywebpush 2.3.0` 락됨, 프론트 `requestAndSubscribe`(`push.api.ts:17-40`).
- **GAP (라스트 마일)**:
  1. `pywebpush` **import·호출 0건**. `send_push`(`notification_service.py:180-186`)는
     `vapid_enabled`면 `NotImplementedError`, 아니면 no-op.
  2. `send_push` **호출처 없음** — 알림 생성 경로(`create_notification :28`, `bump_topic_unread :41`)가
     in-app 알림만 씀. 여기가 훅 포인트.
  3. **VAPID 공개키를 프론트에 노출하는 엔드포인트 없음**.
  4. 프론트 `requestAndSubscribe`/`subscribePush` **호출처 없음**, VAPID 공개키 미배선,
     `applicationServerKey` base64url→Uint8Array 변환 헬퍼(`urlBase64ToUint8Array`) **없음**.
  5. SW `pushsubscriptionchange` 핸들러 없음. push payload 계약(`{title,body,url}`) 서버측 미정의.

### 작업
- **Backend**: (a) VAPID 키페어 생성·`VAPID_*` env 세팅(`.env.example:43-47` 채움).
  (b) `send_push` 실경로 구현 — `push_repo.list_by_user` → SW가 기대하는 `{title,body,url}` payload로
  `pywebpush.webpush(..., vapid_private_key, vapid_claims)`, **404/410(Gone)이면 구독 prune**.
  (c) `create_notification`/`bump_topic_unread`(또는 그 caller)에서 `send_push` 호출 —
  **요청을 블로킹하지 않게**(fire-and-forget / BackgroundTasks) + 실패 흡수.
  (d) `GET /api/config` 또는 `/api/push/vapid-public-key`로 공개키 노출.
- **Frontend**: 공개키 fetch → `urlBase64ToUint8Array` 추가 → `requestAndSubscribe` 호출을
  **권한 요청 UI**(마이페이지 알림 토글 등)에 연결. SW에 `pushsubscriptionchange` 재구독 핸들러.

### 수용 기준
- 구독 후 새 주제/안 읽은 채팅 발생 시 실제 브라우저 푸시 도착, 클릭 시 해당 화면 이동.
- 만료/해지된 구독은 전송 시 자동 prune. 키 미설정 시 조용히 no-op(회귀 없음).

### Open Decision → **[D2] 푸시 발송 방식(동기 fire-and-forget vs 비동기 job)** (§7)

---

## 4. M2 — 그룹 관리 고도화

**목표**: 그룹 이름 수정 · 멤버 관리(제거/탈퇴/역할·소유권 이양) · 그룹 soft-delete.

> ✅ **완료 — PR #18 머지** (2026-08-04). 아래 "현재 상태"·"작업"은 착수 전 정찰 스냅샷이라
> 그대로 두고, 실제 배송 내용만 요약한다:
> - 마이그레이션 `groups.deleted_at` 추가. soft-delete(D3 확정: 즉시 숨김 + `deleted_at` 보존).
> - 엔드포인트: `PATCH /api/groups/{id}`(이름) · `DELETE /api/groups/{id}`(soft-delete) ·
>   `DELETE /api/groups/{gid}/members/{uid}`(제거/탈퇴) · `PATCH /api/groups/{gid}/members/{uid}`(소유권 이양).
> - **인가 캐스케이드**: `require_membership`이 먼저 `get_group_or_404`를 타므로 soft-delete된 그룹은
>   멤버 목록·상세·토픽·채팅 어디서든 404로 사라진다.
> - **경합 방어**: 소유권 이양·멤버 제거·탈퇴·삭제·이름 변경을 전부 `lock_group_or_404`(`SELECT … FOR UPDATE`)
>   아래에서 수행 — "마지막 owner가 동시에 탈퇴" 같은 경합에서 owner 없는 그룹이 생기지 않는다.
>   (채팅 메시지 경로는 의도적으로 락을 걸지 않는다 — 그룹 단위 직렬화가 되어 처리량이 무너지므로.)
> - **WS 즉시 축출**: 제거·탈퇴·그룹 삭제 시 해당 사용자의 열린 소켓을 close code `4001`로 끊는다
>   (`ws_hub.evict_user`/`evict_room`). 축출된 클라이언트는 재연결 시 404를 받는다.
> - 프론트: 그룹 설정 페이지(이름 변경·나가기·삭제), 멤버 목록의 제거/이양 컨트롤, 확인 모달,
>   그룹 이탈 후 관련 쿼리 캐시 purge(5분 staleTime 때문에 뒤로가기로 되살아나는 것 방지).

### 현재 상태
- **재사용 가능**: `owner_id`(`group.py:25`) + Membership `role`(`membership.py:24`, `owner|member`) +
  **`GroupService.require_owner`(`group_service.py:65-69`)** 인가 훅 — 현재 초대 생성(`invites.py:26`)에만 사용.
  멤버 목록(`list_members_out :74`, `GET /members`)·프론트 표시(`invite/+page.svelte:129-154`) 완성.
  예외 체계(`ForbiddenError/NotFoundError/ConflictError`, `exceptions.py`) 완비.
- **GAP**:
  - 엔드포인트: `PATCH /groups/{id}`(rename)·`DELETE /groups/{id}`(soft-delete)·
    `DELETE /groups/{id}/members/{user_id}`(제거/탈퇴)·역할·소유권 이양 **전무**(`groups.py`는 read/create 4개뿐).
  - 모델: Group에 **`deleted_at`/`is_deleted` 없음**, `updated_at` 없음.
  - repo: `MembershipRepository`에 `delete`/`update_role` 없음, `GroupRepository`에 update/soft-delete 없음.
  - **cascade 전무**: groups→children FK에 `ondelete` 없음(하드 삭제는 FK 위반으로 차단),
    ORM `cascade` 없음 → **soft-delete 강력 권장**.
  - 프론트: 그룹 설정 페이지·이름 수정 폼·멤버 관리 컨트롤·삭제 액션 없음. `group.api.ts`에
    `apiPatch`/`apiDelete` 미사용.

### 작업
- **Backend**:
  - migration: `groups.deleted_at TIMESTAMP NULL` 추가(soft-delete). (선택) `updated_at`.
  - `update_group_name`(owner) → `PATCH /groups/{id}`.
  - `soft_delete_group`(owner) → `DELETE /groups/{id}` — `deleted_at` 세팅. `list_by_user`/`get_by_id`/
    `member_count` 등 조회에 **`deleted_at IS NULL` 필터** 추가.
  - `remove_member`(owner가 타인 제거) + `leave_group`(본인 탈퇴) → `DELETE /groups/{id}/members/{user_id}`.
    `MembershipRepository.delete` 추가. **owner는 이양 없이 탈퇴 불가** 규칙.
  - `transfer_ownership`/`change_role` → `PATCH /groups/{id}/members/{user_id}`. `update_role` 추가.
  - 전부 `require_owner`(이양/제거/이름/삭제) 또는 self(탈퇴) 인가.
- **Frontend**: 그룹 설정 진입점(그룹 상세 헤더 `[id]/+page.svelte:111-146`에 설정 버튼 추가),
  이름 수정 폼, 멤버 관리(제거/이양/역할) 컨트롤(초대 페이지 멤버 목록 확장), 삭제 확인 모달,
  탈퇴 액션. `group.api.ts`에 `apiPatch`/`apiDelete` 헬퍼 + 호출.

### 수용 기준
- owner만 이름 변경/삭제/멤버 제거/이양 가능(비owner는 403). 본인 탈퇴 가능(owner는 이양 후).
- soft-delete된 그룹은 모든 멤버 목록·상세·채팅에서 사라짐(복구 가능 상태로 보존).
- 마이그레이션 up/down 검증, `pytest`/`ruff`/`pyright` clean.

### Open Decision → **[D3] soft-delete 시맨틱(복구 창·멤버 처리)** (§7)

---

## 5. M3 — 채팅 미디어 첨부 (이미지 / 비디오)

**목표**: 채팅 메시지에 이미지·비디오 첨부. **M0(스토리지) 선행 필수.**

### 현재 상태
- **재사용**: topic presign→confirm→list 계약·stub fallback 패턴(`media.py`, `TopicService.confirm_media/list_media`,
  `TopicMediaRepository:112-140`), URL-on-read 조합(`topic_service.py:48`), 프론트 업로드 3종(`topic.api.ts:34-80`, 미사용),
  이미지 렌더 블록(`topics/[tid]/+page.svelte:90-105`, `image/`만).
- **GAP (채팅 메시지는 미디어 전무)**:
  - 메시지 모델(`message.py:17-44`)·`MessageOut`(`chat.py:8-19`)·WS payload(`main.py:199-210`)·
    프론트 `ChatMessage`/`WsServerMessage`(`chat.types.ts`) **미디어 필드 0**. `TopicMedia`는 topic-FK 고정.
  - WS `send_message`가 **빈 body 거부**(`main.py:182`) → 이미지 단독 메시지 불가.
  - 채팅 composer는 `<textarea>`만(`ChatRoom.svelte:688-695`), **file input/picker/preview 없음**.
  - 채팅 버블에 이미지/비디오 렌더 없음. **비디오 지원 전무**(`<video>` 없음, 썸네일/트랜스코딩 없음).
  - markdown에서 `<img>` 금지(`markdown.ts:12`, DOMPurify) → 미디어는 별도 필드로 가야 함.
  - 검증 취약(MIME allowlist·크기 cap 없음).

### 작업
- **Backend**:
  - migration + 모델: **`message_media` 테이블**(신규, message-scoped: `message_id` FK, `object_key`,
    `content_type`, `width`/`height`, `byte_size`, video용 `duration` nullable) — `topic_media` 미러.
    (대안: 범용 `media` 테이블로 일반화 — [D4].)
  - write 경로: `ChatService.send_message`·`MessageRepository.create`·WS `send_message` 핸들러가
    **미디어(confirm된 key 목록) 수용**. **body OR media** 있으면 허용(빈 body 규칙 완화, `main.py:182`).
  - read 경로: `MessageOut`/`MessagePage`·`ChatMessage`/`WsServerMessage`에 `media[]` 추가. 히스토리 반환.
  - 검증: MIME allowlist(`image/*`, `video/mp4` 등)·최대 크기.
- **Frontend**: composer에 file picker(+선택 붙여넣기/드래그) + 미리보기, 업로드는 M0 presign 재사용
  (`chat.api.ts`에 chat-scoped 업로드 헬퍼), 채팅 버블에 `<img>`/`<video>` 렌더(`topics/[tid]` 렌더 블록 일반화).

### 수용 기준
- 이미지·비디오(mp4) 첨부 전송 → 상대에게 WS 실시간 표시 + 히스토리에 남음. 이미지 단독 메시지 허용.
- 허용 외 MIME/과대 파일 거부. `eslint`/`svelte-check`/`build` clean, `pytest` 통과.

### Open Decision → **[D4] message_media 전용 테이블 vs 범용 media 테이블**, **[D5] 비디오 처리 수준(직접재생 vs 썸네일/트랜스코딩)** (§7)

---

## 6. M4 — 음성 메시지 + STT (전사)

**목표**: 음성 + transcription. **범위가 커서 M4a/M4b로 분할 권장.** M0 + 비동기 job 선행.

### 현재 상태
- **재사용**: WS 파이프라인(`ws_hub.py`, `main.py:97-244`), 프론트 WS 클라이언트(`ChatRoom.svelte:270-447`),
  메시지 `type` 필드(`message.py:37`, **`String(8)` — "voice"는 OK, "transcription"은 마이그레이션 필요**),
  M0 스토리지(오디오 파일), config 패턴(STT 키 추가), `boto3`/`httpx`.
- **전부 신규**: 오디오/WebRTC/MediaRecorder/whisper/STT 코드 **0건**. **비동기 job 메커니즘 부재**
  (celery/arq/BackgroundTasks/create_task 0). ws_hub 단일 프로세스 → 워커 broadcast엔 Redis pub/sub 필요.
  STT 엔진·config 키 없음. 마이크 캡처·오디오 재생 UI 없음.

### M4a — 비동기 음성 메시지 (권장 v2 범위)
녹음 → 오디오 업로드(M0) → `type="voice"` 메시지 + 오디오 미디어 + duration 생성 →
**비동기 transcription 큐잉** → STT → transcript로 메시지 업데이트(별도 `transcript` 컬럼 권장, `type` cap 주의) →
WS로 결과 broadcast.
- **비동기 인프라 신규 필요**: MVP는 `BackgroundTasks`(in-process·비내구), 확장은 `arq`+Redis(내구·크로스프로세스).
  Redis 도입 시 ws_hub pub/sub도 동시 해결.
- **STT 엔진**: self-hosted `faster-whisper`(alfheim, 무과금, 한국어 양호) vs 클라우드(OpenAI/Deepgram 등, `httpx`로).
- 프론트: composer에 녹음 버튼(MediaRecorder), 채팅 버블에 `<audio>` 플레이어 + transcript 표시.

### M4b — 실시간 음성 채팅 (WebRTC, 스트레치 / vNext 권장)
WebRTC 시그널링(기존 WS 재사용)·peer connection·STUN/TURN. 실시간 전사는 스트리밍 STT 필요.
**M4a 대비 3배+ 범위** → 별도 마일스톤 또는 vNext 권장.

### 수용 기준 (M4a)
- 음성 녹음·전송 → 오디오 재생 가능 + 잠시 후 transcript 채워짐(WS 갱신). 키 미설정 시 로컬 fallback/무전사.

### Open Decision → **[D6] 음성 범위(음성 메시지 vs 실시간 WebRTC)**, **[D7] STT 프로바이더**, **[D8] 비동기 인프라(BackgroundTasks vs arq+Redis)** (§7)

---

## 7. Open Decisions (kickoff 시 확정)

### 확정 결과 (2026-07-19 kickoff)

**D7을 제외한 전부 확정.** 아래 "권장" 표는 확정 근거로 보존한다.

| # | 확정 | 반영 위치 |
|---|------|----------|
| **D1** | ✅ **MinIO + 접근 정책 B**(프라이빗 버킷 + 단기 presigned GET) — 권장안 채택 | M0 (#16), NixOS 배선 (#19·#20) |
| **D2** | ✅ **요청 비블로킹 fire-and-forget** — 권장(BackgroundTasks)과 동일 계열이되, 동시 4 / in-flight 64 상한을 둔 `push_dispatch.py`로 구현 | M1 (#17) |
| **D3** | ✅ **즉시 숨김 + `deleted_at` 보존**(하드 purge는 후속) — 권장안 채택 | M2 (#18) |
| **D4** | ✅ **`message_media` 전용 테이블** — 권장안 채택 | M3 (예정) |
| **D5** | ✅ **직접 재생(mp4) + 크기 제한**(썸네일·트랜스코딩 후속) — 권장안 채택 | M3 (예정) |
| **D6** | ✅ **음성 메시지(M4a)만 v2 범위. WebRTC(M4b)는 vNext** — 권장안 채택 | M4a (대기) |
| **D7** | ⏸ **미확정** — `sherpa-onnx` vs `faster-whisper`를 **정확도 · 한국어 호환성 · jamye-plz 적합성** 기준으로 비교한 뒤 결정. **M4a 착수 전 선행 필수** | — |
| **D8** | ✅ **arq + Redis**(내구성 + ws_hub pub/sub 동시 해결) — M4a에서 도입 | M4a (대기) |

### 권장안 (착수 전 원본)

각 항목에 **권장안**을 제시. 새 세션은 착수 전 사용자와 확정할 것.

| # | 결정 | 옵션 | 권장 |
|---|------|------|------|
| **D1** | 스토리지 프로바이더 + 미디어 접근 정책 | 프로바이더: MinIO · S3 · R2 / 접근: 퍼블릭(A) · presigned GET(B) · 백엔드 프록시(C) | **MinIO**(alfheim self-host 정합, config `minio_*`, boto3 S3 호환→교체 용이) + **접근 B: 프라이빗 버킷 + presigned GET**(멤버십 확인 후 단기 발급, §2 "환경별 배포 & 접근 정책" 참조). **퍼블릭 버킷(A) 금지** |
| **D2** | 푸시 발송 방식 | 요청 내 fire-and-forget · BackgroundTasks · 비동기 job | **BackgroundTasks**(단순·비블로킹), M4에서 job 도입 시 이관 |
| **D3** | soft-delete 시맨틱 | 즉시 숨김만 · 복구창(N일) · 하드삭제 배치 | **즉시 숨김 + `deleted_at` 보존**(복구 여지), 하드 purge는 후속 |
| **D4** | 채팅 미디어 테이블 | `message_media` 전용 · 범용 `media` 일반화 | **`message_media` 전용**(topic_media 미러, 최소 변경) |
| **D5** | 비디오 처리 | 직접 재생만 · 썸네일 · 트랜스코딩 | **직접 재생(mp4) + 크기 제한**, 썸네일/트랜스코딩은 후속 |
| **D6** | 음성 범위 | 비동기 음성 메시지 · 실시간 WebRTC · 둘 다 | **음성 메시지(M4a) 먼저**, WebRTC는 vNext |
| **D7** | STT 프로바이더 | self-host faster-whisper · OpenAI · Deepgram 등 | **faster-whisper self-host**(무과금·한국어·on-device 방향, `docs/architecture/on-device-ai.md` 참조) |
| **D8** | 비동기 인프라 | FastAPI BackgroundTasks · arq+Redis · Celery | **arq+Redis**(내구성 + ws_hub pub/sub 동시 해결) — 단, MVP는 BackgroundTasks로 시작 가능 |

> **D6이 로드맵 규모를 가장 크게 좌우**한다(실시간 WebRTC 포함 여부). 착수 전 최우선 확정.
> → kickoff에서 **음성 메시지(M4a)만 v2 범위**로 확정, WebRTC는 vNext.

---

## 8. 품질 게이트 (모든 마일스톤 공통, 프로젝트 규칙)

- **Backend**: 클린 아키텍처(router→service→repo→model), 커스텀 예외(raw `HTTPException` 금지),
  **third-party는 env-conditional + deferred fallback**(`backend.md` 규칙 11), 파라미터라이즈드 쿼리,
  명시적 트랜잭션. 모델 변경 시 **alembic 마이그레이션 필수**(up/down 검증).
  게이트: `uv run pytest` · **`uv run ruff check/format`** · `npx pyright --project pyrightconfig.json` = 0.
  > `uvx ruff`는 **프로젝트 핀을 무시하고 최신 ruff를 받아** 기존 파일까지 무더기로 지적한다.
  > 반드시 `uv run`(락파일 버전)으로 돌릴 것 — [tech-debt-tracker.md](./tech-debt-tracker.md) #7.
- **Frontend**: Svelte 5 runes · Tailwind v4 + daisyUI · 내부 네비 `resolve()`(`$app/paths`) · bulk-suppression 금지.
  게이트: `bunx eslint .` = 0 · `bun run check` = 0/0 · `bunx prettier --check .` · `bun run build` = 0.
- **공통**: Conventional Commits(scope별 분리) · UI 문자열 한국어(i18n 규칙) · `bun.lock` 변경 시
  Nix FOD 해시(`infra/frontend.nix`) 재생성(alfheim).
- 각 기능 완료 시 `docs/architecture/data-model.md`·`api-contract.md` 갱신, 본 로드맵 상태 업데이트.

---

## 9. Ultrawork Kickoff 프롬프트 (복사용)

새 세션에 아래를 붙여넣어 시작한다:

```
/ultrawork

docs/planning/002-v2-roadmap.md 를 읽고 v2를 구현한다.

시작 전:
1. §7 Open Decisions(D1~D8)를 나에게 확인받아 확정할 것. 특히 D6(음성 범위)은 규모를
   좌우하므로 최우선. 권장안이 있으니 이견 없으면 권장안으로 진행.
2. 확정된 결정에 맞춰 마일스톤 순서를 잡는다. 기본 권장: M0(스토리지)+M1(푸시) 병렬 →
   M2(그룹 관리) → M3(채팅 미디어) → M4a(음성 메시지). M4b(WebRTC)는 vNext.

진행 방식:
- 마일스톤 하나씩 별도 브랜치 + PR. 각 마일스톤의 "현재 상태/작업/수용 기준"을 로드맵에서 따르고,
  파일:라인 앵커는 착수 시 재확인(문서는 main 기준).
- §8 품질 게이트를 모든 변경에 적용(backend: pytest/ruff/pyright, frontend: eslint/check/build).
- deferred 통합은 반드시 env-conditional + 로컬 fallback 유지(키 없어도 데모 동작).

먼저 M0부터 상세 계획을 세우고 나에게 확인받은 뒤 구현을 시작할 것.
```

---

## 부록 A — 기능별 핵심 파일 앵커

| 영역 | 재사용/확장 대상 (EXISTS) | 신규/수정 필요 (GAP) |
|------|--------------------------|----------------------|
| 스토리지 | `media.py:20-84`, `topic_service.py:48,191-213`, `topic.api.ts:34-80`, `config.py:62-67,94-95`, boto3(선언·미사용) | `core/storage.py`(신규), presign 실경로, MIME/크기 검증 |
| Web Push | `push_subscription`모델, `push.py`, `notification_repository.py:163-195`, `config.py:69-73,98-99`, `service-worker.ts:40-64`, `push.api.ts:17-40`, pywebpush | `send_push` 실경로(`notification_service.py:180-186`), 발송 훅(`:28,:41`), 공개키 엔드포인트, 프론트 호출·`urlBase64ToUint8Array`·권한 UI·`pushsubscriptionchange` |
| 그룹 관리 | `require_owner`(`group_service.py:65-69`), `role`(`membership.py:24`), 멤버목록(`:74`), 예외체계 | `PATCH/DELETE /groups/*` + members 엔드포인트, `deleted_at` 마이그레이션, `MembershipRepository.delete/update_role`, 프론트 설정/멤버관리 UI, `apiPatch/apiDelete` |
| 채팅 미디어 | topic presign 흐름, 이미지 렌더(`topics/[tid]/+page.svelte:90-105`), WS broadcast(`main.py:199-222`) | `message_media` 테이블, 메시지 write/read/WS 미디어 필드, 빈 body 규칙 완화(`main.py:182`), composer file picker, `<img>/<video>` 버블 렌더 |
| 음성/STT | WS(`ws_hub.py`,`main.py:97-244`), 메시지 `type`(`message.py:37`, `String(8)`), M0 스토리지, config 패턴, `httpx` | 비동기 job 인프라(전무), STT 엔진·키, MediaRecorder, `<audio>` 플레이어, transcript 컬럼, (WebRTC 시) 시그널링·STUN/TURN·Redis pub/sub |
