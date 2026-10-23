"""Child-process entry: exec the script, export result to STEP. Run via `python -m core.sandbox.runner script.py out.step`."""
import json
import sys
import traceback


def main(script_path: str, step_path: str) -> int:
    import cadquery as cq

    code = open(script_path).read()
    ns: dict = {"__name__": "__cad_script__"}
    try:
        exec(compile(code, "script.py", "exec"), ns)
        res = ns.get("result")
        if res is None:
            raise RuntimeError("脚本必须定义变量 result(cq.Workplane 或 cq.Shape)")
        shape = res.val() if isinstance(res, cq.Workplane) else res
        if isinstance(res, cq.Workplane) and len(res.vals()) > 1:
            shape = cq.Compound.makeCompound(res.vals())  # type: ignore[arg-type]
        cq.exporters.export(cq.Workplane(obj=shape), step_path)
    except BaseException:
        tb = traceback.format_exc().splitlines()
        print(json.dumps({"ok": False, "error": "\n".join(tb[-8:])}))
        return 1
    print(json.dumps({"ok": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
