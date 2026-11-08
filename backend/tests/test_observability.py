from app.core.config import Settings
from app.core.observability import before_send, init_sentry


def test_sentry_is_disabled_without_dsn() -> None:
    assert init_sentry(Settings(sentry_dsn=None)) is False


def test_before_send_removes_bodies_cookies_credentials_and_pii() -> None:
    event = {
        "request": {
            "url": "https://api/x",
            "data": {"weight_kg": 80, "physical_limitations": "rodilla"},
            "cookies": {"zenith_refresh": "secret"},
            "query_string": "token=abc",
            "headers": {"Authorization": "Bearer abc", "User-Agent": "app"},
        },
        "user": {"id": "user-1", "email": "a@b.com", "ip_address": "1.2.3.4"},
        "extra": {"password": "x", "safe": 1},
    }

    cleaned = before_send(event, {})

    assert "data" not in cleaned["request"]
    assert "cookies" not in cleaned["request"]
    assert "query_string" not in cleaned["request"]
    assert cleaned["request"]["headers"]["Authorization"] == "[Filtered]"
    assert cleaned["request"]["headers"]["User-Agent"] == "app"
    assert cleaned["user"] == {"id": "user-1"}
    assert cleaned["extra"] == {"password": "[Filtered]", "safe": 1}
