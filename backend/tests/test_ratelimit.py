from app.core.ratelimit_core import RateLimiter


def test_blocks_after_max_hits_until_the_window_slides():
    now = [0.0]
    rl = RateLimiter(max_hits=3, window_s=60, clock=lambda: now[0])
    for _ in range(3):
        assert rl.blocked("k") == 0
        rl.hit("k")
    assert rl.blocked("k") == 60                 # blocked; first hit expires in 60 s
    now[0] = 30
    assert rl.blocked("k") == 30
    now[0] = 61
    assert rl.blocked("k") == 0                  # oldest hit slid out
    assert rl.blocked("other") == 0              # keys are independent


async def test_login_is_throttled_after_5_failures(client):
    from app.api.routes.auth_routes import LOGIN_FAILS, LOGIN_IP
    LOGIN_FAILS.reset(); LOGIN_IP.reset()
    await client.post("/auth/register", json={"email": "rl@auth.com", "password": "correct-horse"})
    for _ in range(5):
        assert (await client.post("/auth/login", json={"email": "rl@auth.com", "password": "wrong-guess"})).status_code == 401
    r = await client.post("/auth/login", json={"email": "rl@auth.com", "password": "correct-horse"})
    assert r.status_code == 429                  # even the right password waits out the window
    assert int(r.headers["Retry-After"]) > 0
    LOGIN_FAILS.reset(); LOGIN_IP.reset()
