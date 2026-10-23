"""scripts/export_demo.py must produce exactly what the server serves for the bundled examples."""
import importlib.util
import json

from fastapi.testclient import TestClient

from core.config import load_config
from web.server import app as appmod


def _exporter():
    spec = importlib.util.spec_from_file_location("export_demo", appmod.ROOT / "scripts" / "export_demo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_export_matches_api(tmp_path):
    out = tmp_path / "demo-data"
    _exporter().export(appmod.ROOT / "examples", out)
    exported = json.loads((out / "examples.json").read_text())

    app = appmod.create_app(data_dir=tmp_path / "data", cfg=load_config(appmod.ROOT / "config.yaml"))
    with TestClient(app) as c:
        assert c.get("/api/examples").json() == exported
        ex = exported[0]
        n = str(ex["versions"][0])
        assert c.get(f"/api/runs/{ex['id']}").json() == ex
        for f in ex["files"][n]:
            assert (out / "runs" / ex["id"] / f"v{n}" / f).read_bytes() == c.get(f"/api/runs/{ex['id']}/v{n}/{f}").content

    assert {e["id"] for e in exported} >= {"example-bracket", "example-plate", "example-u_bracket"}
    for e in exported:
        for n, files in e["files"].items():
            assert files and all((out / "runs" / e["id"] / f"v{n}" / f).is_file() for f in files)
