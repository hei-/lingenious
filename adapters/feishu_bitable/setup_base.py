"""Create the "CAD Agent 需求单" Base (idempotent via out/bitable/state.json)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.feishu_bitable import larkio  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "out" / "bitable" / "state.json"
BASE_NAME = "CAD Agent 需求单"
TABLE_NAME = "需求表"
DEMO = ("L 型铝支架:底板 100×60×6mm,立板沿长边,高 40mm、厚 3mm,"
        "底板四角各一个 M6 通孔,立板中间一个直径 20 的圆孔。")


def sel(name, opts):
    return {"type": "select", "name": name, "multiple": False, "options": [{"name": o} for o in opts]}


FIELDS = [
    {"type": "text", "name": "需求描述"},
    sel("材料", ["6061", "7075", "304", "45#"]),
    sel("工艺", ["CNC 铣削"]),
    sel("状态", ["待处理", "生成中", "已通过", "需补充", "需人工"]),
    {"type": "text", "name": "修改要求"},
    {"type": "text", "name": "需补充信息"},
    {"type": "number", "name": "迭代轮数", "style": {"type": "plain", "precision": 0}},
    {"type": "text", "name": "迭代日志"},
    {"type": "text", "name": "DFM 报告"},
    {"type": "attachment", "name": "渲染图"},
    {"type": "attachment", "name": "工程图"},
    {"type": "attachment", "name": "STEP"},
    {"type": "attachment", "name": "参数化脚本"},
    {"type": "number", "name": "版本", "style": {"type": "plain", "precision": 0}},
    {"type": "datetime", "name": "更新时间", "style": {"format": "yyyy-MM-dd HH:mm"}},
]


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def main() -> int:
    st = load_state()
    if not st.get("base_token"):
        d = larkio.run(["base", "+base-create", "--name", BASE_NAME, "--table-name", TABLE_NAME,
                        "--fields", json.dumps(FIELDS, ensure_ascii=False)])
        print(json.dumps(d, ensure_ascii=False)[:1500])
        data = d.get("data", d)
        base = data.get("base") or data
        st = {"base_token": base.get("base_token") or base.get("app_token"),
              "url": base.get("url"),
              "table_id": (data.get("table") or {}).get("table_id") or (data.get("table") or {}).get("id")}
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1))
    if not st.get("table_id"):
        tl = larkio.run(["base", "+table-list", "--base-token", st["base_token"]])
        print(json.dumps(tl, ensure_ascii=False)[:800])
        return 2
    if not st.get("demo_record"):
        r = larkio.run(["base", "+record-batch-create", "--base-token", st["base_token"], "--table-id", st["table_id"],
                        "--json", json.dumps({"create_records": [{"需求描述": DEMO, "材料": ["6061"], "工艺": ["CNC 铣削"], "状态": ["待处理"]}]}, ensure_ascii=False)])
        print(json.dumps(r, ensure_ascii=False)[:800])
        st["demo_record"] = True
        STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1))
    print("Base URL:", st.get("url"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
