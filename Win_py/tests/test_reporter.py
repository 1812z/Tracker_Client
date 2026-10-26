from app.reporter import Reporter


class FakeConfig:
    def __init__(self, report_enabled=True, configured=True):
        self._report_enabled = report_enabled
        self._configured = configured

    def get(self, key, default=None):
        if key == "report_enabled":
            return self._report_enabled
        return default

    def is_report_configured(self):
        return self._configured

    def snapshot(self):
        return {
            "api_url": "https://example.com/api",
            "secret_key": "secret",
            "device_id": "device",
        }


class FakeClient:
    def __init__(self):
        self.calls = []

    def post_report(self, payload, max_retries=3, timeout=None):
        self.calls.append(payload)
        return True, ""


def test_battery_fields_only_for_valid_range():
    reporter = Reporter(FakeConfig(), FakeClient(), battery_provider=lambda: (50, True))
    payload = reporter._build_payload("微信", True)
    assert payload["batteryLevel"] == 50
    assert payload["isCharging"] is True

    reporter = Reporter(FakeConfig(), FakeClient(), battery_provider=lambda: (-1, False))
    payload = reporter._build_payload("桌面", True)
    assert "batteryLevel" not in payload
    assert "isCharging" not in payload


def test_submit_deduplicates_successful_and_pending_apps():
    reporter = Reporter(FakeConfig(), FakeClient(), battery_provider=lambda: (None, None))

    reporter.submit("A", True)
    assert reporter._pending == ("A", True)

    reporter.submit("A", True)
    assert reporter._pending == ("A", True)

    reporter._pending = None
    reporter._last_success = "A"
    reporter.submit("A", True)
    assert reporter._pending is None


def test_disabled_or_unconfigured_skips_submit():
    reporter = Reporter(FakeConfig(report_enabled=False), FakeClient())
    reporter.submit("A", True)
    assert reporter._pending is None

    reporter = Reporter(FakeConfig(configured=False), FakeClient())
    reporter.submit("A", True)
    assert reporter._pending is None


class FailingClient:
    def __init__(self):
        self.calls = []

    def post_report(self, payload, max_retries=3, timeout=None):
        self.calls.append(payload)
        return False, "网络请求失败"


def test_shutdown_report_success_clears_marker(tmp_path, monkeypatch):
    marker = tmp_path / "pending_shutdown.json"
    monkeypatch.setattr("app.reporter.pending_shutdown_path", lambda: marker)

    client = FakeClient()
    reporter = Reporter(FakeConfig(), client, battery_provider=lambda: (None, None))

    assert reporter.send_shutdown_report() is True
    assert client.calls[-1]["app_name"] == "设备关机"
    assert client.calls[-1]["running"] is False
    assert not marker.exists()


def test_shutdown_report_failure_keeps_marker(tmp_path, monkeypatch):
    marker = tmp_path / "pending_shutdown.json"
    monkeypatch.setattr("app.reporter.pending_shutdown_path", lambda: marker)

    reporter = Reporter(FakeConfig(), FailingClient(), battery_provider=lambda: (None, None))

    assert reporter.send_shutdown_report() is False
    assert marker.exists()


def test_flush_pending_shutdown_reports_and_clears(tmp_path, monkeypatch):
    marker = tmp_path / "pending_shutdown.json"
    monkeypatch.setattr("app.reporter.pending_shutdown_path", lambda: marker)
    marker.write_text('{"app_name": "设备关机", "at": 1}', encoding="utf-8")

    client = FakeClient()
    reporter = Reporter(FakeConfig(), client, battery_provider=lambda: (None, None))

    assert reporter.flush_pending_shutdown() is True
    assert client.calls[-1]["app_name"] == "设备关机"
    assert not marker.exists()


def test_flush_pending_shutdown_without_marker_is_noop(tmp_path, monkeypatch):
    marker = tmp_path / "pending_shutdown.json"
    monkeypatch.setattr("app.reporter.pending_shutdown_path", lambda: marker)

    client = FakeClient()
    reporter = Reporter(FakeConfig(), client, battery_provider=lambda: (None, None))

    assert reporter.flush_pending_shutdown() is False
    assert client.calls == []

