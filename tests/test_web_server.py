"""Web backend tests with a fake LLM (no network / API key)."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from core.config import load_config
from core.models import PartSpec
from web.server import app as appmod
from web.server import jobs as jobs_mod

CODE = "```python\nimport cadquery as cq\nresult = cq.Workplane('XY').box(%d, 20, 10)\n```"


class FakeLLM:
    def __init__(self, cfg):
        self.usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}

    def structured(self, messages, model, retries=1):
        self.usage["calls"] += 1
        missing = ["长度"] if "NEEDINFO" in messages[-1]["content"] else []
        return PartSpec(part_type="盒子", missing=missing)

    def chat(self, messages, json_mode=False):
        self.usage["calls"] += 1
        return CODE % (40 if "更长" in messages[-1]["content"] else 20)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-secret")
    monkeypatch.setattr(jobs_mod, "make_llm", FakeLLM)
    app = appmod.create_app(data_dir=tmp_path, cfg=load_config(appmod.ROOT / "config.yaml"))
    with TestClient(app) as c:
        yield c


def events(c, rid, version=None):
    url = f"/api/runs/{rid}/events" + (f"?version={version}" if version else "")
    out = []
    with c.stream("GET", url) as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        name = None
        for ln in r.iter_lines():
            if ln.startswith("event: "):
                name = ln[7:]
            elif ln.startswith("data: "):
                out.append((name, json.loads(ln[6:])))
    return out


def wait(c, rid, status="success", t=60):
    end = time.time() + t
    while time.time() < end:
        s = c.get(f"/api/runs/{rid}").json()["status"]
        if s not in ("queued", "running"):
            return s
        time.sleep(0.2)
    raise AssertionError("timeout")


def test_health(client):
    assert client.get("/api/health").json() == {"ok": True, "llm_configured": True, "auth_required": False, "authenticated": True}


def test_missing_key(client, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    assert client.get("/api/health").json()["llm_configured"] is False
    assert client.post("/api/runs", json={"request": "x"}).status_code == 503


def test_validation(client):
    assert client.post("/api/runs", json={"request": ""}).status_code == 422
    assert client.post("/api/runs", json={"request": "x" * 5000}).status_code == 422
    assert client.post("/api/runs", json={"request": "x", "config": "Z"}).status_code == 422


def test_create_sse_done_and_artifacts(client):
    rid = client.post("/api/runs", json={"request": "一个盒子", "config": "A"}).json()["id"]
    evs = events(client, rid)
    names = [n for n, _ in evs]
    assert names[:4] == ["parsing", "spec", "generating", "round"] and names[-1] == "done"
    assert evs[-1][1]["status"] == "success" and evs[-1][1]["version"] == 1
    arts = {d["name"] for n, d in evs if n == "artifact"}
    assert {"part.step", "part.py", "run.json", "render.png", "thumb.png", "part.glb", "drawing.pdf"} <= arts
    assert [n for n, _ in events(client, rid)] == names  # replay after completion
    d = client.get(f"/api/runs/{rid}").json()
    assert d["status"] == "success" and d["versions"] == [1] and d["runs"]["1"]["rounds"][0]["code"]
    assert "part.glb" in d["files"]["1"] and "events.jsonl" not in d["files"]["1"]
    r = client.get(f"/api/runs/{rid}/v1/part.glb")
    assert r.status_code == 200 and r.content[:4] == b"glTF"
    assert client.get(f"/api/runs/{rid}/v1/part.step").status_code == 200
    assert rid in [x["id"] for x in client.get("/api/runs").json()]


def test_need_info(client):
    rid = client.post("/api/runs", json={"request": "NEEDINFO"}).json()["id"]
    evs = events(client, rid)
    assert evs[-1] == ("done", {"status": "need_info", "version": 1, "usage": evs[-1][1]["usage"]})
    assert wait(client, rid) == "need_info"
    assert client.post(f"/api/runs/{rid}/modify", json={"change": "x"}).status_code == 409


def test_modify(client):
    rid = client.post("/api/runs", json={"request": "盒子", "config": "A"}).json()["id"]
    events(client, rid)
    wait(client, rid)
    assert client.post("/api/runs/nope/modify", json={"change": "x"}).status_code == 404
    r = client.post(f"/api/runs/{rid}/modify", json={"change": "更长"})
    assert r.json() == {"id": rid, "version": 2}
    evs = events(client, rid, 2)
    assert [e[0] for e in evs[:3]] == ["parsing", "spec", "generating"] and evs[-1][1]["version"] == 2
    d = client.get(f"/api/runs/{rid}").json()
    assert d["versions"] == [1, 2] and d["changes"]["2"] == "更长"
    assert d["runs"]["2"]["rounds"][0]["n"] == 2
    assert "box(40" in client.get(f"/api/runs/{rid}/v2/part.py").text
    assert "box(20" in client.get(f"/api/runs/{rid}/v1/part.py").text


def test_examples_readonly(client):
    ex = client.get("/api/examples").json()
    assert ex and ex[0]["id"].startswith("example-") and ex[0]["runs"]["1"]["status"] == "success"
    eid = ex[0]["id"]
    assert client.get(f"/api/runs/{eid}").json()["id"] == eid
    assert client.get(f"/api/runs/{eid}/v1/render.png").status_code == 200
    r = client.get(f"/api/runs/{eid}/v1/part.glb")
    assert r.status_code == 200 and r.content[:4] == b"glTF"
    assert events(client, eid)[-1][0] == "done"
    assert client.post(f"/api/runs/{eid}/modify", json={"change": "x"}).status_code == 403


@pytest.mark.parametrize("p", ["../../config.yaml", "..%2F..%2Fconfig.yaml", "meta.json", "events.jsonl", "%2e%2e/meta.json"])
def test_path_traversal(client, p):
    rid = client.post("/api/runs", json={"request": "NEEDINFO"}).json()["id"]
    events(client, rid)
    assert client.get(f"/api/runs/{rid}/v1/{p}").status_code == 404
    assert client.get(f"/api/runs/{rid}/events", params={"version": "../x"}).status_code == 422


def test_bad_ids(client):
    for rid in ["..", "a.b", "x" * 100, "example-nope"]:
        assert client.get(f"/api/runs/{rid}").status_code == 404
    assert client.get("/api/runs/..%2f..%2fetc/v1/part.py").status_code == 404


def test_no_secret_echo(client):
    for u in ("/api/health", "/api/runs", "/api/examples"):
        assert "sk-test-secret" not in client.get(u).text


def test_examples_multi_version(client):
    exs = {e["id"]: e for e in client.get("/api/examples").json()}
    assert {"example-bracket", "example-plate", "example-u_bracket"} <= set(exs)
    ex = exs["example-bracket"]
    assert ex["versions"] == [1, 2] and ex["changes"]["2"] and not ex["synthetic"]
    assert ex["selection"]["runs"] == 3 and isinstance(ex["selection"]["picked"], int)
    assert ex["runs"]["2"]["rounds"][0]["n"] == len(ex["runs"]["1"]["rounds"]) + 1
    for n in ("1", "2"):
        assert all(r["code"] for r in ex["runs"][n]["rounds"])
        assert {"part.step", "render.png", "drawing.pdf", "part.glb"} <= set(ex["files"][n])
    assert client.get("/api/runs/example-bracket/v2/part.glb").content[:4] == b"glTF"


def test_round_glb_files(client):
    rid = client.post("/api/runs", json={"request": "盒子", "config": "A"}).json()["id"]
    evs = events(client, rid)
    assert ("artifact", {"name": "rounds/r1.glb"}) in evs
    rnd = next(d for n, d in evs if n == "round")
    assert rnd["glb"] == "rounds/r1.glb"
    d = client.get(f"/api/runs/{rid}").json()
    assert d["runs"]["1"]["rounds"][0]["glb"] == "rounds/r1.glb" and "rounds/r1.glb" in d["files"]["1"]
    assert client.get(f"/api/runs/{rid}/v1/rounds/r1.glb").content[:4] == b"glTF"
    for bad in ("rounds/x.glb", "rounds/../meta.json", "rounds/r1.glb/../../meta.json", "rounds/r1.step"):
        assert client.get(f"/api/runs/{rid}/v1/{bad}").status_code == 404


def test_example_rounds(client):
    ex = {e["id"]: e for e in client.get("/api/examples").json()}["example-bracket"]
    rs = ex["runs"]["1"]["rounds"]
    assert not any(r.get("reconstructed") for r in rs)
    for r in rs:
        if r.get("glb"):
            assert r["glb"] in ex["files"]["1"]
            assert client.get(f"/api/runs/example-bracket/v1/{r['glb']}").content[:4] == b"glTF"
