"""Unit tests for Web Push (VAPID): NotificationService.send_push and
app.services.push_dispatch.dispatch_push / schedule_push_dispatch.

pywebpush performs a real HTTP call, so `webpush` is monkeypatched at the
module boundary (`app.services.notification_service.webpush`) in every test
that exercises the enabled path. There is no API test harness for this repo
yet, so everything here is unit-level: fake repo/session objects stand in
for the DB, per the milestone's testing convention. This file is
self-contained and does not depend on any other test module or fixture.
"""

import asyncio
import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from pywebpush import WebPushException

from app.services import notification_service as notification_service_module
from app.services import push_dispatch as push_dispatch_module
from app.services.notification_service import NotificationService

PAYLOAD = {"title": "그룹 새 잼얘", "body": "오늘 뭐 먹지", "url": "/groups/g1/topics/t1/chat"}


# ── Fakes ────────────────────────────────────────────────────────────────────


class FakeAsyncSession:
    """Stands in for AsyncSession: only commit() is exercised by send_push."""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


@dataclass
class FakeSub:
    id: str
    user_id: str
    endpoint: str
    p256dh: str
    auth: str


class FakePushRepo:
    def __init__(self, subs: list[FakeSub]) -> None:
        self._subs = subs
        self.deleted: list[FakeSub] = []
        self.prune_calls: list[tuple[str, int]] = []
        self.locked: list[str] = []
        self.calls: list[str] = []

    async def list_by_user(self, user_id: str, limit: int | None = None) -> list[FakeSub]:
        rows = [s for s in self._subs if s.user_id == user_id]
        if limit is not None:
            rows = rows[-limit:]  # "most recent" = last inserted in the fake
        return rows

    async def delete(self, sub: FakeSub) -> None:
        self.deleted.append(sub)
        self._subs = [s for s in self._subs if s is not sub]

    async def delete_by_id(self, sub_id: str) -> None:
        self.deleted.append(sub_id)
        self._subs = [s for s in self._subs if s.id != sub_id]

    async def upsert(self, user_id: str, endpoint: str, p256dh: str, auth: str) -> FakeSub:
        for s in self._subs:
            if s.endpoint == endpoint:
                s.user_id, s.p256dh, s.auth = user_id, p256dh, auth
                return s
        sub = FakeSub(id=endpoint, user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
        self._subs.append(sub)
        return sub

    async def prune_to_limit(self, user_id: str, limit: int) -> None:
        self.calls.append("prune")
        self.prune_calls.append((user_id, limit))
        kept = [s for s in self._subs if s.user_id == user_id][-limit:]
        self._subs = [s for s in self._subs if s.user_id != user_id or s in kept]

    async def lock_user_subscriptions(self, user_id: str) -> None:
        self.calls.append("lock")
        self.locked.append(user_id)


def _settings(*, vapid_enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(
        vapid_enabled=vapid_enabled,
        vapid_private_key="fake-private-key",
        vapid_public_key="fake-public-key",
        vapid_claim_email="admin@example.com",
    )


def _make_service(
    db: FakeAsyncSession, subs: list[FakeSub]
) -> tuple[NotificationService, FakePushRepo]:
    svc = NotificationService(db)
    push_repo = FakePushRepo(subs)
    svc._push_repo = push_repo  # bypass the real DB-backed repo
    return svc, push_repo


# ── (a) enabled path: send to all subscriptions with correct args ──────────


class TestSendPushEnabled:
    async def test_sends_to_all_subscriptions_with_correct_args(self, monkeypatch) -> None:
        calls: list[dict[str, Any]] = []

        def fake_webpush(**kwargs: Any) -> str:
            calls.append(kwargs)
            return "ok"

        monkeypatch.setattr(notification_service_module, "webpush", fake_webpush)
        monkeypatch.setattr(
            notification_service_module, "get_settings", lambda: _settings(vapid_enabled=True)
        )

        subs = [
            FakeSub(
                id="s1", user_id="u1", endpoint="https://push.example/1", p256dh="p1", auth="a1"
            ),
            FakeSub(
                id="s2", user_id="u1", endpoint="https://push.example/2", p256dh="p2", auth="a2"
            ),
        ]
        db = FakeAsyncSession()
        svc, push_repo = _make_service(db, subs)

        await svc.send_push("u1", PAYLOAD)

        assert len(calls) == 2
        for call, sub in zip(calls, subs, strict=True):
            assert call["subscription_info"] == {
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            }
            assert call["data"] == json.dumps(PAYLOAD)
            assert call["vapid_private_key"] == "fake-private-key"
            assert call["vapid_claims"] == {"sub": "mailto:admin@example.com"}
            # Bounded timeout (no worker-thread exhaustion) + nonzero TTL
            # (offline devices get queued instead of dropped).
            assert call["timeout"] == notification_service_module.PUSH_REQUEST_TIMEOUT_SECONDS
            assert call["ttl"] == notification_service_module.PUSH_TTL_SECONDS
            assert call["ttl"] > 0
        assert push_repo.deleted == []
        assert db.commits == 0
        # DB connection released before the outbound sends (pool not held).
        assert db.rollbacks == 1

    async def test_no_subscriptions_is_a_no_op(self, monkeypatch) -> None:
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr(notification_service_module, "webpush", lambda **kw: calls.append(kw))
        monkeypatch.setattr(
            notification_service_module, "get_settings", lambda: _settings(vapid_enabled=True)
        )
        db = FakeAsyncSession()
        svc, _ = _make_service(db, subs=[])

        await svc.send_push("u1", PAYLOAD)

        assert calls == []


# ── (b) WebPushException 404/410 prunes only that subscription ─────────────


class TestSendPushPrunesExpired:
    async def test_410_prunes_only_that_subscription_others_still_sent(self, monkeypatch) -> None:
        calls: list[dict[str, Any]] = []

        def fake_webpush(**kwargs: Any) -> str:
            calls.append(kwargs)
            if kwargs["subscription_info"]["endpoint"] == "https://push.example/2":
                raise WebPushException("gone", response=SimpleNamespace(status_code=410))
            return "ok"

        monkeypatch.setattr(notification_service_module, "webpush", fake_webpush)
        monkeypatch.setattr(
            notification_service_module, "get_settings", lambda: _settings(vapid_enabled=True)
        )

        subs = [
            FakeSub(
                id="s1", user_id="u1", endpoint="https://push.example/1", p256dh="p1", auth="a1"
            ),
            FakeSub(
                id="s2", user_id="u1", endpoint="https://push.example/2", p256dh="p2", auth="a2"
            ),
            FakeSub(
                id="s3", user_id="u1", endpoint="https://push.example/3", p256dh="p3", auth="a3"
            ),
        ]
        db = FakeAsyncSession()
        svc, push_repo = _make_service(db, subs)

        await svc.send_push("u1", PAYLOAD)

        # all three attempted despite the middle one raising
        assert len(calls) == 3
        assert push_repo.deleted == ["s2"]
        assert db.commits == 1

    async def test_404_also_prunes(self, monkeypatch) -> None:
        def fake_webpush(**kwargs: Any) -> str:
            raise WebPushException("not found", response=SimpleNamespace(status_code=404))

        monkeypatch.setattr(notification_service_module, "webpush", fake_webpush)
        monkeypatch.setattr(
            notification_service_module, "get_settings", lambda: _settings(vapid_enabled=True)
        )
        subs = [
            FakeSub(
                id="s1", user_id="u1", endpoint="https://push.example/e1", p256dh="p1", auth="a1"
            )
        ]
        db = FakeAsyncSession()
        svc, push_repo = _make_service(db, subs)

        await svc.send_push("u1", PAYLOAD)

        assert push_repo.deleted == ["s1"]
        assert db.commits == 1

    async def test_other_status_logs_and_does_not_prune(self, monkeypatch) -> None:
        def fake_webpush(**kwargs: Any) -> str:
            raise WebPushException("server error", response=SimpleNamespace(status_code=500))

        monkeypatch.setattr(notification_service_module, "webpush", fake_webpush)
        monkeypatch.setattr(
            notification_service_module, "get_settings", lambda: _settings(vapid_enabled=True)
        )
        subs = [
            FakeSub(
                id="s1", user_id="u1", endpoint="https://push.example/e1", p256dh="p1", auth="a1"
            )
        ]
        db = FakeAsyncSession()
        svc, push_repo = _make_service(db, subs)

        await svc.send_push("u1", PAYLOAD)  # must not raise

        assert push_repo.deleted == []
        assert db.commits == 0

    async def test_unexpected_exception_logs_and_continues(self, monkeypatch) -> None:
        calls: list[str] = []

        def fake_webpush(**kwargs: Any) -> str:
            endpoint = kwargs["subscription_info"]["endpoint"]
            calls.append(endpoint)
            if endpoint == "https://push.example/e1":
                raise RuntimeError("network blip")
            return "ok"

        monkeypatch.setattr(notification_service_module, "webpush", fake_webpush)
        monkeypatch.setattr(
            notification_service_module, "get_settings", lambda: _settings(vapid_enabled=True)
        )
        subs = [
            FakeSub(
                id="s1", user_id="u1", endpoint="https://push.example/e1", p256dh="p1", auth="a1"
            ),
            FakeSub(
                id="s2", user_id="u1", endpoint="https://push.example/e2", p256dh="p2", auth="a2"
            ),
        ]
        db = FakeAsyncSession()
        svc, push_repo = _make_service(db, subs)

        await svc.send_push("u1", PAYLOAD)  # must not raise

        assert calls == ["https://push.example/e1", "https://push.example/e2"]
        assert push_repo.deleted == []

    async def test_unsafe_stored_endpoint_is_pruned_not_sent(self, monkeypatch) -> None:
        """A row whose endpoint predates the validator must be pruned, not sent."""
        sent: list[str] = []
        monkeypatch.setattr(
            notification_service_module,
            "webpush",
            lambda **kw: sent.append(kw["subscription_info"]["endpoint"]),
        )
        monkeypatch.setattr(
            notification_service_module, "get_settings", lambda: _settings(vapid_enabled=True)
        )
        subs = [
            FakeSub(id="bad", user_id="u1", endpoint="http://127.0.0.1/x", p256dh="p", auth="a"),
            FakeSub(
                id="ok",
                user_id="u1",
                endpoint="https://push.example/ok",
                p256dh="p",
                auth="a",
            ),
        ]
        db = FakeAsyncSession()
        svc, push_repo = _make_service(db, subs)

        await svc.send_push("u1", PAYLOAD)

        assert push_repo.deleted == ["bad"]
        assert sent == ["https://push.example/ok"]


# ── (c) disabled → no webpush calls (silent no-op) ──────────────────────────


class TestSendPushDisabled:
    async def test_no_webpush_calls_when_vapid_disabled(self, monkeypatch) -> None:
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr(notification_service_module, "webpush", lambda **kw: calls.append(kw))
        monkeypatch.setattr(
            notification_service_module, "get_settings", lambda: _settings(vapid_enabled=False)
        )

        subs = [
            FakeSub(
                id="s1", user_id="u1", endpoint="https://push.example/e1", p256dh="p1", auth="a1"
            )
        ]
        db = FakeAsyncSession()
        svc, push_repo = _make_service(db, subs)

        list_by_user_called = False
        original_list_by_user = push_repo.list_by_user

        async def spy_list_by_user(*args: Any, **kwargs: Any) -> list[FakeSub]:
            nonlocal list_by_user_called
            list_by_user_called = True
            return await original_list_by_user(*args, **kwargs)

        push_repo.list_by_user = spy_list_by_user  # type: ignore[method-assign]

        await svc.send_push("u1", PAYLOAD)

        assert calls == []
        assert list_by_user_called is False, "disabled path must not touch the repo"


# ── (e) payload contract: exactly {title, body, url} ────────────────────────


class TestPayloadContract:
    async def test_payload_serializes_exactly_title_body_url(self, monkeypatch) -> None:
        captured: dict[str, Any] = {}

        def fake_webpush(**kwargs: Any) -> str:
            captured["data"] = kwargs["data"]
            return "ok"

        monkeypatch.setattr(notification_service_module, "webpush", fake_webpush)
        monkeypatch.setattr(
            notification_service_module, "get_settings", lambda: _settings(vapid_enabled=True)
        )
        subs = [
            FakeSub(
                id="s1", user_id="u1", endpoint="https://push.example/e1", p256dh="p1", auth="a1"
            )
        ]
        db = FakeAsyncSession()
        svc, _ = _make_service(db, subs)

        payload = {"title": "제목", "body": "내용", "url": "/groups/g/topics/t/chat"}
        await svc.send_push("u1", payload)

        decoded = json.loads(captured["data"])
        assert set(decoded.keys()) == {"title", "body", "url"}
        assert decoded == payload


# ── (d) dispatch_push swallows every exception ──────────────────────────────


class _FakeSessionCtx:
    """Minimal async-context-manager stand-in for an AsyncSession."""

    async def __aenter__(self) -> "_FakeSessionCtx":
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class TestDispatchPush:
    async def test_swallows_send_push_exceptions_and_processes_all_users(self, monkeypatch) -> None:
        monkeypatch.setattr(push_dispatch_module, "_get_session_factory", lambda: _FakeSessionCtx)

        called: list[str] = []

        class FakeNotificationService:
            def __init__(self, db: Any) -> None:
                self.db = db

            async def send_push(self, user_id: str, payload: dict[str, Any]) -> None:
                called.append(user_id)
                raise RuntimeError("boom")

        monkeypatch.setattr(push_dispatch_module, "NotificationService", FakeNotificationService)

        # Must not raise, and must still attempt every user despite each failing.
        await push_dispatch_module.dispatch_push(["u1", "u2"], PAYLOAD)

        assert called == ["u1", "u2"]

    async def test_swallows_session_factory_errors(self, monkeypatch) -> None:
        def boom() -> Any:
            raise RuntimeError("no db configured")

        monkeypatch.setattr(push_dispatch_module, "_get_session_factory", boom)

        await push_dispatch_module.dispatch_push(["u1"], PAYLOAD)  # must not raise

    async def test_schedule_push_dispatch_runs_task_and_cleans_up(self, monkeypatch) -> None:
        called: list[tuple[list[str], dict[str, Any]]] = []

        async def fake_dispatch(user_ids: list[str], payload: dict[str, Any]) -> None:
            called.append((user_ids, payload))

        monkeypatch.setattr(push_dispatch_module, "dispatch_push", fake_dispatch)

        push_dispatch_module.schedule_push_dispatch(["u1"], PAYLOAD)
        # Let the scheduled task run to completion.
        for _ in range(3):
            await asyncio.sleep(0)

        assert called == [(["u1"], PAYLOAD)]
        assert push_dispatch_module._background_tasks == set()

    def test_schedule_push_dispatch_is_a_no_op_for_empty_user_ids(self, monkeypatch) -> None:
        created: list[Any] = []
        monkeypatch.setattr(
            push_dispatch_module.asyncio, "create_task", lambda coro: created.append(coro)
        )

        push_dispatch_module.schedule_push_dispatch([], PAYLOAD)

        assert created == []


# ── Endpoint SSRF validation (PushSubscribeBody) ─────────────────────────────


class TestEndpointSsrfValidation:
    def test_accepts_public_https_push_endpoint(self) -> None:
        from app.routers.push import PushSubscribeBody

        body = PushSubscribeBody(
            endpoint="https://fcm.googleapis.com/fcm/send/abc123",
            p256dh="p",
            auth="a",
        )
        assert body.endpoint.startswith("https://")

    def test_rejects_non_https(self) -> None:
        import pytest

        from app.routers.push import PushSubscribeBody

        with pytest.raises(ValueError):
            PushSubscribeBody(endpoint="http://push.example/x", p256dh="p", auth="a")

    def test_rejects_localhost(self) -> None:
        import pytest

        from app.routers.push import PushSubscribeBody

        with pytest.raises(ValueError):
            PushSubscribeBody(endpoint="https://localhost/x", p256dh="p", auth="a")

    def test_rejects_loopback_host_aliases(self) -> None:
        """ip6-localhost / ip6-loopback resolve to ::1 via the default /etc/hosts."""
        import pytest

        from app.routers.push import PushSubscribeBody

        for host in ("ip6-localhost", "ip6-loopback", "localhost.localdomain", "IP6-LOCALHOST"):
            with pytest.raises(ValueError):
                PushSubscribeBody(endpoint=f"https://{host}:8443/x", p256dh="p", auth="a")

    def test_rejects_multicast_literals(self) -> None:
        """Python 3.12+ marks multicast as is_global; reject it explicitly."""
        import pytest

        from app.routers.push import PushSubscribeBody

        for host in ("224.0.0.1", "[ff02::1]"):
            with pytest.raises(ValueError):
                PushSubscribeBody(endpoint=f"https://{host}/x", p256dh="p", auth="a")

    def test_rejects_private_ip_literal(self) -> None:
        import pytest

        from app.routers.push import PushSubscribeBody

        with pytest.raises(ValueError):
            PushSubscribeBody(endpoint="https://169.254.169.254/latest", p256dh="p", auth="a")

    def test_rejects_loopback_ip_literal(self) -> None:
        import pytest

        from app.routers.push import PushSubscribeBody

        with pytest.raises(ValueError):
            PushSubscribeBody(endpoint="https://127.0.0.1:9000/x", p256dh="p", auth="a")

    def test_rejects_numeric_alias_hosts(self) -> None:
        """127.1 / decimal / hex forms the OS resolver maps to loopback/metadata."""
        import pytest

        from app.routers.push import PushSubscribeBody

        for host in ("127.1", "2130706433", "0x7f000001", "0xa9fea9fe"):
            with pytest.raises(ValueError):
                PushSubscribeBody(endpoint=f"https://{host}/x", p256dh="p", auth="a")

    def test_accepts_public_ip_literal(self) -> None:
        from app.routers.push import PushSubscribeBody

        body = PushSubscribeBody(endpoint="https://93.184.216.34/x", p256dh="p", auth="a")
        assert body.endpoint.startswith("https://")

    def test_rejects_cgnat_shared_range(self) -> None:
        """100.64.0.0/10 (CGNAT/Tailscale) isn't is_private but isn't global."""
        import pytest

        from app.routers.push import PushSubscribeBody

        with pytest.raises(ValueError):
            PushSubscribeBody(endpoint="https://100.64.0.1/x", p256dh="p", auth="a")


# ── vapid-public-key endpoint gates on full provisioning ─────────────────────


class TestVapidPublicKeyEndpoint:
    async def test_returns_key_when_fully_enabled(self, monkeypatch) -> None:
        from app.routers import push as push_module

        monkeypatch.setattr(
            push_module,
            "get_settings",
            lambda: SimpleNamespace(vapid_public_key="pub", vapid_enabled=True),
        )
        out = await push_module.get_vapid_public_key()
        assert out.public_key == "pub"

    async def test_returns_empty_when_half_configured(self, monkeypatch) -> None:
        from app.routers import push as push_module

        # public key set but private missing -> vapid_enabled False -> hide toggle
        monkeypatch.setattr(
            push_module,
            "get_settings",
            lambda: SimpleNamespace(vapid_public_key="pub", vapid_enabled=False),
        )
        out = await push_module.get_vapid_public_key()
        assert out.public_key == ""


# ── outbound push POST refuses redirects (SSRF-via-redirect) ─────────────────


class TestNoRedirectSession:
    def test_post_forces_allow_redirects_false(self, monkeypatch) -> None:
        import requests

        from app.services.notification_service import _NoRedirectSession

        captured: dict[str, Any] = {}

        def fake_super_post(self, url, **kwargs):  # noqa: ANN001
            captured.update(kwargs)
            return SimpleNamespace(status_code=201)

        monkeypatch.setattr(requests.Session, "post", fake_super_post)
        _NoRedirectSession().post("https://push.example/x", data=b"d")
        assert captured["allow_redirects"] is False

    async def test_send_push_passes_no_redirect_session(self, monkeypatch) -> None:
        from app.services.notification_service import _NoRedirectSession

        seen: list[Any] = []
        monkeypatch.setattr(
            notification_service_module,
            "webpush",
            lambda **kw: seen.append(kw.get("requests_session")),
        )
        monkeypatch.setattr(
            notification_service_module, "get_settings", lambda: _settings(vapid_enabled=True)
        )
        subs = [
            FakeSub(id="s1", user_id="u1", endpoint="https://push.example/1", p256dh="p", auth="a")
        ]
        db = FakeAsyncSession()
        svc, _ = _make_service(db, subs)

        await svc.send_push("u1", PAYLOAD)

        assert len(seen) == 1
        assert isinstance(seen[0], _NoRedirectSession)


# ── per-user subscription cap bounds fan-out ─────────────────────────────────


class TestSubscriptionCap:
    async def test_upsert_prunes_to_per_user_limit(self) -> None:
        db = FakeAsyncSession()
        svc, push_repo = _make_service(db, subs=[])

        await svc.upsert_push_subscription(
            user_id="u1", endpoint="https://push.example/new", p256dh="p", auth="a"
        )

        assert push_repo.prune_calls == [
            ("u1", notification_service_module.MAX_PUSH_SUBSCRIPTIONS_PER_USER)
        ]
        assert push_repo.locked == ["u1"]
        # Advisory lock must be taken BEFORE the prune so the cap is atomic.
        assert push_repo.calls.index("lock") < push_repo.calls.index("prune")
        assert db.commits == 1


# ── send fan-out is bounded even when stored rows exceed the cap ──────────────


class TestSendFanOutCap:
    async def test_send_push_only_targets_capped_recent_subscriptions(self, monkeypatch) -> None:
        sent: list[str] = []
        monkeypatch.setattr(
            notification_service_module,
            "webpush",
            lambda **kw: sent.append(kw["subscription_info"]["endpoint"]),
        )
        monkeypatch.setattr(
            notification_service_module, "get_settings", lambda: _settings(vapid_enabled=True)
        )
        cap = notification_service_module.MAX_PUSH_SUBSCRIPTIONS_PER_USER
        # More stored rows than the cap (e.g. predating it / inserted directly).
        subs = [
            FakeSub(
                id=f"s{i}",
                user_id="u1",
                endpoint=f"https://push.example/{i}",
                p256dh="p",
                auth="a",
            )
            for i in range(cap + 5)
        ]
        db = FakeAsyncSession()
        svc, _ = _make_service(db, subs)

        await svc.send_push("u1", PAYLOAD)

        assert len(sent) == cap
