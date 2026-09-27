from app.rate_limit import RateLimiter

def test_rate_limiter_enforces_and_expires_window(monkeypatch):
    clock=[100.0]
    monkeypatch.setattr("app.rate_limit.monotonic",lambda: clock[0])
    limiter=RateLimiter(limit=2,window_seconds=10)
    assert limiter.allow("u") is True
    assert limiter.allow("u") is True
    assert limiter.allow("u") is False
    clock[0]=111.0
    assert limiter.allow("u") is True

def test_rate_limiter_isolated_by_key():
    limiter=RateLimiter(limit=1,window_seconds=60)
    assert limiter.allow("a") is True
    assert limiter.allow("a") is False
    assert limiter.allow("b") is True
