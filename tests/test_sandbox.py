from core.sandbox import execute, static_check

OK = "import cadquery as cq\nresult = cq.Workplane('XY').box(10, 10, 10)\n"


def test_ok_exports_step():
    r = execute(OK)
    assert r.ok and r.step_path.exists() and r.shape.Volume() > 999


def test_missing_result():
    r = execute("import cadquery as cq\nx = 1\n")
    assert not r.ok and "result" in r.error


def test_banned_import_and_calls():
    assert "os" in static_check("import os\n")
    assert static_check("open('/etc/passwd')") is not None
    assert static_check("x = ().__class__") is not None


def test_timeout():
    r = execute("import cadquery as cq\nwhile True:\n    pass\nresult = 1\n", timeout_s=3)
    assert not r.ok and "超时" in r.error


def test_runtime_error_reports_traceback():
    r = execute("import cadquery as cq\nresult = cq.Workplane('XY').box(1,1,1).faces('>Z').fillet(50)\n")
    assert not r.ok and r.error


def test_relative_workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = execute(OK, workdir="rel/dir")
    assert r.ok
