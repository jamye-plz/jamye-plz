# 데이터 모델

PostgreSQL 위 11개 테이블로 사용자·그룹·잼얘(주제)·채팅·알림을 표현한다. 권한은 RLS 대신 서비스 레이어에서 `memberships` 기반으로 강제한다.

> 버전 v1 · 2026-06-16 · SSOT: plan.json

---

## 1. ERD

```mermaid
erDiagram
    users ||--o{ memberships : "가입"
    users ||--o{ groups : "소유(owner)"
    groups ||--o{ memberships : "구성"
    groups ||--o{ invites : "발급"
    users ||--o{ invites : "생성"
    groups ||--o{ topics : "보유"
    users ||--o{ topics : "작성"
    topics ||--o{ topic_media : "첨부"
    topics ||--o{ topic_tags : "태그"
    groups ||--o{ chatrooms : "보유"
    topics ||--o| chatrooms : "주제방"
    chatrooms ||--o{ messages : "기록"
    users ||--o{ messages : "발신"
    users ||--o{ push_subscriptions : "구독"
    users ||--o{ notifications : "수신"

    users {
        id PK
        provider "kakao|google"
        provider_id
        nickname
        avatar_url
        created_at
    }
    groups {
        id PK
        name
        owner_id FK
        max_members "default 12"
        created_at
    }
    memberships {
        id PK
        group_id FK
        user_id FK
        role "owner|member"
        joined_at
    }
    invites {
        id PK
        group_id FK
        code "unique"
        created_by FK
        expires_at
        max_uses
        used_count
        created_at
    }
    topics {
        id PK
        group_id FK
        author_id FK
        title
        body "text null"
        status "seed|enriched"
        created_at
        updated_at
    }
    topic_media {
        id PK
        topic_id FK
        type "image"
        object_key
        width
        height
        byte_size
        created_at
    }
    topic_tags {
        id PK
        topic_id FK
        tag
        source "ai|user"
        confidence "float null"
    }
    chatrooms {
        id PK
        group_id FK
        type "topic|main"
        topic_id FK "null for main"
        created_at
    }
    messages {
        id PK
        chatroom_id FK
        sender_id FK "null for system"
        client_msg_id "null for system; UNIQUE(sender_id,client_msg_id)"
        body
        type "user|system"
        created_at
    }
    push_subscriptions {
        id PK
        user_id FK
        endpoint "unique"
        p256dh
        auth
        created_at
    }
    notifications {
        id PK
        user_id FK
        type
        payload "jsonb"
        read_at "null"
        created_at
    }
```

관계 요약:

- `users` N:M `groups` via `memberships`
- `groups` 1:N `topics`
- `topics` 1:N `topic_media`, 1:N `topic_tags`
- `groups` 1:N `chatrooms` (main 1개 + topic N개)
- `chatrooms` 1:N `messages`
- `users` 1:N `push_subscriptions`, 1:N `notifications`

---

## 2. 테이블 명세

### users
사용자 계정. OAuth 제공자별로 식별한다.

| 컬럼 | 타입/값 | 제약 |
|------|---------|------|
| id | PK | |
| provider | `kakao` \| `google` | |
| provider_id | 제공자 측 사용자 ID | |
| nickname | 닉네임 | |
| avatar_url | 아바타 URL | nullable(미설정 시 기본 아바타) |
| created_at | timestamp | |

- **제약**: `UNIQUE(provider, provider_id)` — 같은 제공자 계정 중복 가입 방지.

### groups
폐쇄 그룹. 초대로만 합류한다.

| 컬럼 | 타입/값 | 제약 |
|------|---------|------|
| id | PK | |
| name | 그룹 이름 | |
| owner_id | → `users` | FK |
| max_members | int | default 12 |
| created_at | timestamp | |

### memberships
사용자-그룹 N:M 연결 + 역할. 권한의 기준점이다.

| 컬럼 | 타입/값 | 제약 |
|------|---------|------|
| id | PK | |
| group_id | → `groups` | FK |
| user_id | → `users` | FK |
| role | `owner` \| `member` | |
| joined_at | timestamp | |

- **제약**: `UNIQUE(group_id, user_id)` — 한 그룹에 한 번만 가입.

### invites
초대 코드/링크. 만료·사용횟수 제한.

| 컬럼 | 타입/값 | 제약 |
|------|---------|------|
| id | PK | |
| group_id | → `groups` | FK |
| code | 초대 코드 | UNIQUE |
| created_by | → `users` | FK |
| expires_at | timestamp | 만료 시각 |
| max_uses | int | 최대 사용 횟수 |
| used_count | int | 현재 사용 횟수 |
| created_at | timestamp | |

- 합류 시 `expires_at` 경과 또는 `used_count >= max_uses`면 거부. 그룹 인원이 `groups.max_members`에 도달해도 거부.

### topics
잼얘(주제). 시드로 먼저 던지고 나중에 enrich한다.

| 컬럼 | 타입/값 | 제약 |
|------|---------|------|
| id | PK | |
| group_id | → `groups` | FK |
| author_id | → `users` | FK |
| title | 제목 | 시드 단계에 title만으로 생성 가능 |
| body | text | nullable |
| status | `seed` \| `enriched` | |
| created_at | timestamp | |
| updated_at | timestamp | |

- 시드 등록은 `title`만으로 `status=seed`. 본문·사진을 추가하면 `status=enriched`. 수정은 작성자만.

