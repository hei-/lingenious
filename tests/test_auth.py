"""Optional access token for the web app (LINGENIOUS_ACCESS_TOKEN) and LINGENIOUS__* config overrides."""
import pytest
from fastapi.testclient import TestClient

from core.config import apply_env_overrides, load_config
from web.server import app as appmod
from web.server import auth as authmod

TOKEN = "s3cret-token-value"
H = {"Authorization": f"Bearer {TOKEN}"}


def make(tmp_path, token, monkeypatch):
    monkeypatch.delenv("LINGENIOUS_ACCESS_TOKEN", raising=False)
    return TestClient(appmod.create_app(data_dir=tmp_path, cfg=load_config(appmod.ROOT / "config.yaml"), access_token=token))


@pytest.fixture
def secured(tmp_path, monkeypatch):
    with make(tmp_path, TOKEN, monkeypatch) as c:
        yield c


def test_open_when_no_token(tmp_path, monkeypatch):
    with make(tmp_path, None, monkeypatch) as c:
        assert c.get("/api/runs").status_code == 200
        assert c.get("/api/health").json()["auth_required"] is False
        assert c.post("/api/auth/login", json={"token": "x"}).json() == {"ok": True, "auth_required": False}


def test_env_var_enables_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("LINGENIOUS_ACCESS_TOKEN", TOKEN)
    with TestClient(appmod.create_app(data_dir=tmp_path, cfg=load_config(appmod.ROOT / "config.yaml"))) as c:
        assert c.get("/api/runs").status_code == 401
        assert c.get("/api/runs", headers=H).status_code == 200


def test_health_open_and_reports(secured):
    h = secured.get("/api/health")
    assert h.status_code == 200 and h.json()["auth_required"] is True and h.json()["authenticated"] is False
    assert secured.get("/api/health", headers=H).json()["authenticated"] is True


@pytest.mark.parametrize("path", ["/api/runs", "/api/examples", "/api/runs/example-bracket", "/api/runs/example-bracket/v1/render.png",
                                  "/api/runs/example-bracket/events", "/api/nope"])
def test_api_requires_token(secured, path):
    r = secured.get(path)
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer" and TOKEN not in r.text
    assert secured.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert secured.get(path, headers={"Authorization": TOKEN}).status_code == 401  # scheme required
    assert secured.get(path, headers=H).status_code != 401


def test_post_requires_token(secured):
    assert secured.post("/api/runs", json={"request": "x"}).status_code == 401
    assert secured.post("/api/runs/example-bracket/modify", json={"change": "x"}).status_code == 401
    assert secured.post("/api/runs/example-bracket/modify", json={"change": "x"}, headers=H).status_code == 403


def test_static_ui_public(secured, tmp_path, monkeypatch):
    dist = tmp_path / "dist"; dist.mkdir(); (dist / "index.html").write_text("<html>ui</html>")
    monkeypatch.setenv("LINGENIOUS_UI_DIST", str(dist))
    with make(tmp_path / "d", TOKEN, monkeypatch) as c:
        assert c.get("/").text == "<html>ui</html>"
        assert c.get("/some/route").status_code == 200
        assert c.get("/api/runs").status_code == 401


def test_cookie_flow(secured):
    assert secured.post("/api/auth/login", json={"token": "bad"}).status_code == 401
    assert secured.get("/api/runs").status_code == 401
    r = secured.post("/api/auth/login", json={"token": TOKEN})
    assert r.status_code == 200 and TOKEN not in r.text
    sc = r.headers["set-cookie"]
    assert "HttpOnly" in sc and "SameSite=strict" in sc and "Path=/" in sc and TOKEN not in sc
    assert secured.get("/api/examples").status_code == 200  # cookie jar, no header
    assert secured.get("/api/runs/example-bracket/v1/render.png").status_code == 200
    assert secured.get("/api/health").json()["authenticated"] is True
    assert secured.post("/api/auth/logout").status_code == 200
    assert secured.get("/api/examples").status_code == 401


def test_forged_cookie_rejected(secured):
    secured.cookies.set(authmod.COOKIE, "x" * 64)
    assert secured.get("/api/runs").status_code == 401
    secured.cookies.set(authmod.COOKIE, TOKEN)  # the raw token is not a valid session value
    secured.cookies.set(authmod.COOKIE, TOKEN, path="/")
    assert secured.get("/api/runs").status_code == 401


def test_login_rate_limit(secured):
    for _ in range(authmod.MAX_FREE_FAILS):
        assert secured.post("/api/auth/login", json={"token": "bad"}).status_code == 401
    r = secured.post("/api/auth/login", json={"token": TOKEN})  # even the right token is refused while backing off
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1


def test_backoff_expires_and_resets():
    now = [0.0]
    a = authmod.Auth(TOKEN, clock=lambda: now[0])
    for _ in range(authmod.MAX_FREE_FAILS - 1):
        a.record_failure("1.2.3.4")
    assert a.retry_after("1.2.3.4") == 0
    a.record_failure("1.2.3.4")
    first = a.retry_after("1.2.3.4")
    assert first >= 1
    now[0] += first
    assert a.retry_after("1.2.3.4") == 0
    a.record_failure("1.2.3.4")
    assert a.retry_after("1.2.3.4") > first          # exponential
    assert a.retry_after("9.9.9.9") == 0             # per client
    a.record_success("1.2.3.4")
    assert a.retry_after("1.2.3.4") == 0


def test_token_not_logged(secured, caplog):
    secured.post("/api/auth/login", json={"token": TOKEN})
    secured.get("/api/runs", headers={"Authorization": "Bearer nope"})
    assert TOKEN not in caplog.text


# ---- config overrides
def test_env_override_types():
    cfg = {"agent": {"max_rounds": 4}, "llm": {"model": "a"}, "dfm": {"material_overrides": {"6061": {"min_wall_thickness": 1.5}}}}
    env = {"LINGENIOUS__AGENT__MAX_ROUNDS": "3", "LINGENIOUS__LLM__MODEL": "deepseek-reasoner", "LINGENIOUS__SANDBOX__MEM_MB": "2048",
           "LINGENIOUS__DFM__MIN_WALL_WARN": "2.5", "LINGENIOUS__DFM__MATERIAL_OVERRIDES__6061__MIN_WALL_THICKNESS": "1.0",
           "LINGENIOUS__FLAG": "true", "LINGENIOUS_DATA": "/x", "OTHER": "1"}
    out = apply_env_overrides(cfg, env)
    assert out["agent"]["max_rounds"] == 3 and isinstance(out["agent"]["max_rounds"], int)
    assert out["llm"]["model"] == "deepseek-reasoner" and out["sandbox"]["mem_mb"] == 2048
    assert out["dfm"]["min_wall_warn"] == 2.5 and out["dfm"]["material_overrides"]["6061"]["min_wall_thickness"] == 1.0
    assert out["flag"] is True and "data" not in out


def test_load_config_applies_env(tmp_path, monkeypatch):
    p = tmp_path / "c.yaml"; p.write_text("agent:\n  max_rounds: 4\n")
    monkeypatch.setenv("LINGENIOUS__AGENT__MAX_ROUNDS", "7")
    assert load_config(p)["agent"]["max_rounds"] == 7
    assert load_config(p, env={})["agent"]["max_rounds"] == 4


def test_bundle_requires_auth(secured):
    assert secured.get("/api/runs/example-bracket/v1/bundle.zip").status_code == 401
    assert secured.get("/api/runs/example-bracket/v1/bundle.zip", headers=H).status_code == 200
