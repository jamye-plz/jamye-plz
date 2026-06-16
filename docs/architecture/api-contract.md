# API 계약 (REST + WebSocket)

백엔드 FastAPI가 노출하는 REST 엔드포인트 24개와 실시간 WebSocket 프로토콜, 인증 모델을 정리한 계약 문서다.

> 버전 v1 · 2026-06-16 · SSOT: plan.json

## 개요

- **REST**: 동기 자원 조작(인증·그룹·주제·미디어·알림)에 사용한다. JSON 요청/응답.
- **WebSocket**: 채팅 메시지 송수신과 리마인드 시스템 메시지처럼 실시간성이 필요한 흐름에 사용한다.
- 스택·배포·데이터 모델 상세는 [tech-stack](./tech-stack.md), [deployment](./deployment.md), [data-model](./data-model.md)를 참고한다. 제품 개요는 [README](../README.md)에 있다.

인증 모델 요약은 [인증 모델](#인증-모델) 절을 참고한다. 표의 "인증" 열은 호출에 유효한 JWT가 필요한지 여부다.

## REST 엔드포인트

### auth — 인증

| 메서드 | 경로 | 설명 | 인증 |
|---|---|---|---|
| GET | `/auth/{provider}/login` | OAuth 로그인 시작 (provider: kakao \| google) | 불필요 |
| GET | `/auth/{provider}/callback` | OAuth 콜백 처리 후 JWT를 httpOnly 쿠키로 발급 (`Set-Cookie`) | 불필요 |
| POST | `/auth/logout` | 세션 종료, 쿠키 무효화 | 필요 |

### me — 내 프로필

| 메서드 | 경로 | 설명 | 인증 |
|---|---|---|---|
| GET | `/me` | 현재 사용자 정보 조회 | 필요 |
| PATCH | `/me` | 닉네임·아바타 수정 | 필요 |

### groups · invites — 그룹·초대

| 메서드 | 경로 | 설명 | 인증 |
|---|---|---|---|
| POST | `/groups` | 그룹 생성 (이름). 생성자는 owner | 필요 |
| GET | `/groups` | 내가 멤버인 그룹 목록 | 필요 |
| GET | `/groups/{id}` | 그룹 상세. 비멤버는 403 | 필요 (멤버) |
| POST | `/groups/{id}/invites` | 초대코드/링크 생성 (만료·사용횟수) | 필요 (owner) |
| POST | `/invites/{code}/join` | 초대코드로 그룹 참여. 만료/초과 시 거부 | 필요 |

### topics · media · tags — 잼얘 시드·enrich

| 메서드 | 경로 | 설명 | 인증 |
|---|---|---|---|
| POST | `/groups/{id}/topics` | 주제 시드 등록 (title만, status=seed) | 필요 (멤버) |
| PATCH | `/topics/{id}` | enrich: 본문 추가 (status=enriched). 작성자만 | 필요 (작성자) |
| GET | `/groups/{id}/topics?cursor=&date=` | 일별 타임라인 (cursor 페이지네이션) | 필요 (멤버) |
| GET | `/topics/{id}` | 주제 상세 (본문·미디어·태그) | 필요 (멤버) |
| POST | `/topics/{id}/media/presign` | MinIO presigned PUT URL 발급 | 필요 (작성자) |
| POST | `/topics/{id}/media` | 업로드 확정 (object_key, 치수 등록) | 필요 (작성자) |
| PUT | `/topics/{id}/tags` | ai/user 태그 동기화 | 필요 (작성자) |

### chat — 채팅 히스토리

| 메서드 | 경로 | 설명 | 인증 |
|---|---|---|---|
| GET | `/chatrooms/{id}/messages?cursor=` | 채팅방 메시지 히스토리 (cursor 페이지네이션) | 필요 (멤버) |

> 실시간 메시지 송수신은 REST가 아니라 WebSocket으로 처리한다. 이 엔드포인트는 입장 시점의 과거 메시지 로딩과 재연결 후 재동기화 용도다.

### push — 푸시 구독

| 메서드 | 경로 | 설명 | 인증 |
|---|---|---|---|
| POST | `/push/subscribe` | Web Push 구독 등록 (endpoint, p256dh, auth) | 필요 |
| DELETE | `/push/subscribe` | 구독 해제 | 필요 |

### notifications — 인앱 알림

| 메서드 | 경로 | 설명 | 인증 |
|---|---|---|---|
| GET | `/notifications` | 인앱 알림 목록 (읽음/안읽음) | 필요 |
| POST | `/notifications/{id}/read` | 알림 읽음 처리 | 필요 |

## 요청/응답 예시

### POST /groups/{id}/topics — 주제 시드 등록

생각났을 때 제목만으로 가볍게 던져두는 흐름이다. 본문·사진은 없어도 된다.

```json
// 요청
{ "title": "어제 본 그 영화 결말 다들 어떻게 해석함?" }

// 응답 201
{
  "id": "tpc_01HX...",
  "group_id": "grp_01HX...",
  "author_id": "usr_01HX...",
  "title": "어제 본 그 영화 결말 다들 어떻게 해석함?",
  "body": null,
  "status": "seed",
  "created_at": "2026-06-16T09:12:00Z",
  "updated_at": "2026-06-16T09:12:00Z"
}
```

### PATCH /topics/{id} — enrich

나중에 본문을 붙이면 상태가 `enriched`로 바뀐다. 작성자만 수정할 수 있다.

```json
// 요청
{ "body": "특히 마지막 5분이 회상인지 현재인지 애매한데..." }

// 응답 200
{
  "id": "tpc_01HX...",
  "status": "enriched",
  "body": "특히 마지막 5분이 회상인지 현재인지 애매한데...",
  "updated_at": "2026-06-16T11:40:00Z"
}
```

### POST /topics/{id}/media/presign — 업로드 URL 발급

클라이언트는 발급받은 presigned URL로 MinIO에 직접 PUT 업로드한 뒤, `POST /topics/{id}/media`로 확정한다.

```json
// 요청
{ "content_type": "image/webp", "byte_size": 184320 }

// 응답 200
{
  "object_key": "topics/tpc_01HX/img_a1b2c3.webp",
  "upload_url": "https://minio.example/jamye/topics/tpc_01HX/img_a1b2c3.webp?X-Amz-Signature=...",
  "expires_in": 600
}
```

## WebSocket 프로토콜

### 엔드포인트와 인증

```
/ws?token=<jwt>
```

연결 시 쿼리스트링의 JWT를 검증한다. 검증에 실패하면 즉시 연결을 close한다. 클라이언트는 `partysocket`으로 연결을 맺고 재연결·백오프와 heartbeat를 직접 관리한다 (socket.io-client는 사용하지 않는다). 인증 모델 전반은 [인증 모델](#인증-모델)을 참고한다.

### client → server

| 메시지 | 페이로드 | 설명 |
|---|---|---|
| `join_room` | `{ chatroom_id }` | 채팅방 입장 (구독 시작) |
| `leave_room` | `{ chatroom_id }` | 채팅방 퇴장 |
| `send_message` | `{ chatroom_id, body, client_msg_id }` | 메시지 전송. `client_msg_id`는 클라이언트가 생성하는 멱등 키로, 낙관적 렌더링과 ack 매칭·중복 방지에 쓴다 |

### server → client

| 메시지 | 페이로드 | 설명 |
|---|---|---|
| `message` | `{ id, chatroom_id, sender_id, body, type, created_at }` | 방의 다른 멤버에게 브로드캐스트되는 일반 메시지 |
| `message_ack` | `{ client_msg_id, message_id }` | 전송한 메시지의 영속 완료 확인. `client_msg_id`로 낙관적 메시지를 확정 처리 |
| `system` | `{ chatroom_id, body }` | 시스템 메시지 (새 주제·첫 채팅 리마인드). `sender_id`는 null |
| `error` | `{ code, detail }` | 처리 실패 (권한 없음, 잘못된 방 등) |

> `presence`(접속 표시)와 `typing`(입력 중 표시)은 2차 범위다. 1차에서는 전송하지 않는다.

### 흐름 1 — 메시지 전송 → ack → 브로드캐스트

```mermaid
sequenceDiagram
    participant A as 보낸 사람 (클라)
    participant WS as FastAPI WebSocket
    participant DB as PostgreSQL
    participant B as 같은 방 멤버 (클라)

    A->>A: 낙관적 렌더 (client_msg_id 생성)
    A->>WS: send_message{chatroom_id, body, client_msg_id}
    WS->>DB: 메시지 영속 (message_id 발급)
    WS-->>A: message_ack{client_msg_id, message_id}
    A->>A: 낙관적 메시지 → 확정 처리
    WS-->>B: message{id, chatroom_id, sender_id, body, ...}
```

### 흐름 2 — 새 주제 → 리마인드 시스템 메시지

새 주제가 등록되거나 주제방에 첫 채팅이 달리면, 서버가 그룹 메인 채팅방에 시스템 메시지를 브로드캐스트하고 동시에 Web Push·인앱 알림을 발송한다 (T11 리마인드 시스템). 알림 발송 경로는 [tech-stack](./tech-stack.md)의 Web Push 절을 참고한다.

```mermaid
sequenceDiagram
    participant U as 작성자 (클라)
    participant API as FastAPI REST
    participant SVC as 리마인드 서비스
    participant WS as WebSocket 허브
    participant M as 메인방 멤버들

    U->>API: POST /groups/{id}/topics (새 주제)
    API->>SVC: 주제 생성 이벤트
    SVC->>WS: 메인방 system{chatroom_id, body}
    WS-->>M: system{...} (리마인드 표시)
    SVC->>SVC: push_subscriptions 발송 + 인앱 notification 생성
```

## 인증 모델

- **REST**: OAuth 콜백에서 발급한 JWT를 **httpOnly 쿠키**로 전달한다. 브라우저가 자동으로 쿠키를 실어 보내고, FastAPI가 매 요청에서 JWT를 검증한다.
- **WebSocket**: 쿠키 대신 `/ws?token=<jwt>` 쿼리로 토큰을 받아 연결 시 검증하고, 실패하면 close한다.
- **2중 방어**: SPA 클라이언트 가드는 UX(라우팅·리다이렉트)를 담당하고, 실보안은 FastAPI의 JWT 검증(401/403)이 담당한다. 클라이언트 가드만으로 자원을 보호하지 않는다.

상세 토큰 수명·OAuth provider 설정은 [tech-stack](./tech-stack.md)를 참고한다.