### topic_media
주제에 첨부된 이미지. MinIO 객체를 참조한다.

| 컬럼 | 타입/값 | 제약 |
|------|---------|------|
| id | PK | |
| topic_id | → `topics` | FK |
| type | `image` | |
| object_key | MinIO 객체 키 | |
| width | int | |
| height | int | |
| byte_size | int | |
| created_at | timestamp | |

- presigned PUT으로 클라가 직접 MinIO에 업로드한 뒤, `object_key`·치수를 confirm한다.

### topic_tags
주제 태그. AI 자동 태그와 사용자 수정 태그를 함께 담는다.

| 컬럼 | 타입/값 | 제약 |
|------|---------|------|
| id | PK | |
| topic_id | → `topics` | FK |
| tag | 태그 문자열 | |
| source | `ai` \| `user` | |
| confidence | float | nullable(`ai`일 때 분류 신뢰도) |

- **제약**: `UNIQUE(topic_id, tag)` — 한 주제에 같은 태그 중복 방지.
- WASM e5-small 임베딩 zero-shot 분류 결과는 `source=ai`. 사용자가 고치면 `source=user`.

### chatrooms
채팅방. 그룹당 메인 1개 + 주제별 N개.

| 컬럼 | 타입/값 | 제약 |
|------|---------|------|
| id | PK | |
| group_id | → `groups` | FK |
| type | `topic` \| `main` | |
| topic_id | → `topics` | nullable (main은 null) |
| created_at | timestamp | |

- `type=main`은 그룹당 1개. `type=topic`은 `topic_id`로 주제와 연결.

### messages
채팅 메시지. 사용자 메시지와 시스템(리마인드) 메시지.

| 컬럼 | 타입/값 | 제약 |
|------|---------|------|
| id | PK | |
| chatroom_id | → `chatrooms` | FK |
| sender_id | → `users` | nullable (system은 null) |
| client_msg_id | 클라 생성 멱등 키 | nullable (system은 null) |
| body | 본문 | |
| type | `user` \| `system` | |
| created_at | timestamp | |

- **제약**: `UNIQUE(sender_id, client_msg_id)` — `client_msg_id IS NOT NULL`인 행만 대상이다(PostgreSQL은 NULL을 서로 다른 값으로 취급하므로 `sender_id`·`client_msg_id`가 모두 null인 system 메시지는 제약에서 자연 제외된다). WS 재연결이나 ack 유실 후 클라가 같은 `client_msg_id`로 재전송해도 서버가 같은 키를 중복 영속하지 않아 **멱등성**이 보장된다.
- 리마인드(새 주제/첫 채팅)는 메인 채팅방에 `type=system` 메시지로 들어간다(`sender_id`·`client_msg_id` 모두 null).
- 클라는 `client_msg_id`로 낙관적 전송하고 서버 `message_ack`로 확정한다. 위 unique 제약이 멱등성의 실제 보장 장치다(WS 프로토콜은 [`./api-contract.md`](./api-contract.md) 참고).

### push_subscriptions
Web Push 구독 정보(VAPID).

| 컬럼 | 타입/값 | 제약 |
|------|---------|------|
| id | PK | |
| user_id | → `users` | FK |
| endpoint | 푸시 엔드포인트 | UNIQUE |
| p256dh | 공개키 | |
| auth | 인증 시크릿 | |
| created_at | timestamp | |

### notifications
인앱 알림 목록. 푸시 미지원 환경의 fallback이자 알림 이력.

| 컬럼 | 타입/값 | 제약 |
|------|---------|------|
| id | PK | |
| user_id | → `users` | FK |
| type | 알림 종류 | |
| payload | jsonb | 이동 대상 리소스 등 |
| read_at | timestamp | nullable(읽음 시각) |
| created_at | timestamp | |

---

## 3. 권한 모델 (RLS 대체)

매니지드 BaaS의 Row Level Security를 쓰지 않고, **서비스 레이어에서 `memberships`를 기준으로 권한을 강제**한다.

- **그룹 리소스 접근**: 해당 그룹의 멤버만 topics·chatrooms·messages 등에 접근할 수 있다. 비멤버 요청은 403.
- **수정·삭제**: 리소스 작성자(`author_id`/`sender_id`) 또는 그룹 오너(`memberships.role = owner`)만 수정·삭제할 수 있다.
- **조회 범위**: `GET /groups`는 요청자가 멤버인 그룹만 반환한다.

이 검증은 FastAPI service 레이어에서 일관되게 수행한다. router는 인증된 사용자만 통과시키고(토큰 검증은 [`./tech-stack.md`](./tech-stack.md) ADR-4), 실제 자원 권한은 service가 판정한다.

---

## 4. 마이그레이션

- **도구**: Alembic.
- 전체 엔티티 스키마는 단일 마이그레이션 단계(태스크 T3)에서 생성한다.
- 클린 아키텍처상 repository가 ORM 모델에 접근하고, service가 트랜잭션 경계를 잡는다.

---

## 5. 관련 문서

- 스택·권한 강제 위치 → [`./tech-stack.md`](./tech-stack.md)
- REST·WebSocket API 계약 → [`./api-contract.md`](./api-contract.md)
- 배포(PostgreSQL native + 백업) → [`./deployment.md`](./deployment.md)
- 기능 명세 → [`../product/features.md`](../product/features.md)
