# Task Board — M0 보완 (session oma-00mqs5jo4nitvc61k2)

Status: ⬜ todo · 🟦 in_progress · ✅ done

## API Contract (LOCKED)
- `GET /api/groups/{gid}/topics?date=YYYY-MM-DD&cursor&limit` — date 옵션(Asia/Seoul 일 경계). TopicOut에 `unread: bool` 추가.
- `GET /api/groups/{gid}/topics/dates` → `{ dates: string[] (YYYY-MM-DD desc, today 항상 포함), today: string }`.
- `POST /api/groups/{gid}/chatrooms/{cid}/read` → 204. read upsert + 해당 topic의 new_topic/chat_unread 알림 read 처리.
- chat_unread 알림: type=`chat_unread`, title `{topic_title}에 대해 안 읽은 채팅이 있어요`, body=group_name, action_url=topic chat. dedup_key=`chat_unread:{tid}`.
- new_topic 알림: dedup_key=`new_topic:{tid}` (생성시 set).

## Tasks
- 🟦 BE: chatroom_reads 모델+repo, notification.dedup_key+migration, config.app_timezone, topic date filter + /dates, unread batch, chatroom read endpoint, WS chat_unread bump, notification view+upsert/clear, pure-logic tests.
- 🟦 FE: types(unread,TopicDates), api(getTopicDates, markChatroomRead), 주제목록 날짜탭+파란점(정리됨 제거), ChatRoom mark-read.

## Sync point
- TopicOut.unread, /topics/dates, POST read, listTopics?date — 계약 위 고정. FE/BE 병렬 가능.
