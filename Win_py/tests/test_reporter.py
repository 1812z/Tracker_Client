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
