from fastapi.testclient import TestClient

from app.core import rate_limit
from app.core.config import get_settings
from app.core.rate_limit import RateLimitExceededError, check_rate_limit, rate_limit_bucket_count
from tests.test_ai_training_plans import SessionFactory, client_with_db, register_and_login  # noqa: F401


def test_rate_limit_blocks_after_limit() -> None:
    check_rate_limit(key="k", limit=2, window_seconds=60)
    check_rate_limit(key="k", limit=2, window_seconds=60)
    try:
        check_rate_limit(key="k", limit=2, window_seconds=60)
    except RateLimitExceededError:
        pass
    else:
        raise AssertionError("Expected rate limit")


def test_rate_limit_sweeps_expired_buckets(monkeypatch) -> None:
    clock = [1_000.0]
    monkeypatch.setattr(rate_limit, "monotonic", lambda: clock[0])
    rate_limit.clear_rate_limit_state()
    for index in range(50):
        check_rate_limit(key=f"ip-{index}", limit=5, window_seconds=60)
    assert rate_limit_bucket_count() == 50

    clock[0] += 120
    check_rate_limit(key="fresh", limit=5, window_seconds=60)

    assert rate_limit_bucket_count() == 1


def test_ai_endpoints_are_rate_limited_per_user(monkeypatch, client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, _session_factory = client_with_db
    monkeypatch.setenv("APP_AI_RATE_LIMIT_PER_MINUTE", "2")
    get_settings.cache_clear()
    token = register_and_login(client, "ai-limit@example.com", "ai_limit")
    other = register_and_login(client, "ai-limit-2@example.com", "ai_limit_2")
    headers = {"Authorization": f"Bearer {token}"}
    body = {"message": "Hola", "personal_data_acknowledged": True}

    statuses = [client.post("/ai/coach/messages", headers=headers, json=body).status_code for _ in range(3)]
    other_status = client.post("/ai/coach/messages", headers={"Authorization": f"Bearer {other}"}, json=body).status_code
    get_settings.cache_clear()

    assert statuses[:2] == [200, 200]
    assert statuses[2] == 429
    assert other_status == 200
