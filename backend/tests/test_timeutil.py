"""Unit tests for the pure timezone / unread helpers (no DB)."""

from datetime import datetime, timedelta, timezone

from app.core.timeutil import seoul_day_window, today_str, topic_is_unread


class TestSeoulDayWindow:
    def test_midday_window_utc_boundaries(self) -> None:
        # Asia/Seoul is UTC+9 (no DST): a KST calendar day starts at 15:00Z the
        # previous day and ends at 15:00Z the same day.
        start, end = seoul_day_window("2026-06-25")
        assert start == datetime(2026, 6, 24, 15, 0, tzinfo=timezone.utc)
        assert end == datetime(2026, 6, 25, 15, 0, tzinfo=timezone.utc)
        assert start.tzinfo is not None and end.tzinfo is not None

    def test_window_is_exactly_24h(self) -> None:
        start, end = seoul_day_window("2026-01-01")
        assert end - start == timedelta(hours=24)

    def test_month_end_rollover_does_not_crash(self) -> None:
        # Regression: day+1 arithmetic crashed on the last day of a month.
        start, end = seoul_day_window("2026-06-30")
        assert start == datetime(2026, 6, 29, 15, 0, tzinfo=timezone.utc)
        assert end == datetime(2026, 6, 30, 15, 0, tzinfo=timezone.utc)

    def test_year_end_rollover(self) -> None:
        start, end = seoul_day_window("2026-12-31")
        assert end == datetime(2026, 12, 31, 15, 0, tzinfo=timezone.utc)
        # next day is 2027-01-01 KST → 2026-12-31T15:00Z .. 2027-01-01T15:00Z
        assert end - start == timedelta(hours=24)


class TestTodayStr:
    def test_format_is_yyyy_mm_dd(self) -> None:
        s = today_str()
        assert len(s) == 10
        y, m, d = s.split("-")
        assert len(y) == 4 and len(m) == 2 and len(d) == 2


class TestTopicIsUnread:
    def _t(self, offset_seconds: int) -> datetime:
        base = datetime(2026, 6, 25, 0, 0, tzinfo=timezone.utc)
        return base + timedelta(seconds=offset_seconds)

    def test_no_read_record_is_unread(self) -> None:
        # A brand-new topic the user has never opened is unread.
        assert topic_is_unread(None, self._t(0), None) is True

    def test_read_after_creation_no_messages_is_read(self) -> None:
        created = self._t(0)
        read = self._t(10)
        assert topic_is_unread(read, created, None) is False

    def test_new_message_after_read_is_unread(self) -> None:
        created = self._t(0)
        read = self._t(10)
        latest_msg = self._t(20)
        assert topic_is_unread(read, created, latest_msg) is True

    def test_message_before_read_is_read(self) -> None:
        created = self._t(0)
        latest_msg = self._t(5)
        read = self._t(10)
        assert topic_is_unread(read, created, latest_msg) is False

    def test_naive_datetimes_are_coerced_to_utc(self) -> None:
        # Defensive: mixed naive/aware inputs must not raise.
        created_naive = datetime(2026, 6, 25, 0, 0)
        read_naive = datetime(2026, 6, 25, 0, 0, 1)
        assert topic_is_unread(read_naive, created_naive, None) is False
