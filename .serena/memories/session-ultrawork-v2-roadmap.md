# Ultrawork Session — v2 Roadmap 구현

- **시작**: 2026-07-19 (Asia/Seoul)
- **sid**: oma-00mrraurqqfch0nkha
- **워크플로**: ultrawork (5-Phase Gate Loop)
- **요청 요약**: `docs/planning/002-v2-roadmap.md` 기반 v2 구현.
  1. §7 Open Decisions D1~D8 사용자 확정 (D6 최우선, 권장안 기본)
  2. 마일스톤 순서: M0(스토리지)+M1(푸시) → M2(그룹) → M3(미디어) → M4a(음성). M4b는 vNext
  3. 마일스톤당 별도 브랜치+PR, 로드맵 문서는 첫 PR에 포함
  4. §8 품질 게이트 전 변경 적용 (backend: pytest/ruff/pyright, frontend: eslint/check/build)
  5. deferred 통합은 env-conditional + 로컬 fallback 필수
  6. M0 상세 계획 → 사용자 승인 → 구현 시작

## Phase Log

- Phase 0 (Init): 완료 — 필수 리소스 로드(coordination, context-loading, memory-protocol, event-spec, multi-review-protocol, quality-principles, phase-gates, vendor-detection), serena 활성화, 언어=ko, 런타임=Claude Code(native subagent)
- Phase 1 (PLAN): 완료 — D1~D8 확정(D7만 보류: sherpa-onnx vs faster-whisper 비교 후), M0 계획 승인(PLAN_GATE pass), plan JSON: .agents/results/plan-oma-00mrraurqqfch0nkha.json
- Phase 2 (IMPL): 완료 — backend-engineer(a2bb933a067c2968a)가 T1~T6 구현. Baseline: pytest 21 passed / ruff 0 / pyright 0. IMPL_GATE pass. 특이: 1차 스폰 중단 → SendMessage로 재개 완료. QA 확인 요청 사항: minio 컨테이너 healthcheck가 curl 의존(이미지에 curl 없을 수 있음)
- Phase 3 (VERIFY): 1차 FAIL — QA(a82969ef97e4dba63): HIGH 1(confirm object_key BOLA), MEDIUM 5(confirm MIME/size 미검증, ContentLength 미바인딩, minio healthcheck curl, prod fail-closed 부재, :latest 미고정). Step 5 복귀, backend 에이전트에 root-cause 수정 지시(반복 1/5). 안전 확인 항목: ContentType 서명 바인딩 OK, 인가 OK, TTL 600s OK, boto3 lru_cache OK
- Phase 3 (VERIFY) 2차: backend가 6건 전부 root-cause 수정(BOLA 가드 validate_object_key_for_topic, confirm validator, ContentLength 바인딩, mc ready healthcheck+이미지 핀, prod fail-closed, 회귀테스트 12건 추가 → pytest 33 passed). 오케스트레이터 스팟체크 통과. QA 재검증 PASS(우회 불가 확인, 프론트 fetch Content-Length 계약도 검증 — M3 주의: presign byteSize는 실제 File.size와 일치 필수). VERIFY_GATE pass
- Phase 4 (REFINE): 완료 — debug-investigator(a5c8597f62c92d10e) Steps 9-13 전부 clean, 수정 0건. REFINE_GATE pass
- T7 (docs sync): 완료 — docs-curator(abdf4c3174fa49d6d): api-contract.md 미디어 흐름 섹션+예시, 로드맵 §0/§2 상태 갱신, deployment/tech-stack 드리프트 없음. 오케스트레이터가 기존 경로 드리프트(`/api/topics/{id}` → 실제 `/api/groups/{gid}/topics/{tid}/...`, confirm은 `/media/confirm`) 직접 수정
- Phase 5 (SHIP): QA PASS — pytest 33/ruff/format/pyright 0, storage.py 커버리지 100%, fallback UX 계약 보존, docs↔router 정합(in-scope 100%), 배포 준비성 통과. EA: good_catch 1(QA가 BOLA 포착), false_positive 0, missed_stub 0. 사용자 최종 승인 대기
- Report-only 후속 티켓 후보: api-contract.md 사전 존재 갭(GET media/tags/dates/members 미문서화, chat/auth 경로 불일치, "24개" 카운트 부정확 — 실제 30 라우트)
- **M0 완료**: 사용자 승인(커밋만). 커밋 a9a4a32(feat backend) / 0e6d420(chore infra) / e4cb2e5(docs). push+PR은 사용자가 podman 스모크 후 직접. SHIP_GATE pass
- **M1 (Web Push)**: PLAN_GATE pass(사용자 승인). 브랜치 feat/m1-web-push(main 분기). Plan: .agents/results/plan-m1-oma-00mrraurqqfch0nkha.json. D2 보정: WS 경로 BackgroundTasks 불가 → asyncio.create_task 디스패처(arq는 M4a). 신규 발견: requestAndSubscribe가 base64url 문자열을 applicationServerKey에 직접 전달(Safari 비호환) → urlBase64ToUint8Array 필요
- M1 Phase 2 (IMPL): 완료 — backend(a2e7d07ec674b217c, 중단 2회→마지막 게이트는 오케스트레이터 인라인 마무리: vapid_claims dict[str,str|int] 타입 수정) + frontend(af033ec1fdbb3abc8, 중단 1회). 게이트 전부 clean(pytest 22/ruff/pyright 0 · prettier/eslint/svelte-check 0/build ok). 신규 파일: push_dispatch.py, test_push.py. 훅: topics.py create_topic(chat_path 재사용) + chat_service.py:222(url /groups/{gid}/topics/{tid}/chat — frontend 라우트 실존 확인). IMPL_GATE pass
- M1 Phase 3 (VERIFY): PASS 1차 — qa(a8e997f9fa2ec26aa): CRITICAL/HIGH/MEDIUM 0, LOW 4(발송 순차→gather 병렬화 후보, prod VAPID 미설정 startup 경고 부재, 해지 실패 시 토글 상태 우선순위, oldSubscription null 엣지). pywebpush 2.3.0 소스 확인·SW 계약 일치·훅 정확성 검증
- M1 Phase 4 (REFINE): PASS — debug(a89b989ddf123c4ac): except 블록 병합(WebPushException import 제거), 푸시 제목 "새 잼얘"→"새 주제" 용어 통일. backend 게이트 재실행 clean
- M1 T8 (docs): 완료 — api-contract.md push 섹션(vapid-public-key 행+흐름), 오케스트레이터가 milestone.md T14 상태 갱신. 범위 밖 드리프트: nixos-alfheim.md:114,250 "vapid_* 추후 추가" 낡음(후속)
- M1 Phase 5 (SHIP): QA PASS. **M1 완료** — 사용자 승인(커밋만): 58ca2bd(feat backend)/7a6b84b(feat frontend)/234cc4f(docs) on feat/m1-web-push. 사용자 요청 보고 완료(구현 요약, MinIO/VAPID env 가이드, 의존성 추가 없음, 실행 명령)
- **M2 (그룹 관리)**: PLAN_GATE pass. 브랜치 feat/m2-group-management(main 분기). 결정: deleted_at만(updated_at 제외), 멤버 컨트롤은 초대 페이지, 설정 페이지 신규(groups/[id]/settings). 계약: PATCH/DELETE /groups/{id}, DELETE·PATCH /groups/{id}/members/{user_id}, 403/404/409 시맨틱
- M2 Phase 2 (IMPL): backend 완료(a6f47f9da902c0eaf, 중단 1회) — 마이그레이션 c3d4e5f6a7b8(deleted_at, up/down --sql 렌더 검증), repo 필터+write, service 6메서드(set_member_role 디스패치), 라우터 4개, 테스트 17개(총 27 passed), 게이트 clean. member_count는 membership만 조회라 미필터(주석 문서화). frontend 완료(설정 페이지·초대 owner 컨트롤·5 API 함수, 게이트 clean). IMPL_GATE pass
- M2 Phase 3 (VERIFY) 1차 FAIL — qa(af3319b35696e9677): HIGH 2(require_membership soft-delete 미확인→토픽/채팅/멤버목록/초대/WS join 누수, 강퇴 멤버 WS 브로드캐스트 계속 수신), MEDIUM 1(이양 후 group 쿼리 무효화 누락), LOW 2(maxlength 50 vs 128, group.types main_chatroom_id 기존 부채). report-only: 이양 row-lock race(홈랩 부채), 고아 chatroom_reads/notifications. 반복 1/5, backend+frontend 수정 재스폰
- M2 수정 완료: backend(require_membership에 get_group_or_404 선행 cascade, require_member_access 그룹 생존 확인, ws_hub user 추적+evict_user 4001, ChatroomRepository.list_by_group, 테스트 45개) + frontend(group 쿼리 무효화, maxlength 128)
- M2 VERIFY 2차 PASS (403→404 시맨틱은 일관성 개선 판정. report-only: is_member 삭제그룹 미확인{joined:false}, 요청당 그룹 조회 +1 수용). REFINE PASS. T7 docs 완료(+오케스트레이터가 role row 서술 정정). SHIP WARNING(MEDIUM: rename/delete 성공경로 테스트 부재)→오케스트레이터 인라인 보완(47 passed). **M2 완료**: 커밋 efd7f1b/c320b07/6fc3525
- **PR 생성 완료(사용자 지시)**: #16(M0) #17(M1) #18(M2), 3개 브랜치 push됨
- **PR 리뷰 대응 완료(사용자 지시)**: Codex 봇 리뷰 5건 전부 타당 판정→수정→push→스레드 답글.
  - #16 M0: prod에서 MinIO endpoint localhost/non-https 거부(d427651, +2 tests)
  - #17 M1: (a) push endpoint SSRF 검증 https+사설host 거부(f39680c, +5 tests) (b) upsert user_id 재할당+프론트 mount 재등록(reconcilePush) (c) DELETE endpoint별 삭제 delete_push_subscription_if_present(a9ab765) + doc(1a276d4)
  - #18 M2: redeem_invite에 get_group_or_404 선행→삭제 그룹 초대 404(03032ad)
  - #17 2차 재리뷰(1a276d4) 3건 추가 대응: (P1) reconcile 실패 시 토글 off+힌트로 게이트(d45e129), (P1) webpush timeout=10s, (P2) ttl=1일(0891e2e, +test) — 게이트 clean, push+답글 완료
  - #17 3차 재리뷰(d45e129) 2건: (P2) vapid-public-key는 vapid_enabled일 때만 반환(반쪽 구성 시 빈 문자열, +2 tests), (P2) getSubscription null이면 서버 unsubscribe 스킵(전체삭제 fallback 방지) — f4c2219, 게이트 clean, push+답글
  - #17 4차(f4c2219 재리뷰) 2건: (P1) 로그아웃 시 detachPushOnLogout로 구독 정리(크로스계정 차단), (P1) SSRF 숫자별칭(127.1/2130706433/0x..) inet_aton 정규화 — 7399389, +tests
  - #18 2차(03032ad 재리뷰) 2건: (P2) transfer_ownership row-lock(get_by_id_for_update FOR UPDATE), (P2) soft_delete_group에 ws_hub.evict_room 전체 소켓 축출 — d3cb731, +test(48 passed)
  - #17 5차(7399389 재리뷰) 2건: (P2) detachPushOnLogout .ready→getRegistration(로그아웃 무한대기 방지), (P2) reconcileOrRecreate로 VAPID 키 회전 시 재구독 — 2a41374
  - #18 3차(d3cb731 재리뷰) 1건: (P2) 삭제/탈퇴 시 dropGroupCaches로 group/members/topics/topic-dates 캐시 제거 — d126af3
  - #17 6차(2a41374 재리뷰) 3건: (P1) send_push 전송경로 endpoint 재검증+prune(SSRF 헬퍼를 core/push_endpoint.py로 이관), (P2) detach 시 서버 실패해도 브라우저 unsubscribe 독립 실행, (P2) SW pushsubscriptionchange가 현재 VAPID 키 fetch 후 재구독 — 78f2d00, +test(32 passed)
  - #18 4차(d126af3 재리뷰) 2건: (P2) remove_member/leave_group도 get_by_id_for_update 락+role 재확인(transfer와 직렬화), (P2) dropGroupCaches에 ['topic']/['messages'] prefix 제거 — 56fbf31
  - #17 7차(78f2d00 재리뷰) 2건: (P1) is_global 기준으로 CGNAT 100.64/10 등 non-global 거부, (P2) send_push가 rollback으로 커넥션 반환 후 네트워크 I/O, prune은 배치 트랜잭션 — f61e537, +tests(33 passed)
  - #18 5차(56fbf31 재리뷰) 1건: (P2) ChatRoom onclose 4001 축출 시 group/topic/message 캐시 제거+/groups 리다이렉트 — 7a17d80
  - #17 8차(f61e537 재리뷰) 1건: (P2) rollback 후 ORM sub.id 접근=MissingGreenlet → id 스냅샷+delete_by_id로 prune — c68e6a2
  - #18 6차(7a17d80 재리뷰) 1건: (P2) soft_delete_group/update_group_name도 get_by_id_for_update 락(transfer와 직렬화) — 36f0bce
  - **/loop 자동 모니터 가동 중**(job 2eaa3def, 10분 주기): 새 Codex 코멘트 타당성판단→수정→답글→resolve 자동. 이 라운드는 loop 첫 실행에서 처리.
  - #18 7차(36f0bce 재리뷰) 1건: (P2) create_topic도 lock_group_or_404(FOR UPDATE)로 soft-delete와 직렬화 — 20a1565. 다른 write 경로(enrich/tags/msg)는 orphan-row 저영향이라 미락(답글에 명시)
  - **loop 주의**: 이번 실행 초반 git checkout 누락으로 main에서 편집→pyright 에러로 감지→discard 후 정확 브랜치서 재작업. 향후 loop은 편집 전 반드시 해당 브랜치 checkout 확인
  - #17 9차(c68e6a2 재리뷰) 2건: (P1) send_push에 _NoRedirectSession(allow_redirects=False)로 SSRF-via-redirect 차단, (P1) PushReconciler(루트 레이아웃)로 매 로그인 시 구독 재청구 reclaimPushForCurrentUser — 5d9149b, +tests
  - #18 8차(36f0bce 재리뷰) 3건: (P2) redeem_invite에 lock_group_or_404 추가(3dc6742). topics 공지·chat 메시지 2건은 proportionality 판단으로 미수정+답글 resolve(create는 이미 락 보호, chat 메시지별 그룹락은 throughput 저해, orphan-row 저영향)
  - 게이트 clean. 누적: #16×1, #17×20(9라운드), #18×12(8라운드). 전 스레드 resolved 유지. 판단: 유효하지만 fix가 disproportionate한 경우(chat 메시지별 락) 근거 명시 후 resolve
  - 모든 수정 게이트 clean. **추가 코멘트 없을 때까지 대기 후 머지 예정**(사용자 지시). 그 다음 M3.
- **M3 (채팅 미디어)**: 대기 — PR 머지 후 최신 main에서 feat/m3-chat-media 분기 예정. PLAN_GATE는 이미 사용자 승인. M0 storage 의존+M2 chat_service/main.py 겹침 주의
