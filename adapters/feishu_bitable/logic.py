"""Pure-function layer: record parsing, trigger decisions, DFM report, field mapping. No I/O."""
from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional

LEVEL_RULES = {
    "L1": [("valid_solid", "实体有效"), ("single_solid", "单一实体"), ("positive_volume", "体积为正")],
    "L2": [("bbox_match", "包围盒"), ("hole_count", "孔数"), ("hole_diameter", "孔径"),
           ("volume_range", "体积范围"), ("hole_breakout", "孔贯穿边缘")],
    "L3": [("hole_edge_distance", "孔边距"), ("internal_corner_radius", "内凹圆角"),
           ("min_wall_thickness", "最小壁厚"), ("hole_spacing", "孔间距")],
}
LEVEL_TITLE = {"L0": "L0 脚本执行", "L1": "L1 几何有效性", "L2": "L2 需求符合度", "L3": "L3 可制造性(DFM)"}


def cell_text(v: Any) -> str:
    """Normalize a Bitable cell (str / list of str / list of rich-text dicts / None) to text."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "".join(cell_text(x) if not isinstance(x, str) else x for x in v).strip()
    if isinstance(v, dict):
        return str(v.get("text") or v.get("name") or "").strip()
    return str(v).strip()


def cell_select(v: Any) -> str:
    if isinstance(v, list):
        return cell_text(v[0]) if v else ""
    return cell_text(v)


def cell_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(cell_text(v)))
    except ValueError:
        return default


def parse_records(resp_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert +record-list matrix output ({fields, data, record_id_list}) to normalized dicts."""
    names = resp_data.get("fields") or []
    out = []
    for rid, row in zip(resp_data.get("record_id_list") or [], resp_data.get("data") or []):
        raw = dict(zip(names, row))
        out.append({
            "record_id": rid,
            "desc": cell_text(raw.get("需求描述")),
            "material": cell_select(raw.get("材料")),
            "process": cell_select(raw.get("工艺")),
            "status": cell_select(raw.get("状态")),
            "change": cell_text(raw.get("修改要求")),
            "log": cell_text(raw.get("迭代日志")),
            "rounds": cell_int(raw.get("迭代轮数")),
            "version": cell_int(raw.get("版本")),
        })
    return out


def decide(rec: Dict[str, Any]) -> Optional[str]:
    """'new' | 'modify' | None per the trigger rules in README.md."""
    if rec["status"] == "待处理" and rec["desc"]:
        return "new"
    if rec["status"] == "已通过" and rec["change"]:
        return "modify"
    return None


def pending_work(records: List[Dict[str, Any]]) -> List[tuple]:
    out = []
    for r in records:
        d = decide(r)
        if d:
            out.append((d, r))
    return out


def now_str(now: Optional[_dt.datetime] = None) -> str:
    return (now or _dt.datetime.now()).strftime("%Y-%m-%d %H:%M")


def format_dfm_report(run: Dict[str, Any]) -> str:
    """Human-readable list: passed groups/rules, warnings, errors, from run.json final_issues."""
    issues = run.get("final_issues") or []
    status = run.get("status")
    lines = []
    by_level: Dict[str, list] = {}
    for i in issues:
        by_level.setdefault(i.get("level", "L3"), []).append(i)
    errs = [i for i in issues if i.get("severity") == "error"]
    warns = [i for i in issues if i.get("severity") != "error"]
    if status == "success":
        head = "结论:通过(%d 条告警)" % len(warns) if warns else "结论:全部通过"
    else:
        head = "结论:未通过(%d 条违规, %d 条告警)" % (len(errs), len(warns))
    lines.append(head)
    for lv in ("L0", "L1", "L2", "L3"):
        lvi = by_level.get(lv, [])
        if lv == "L0" and not lvi:
            continue
        lv_err = [i for i in lvi if i.get("severity") == "error"]
        lines.append("")
        lines.append("【%s】%s" % (LEVEL_TITLE[lv], "未通过" if lv_err else ("通过(有告警)" if lvi else "全部通过")))
        failed = {i.get("rule") for i in lvi}
        for rule, label in LEVEL_RULES.get(lv, []):
            if rule not in failed:
                lines.append("  [通过] %s" % label)
        for i in lvi:
            tag = "违规" if i.get("severity") == "error" else "告警"
            lines.append("  [%s] %s: %s" % (tag, i.get("rule"), i.get("message")))
            if i.get("hint"):
                lines.append("        建议: %s" % i["hint"])
    return "\n".join(lines)


def decide_status(run: Dict[str, Any]) -> str:
    """Map run.json status to Bitable 状态."""
    s = run.get("status")
    if s == "success":
        return "已通过"
    if s == "need_info":
        return "需补充"
    return "需人工"


def missing_text(run: Dict[str, Any]) -> str:
    spec = run.get("spec") or {}
    return ";".join(spec.get("missing") or [])


def build_update_fields(run: Dict[str, Any], log_text: str, rounds: int, version: int,
                        prev_log: str = "", change: str = "", now: Optional[_dt.datetime] = None) -> Dict[str, Any]:
    """Field map for the single write-back update (attachments are uploaded separately)."""
    log = log_text.strip()
    if change:
        header = "—— v%d 修改:%s ——" % (version, change)
        log = (prev_log.strip() + "\n\n" if prev_log.strip() else "") + header + "\n" + log
    f: Dict[str, Any] = {
        "状态": [decide_status(run)],
        "需补充信息": missing_text(run),
        "迭代轮数": rounds,
        "迭代日志": log,
        "DFM 报告": format_dfm_report(run) if run.get("status") != "need_info" else "",
        "版本": version,
        "更新时间": now_str(now),
    }
    if change:
        f["修改要求"] = None
    return f


def error_fields(err: str, prev_log: str = "", restore_status: str = "需人工",
                 now: Optional[_dt.datetime] = None) -> Dict[str, Any]:
    msg = "处理异常:" + err.strip()[:800]
    return {"状态": [restore_status],
            "迭代日志": (prev_log.strip() + "\n\n" if prev_log.strip() else "") + msg,
            "更新时间": now_str(now)}


def attachment_plan(vdir_files: Dict[str, bool], version: int) -> Dict[str, List[str]]:
    """Which local files go to which attachment field. vdir_files: filename -> exists."""
    plan = {"渲染图": ["render.png"], "STEP": ["part.step"], "参数化脚本": ["part.py"],
            "工程图": ["drawing.pdf", "drawing.dxf"]}
    return {k: [f for f in v if vdir_files.get(f)] for k, v in plan.items() if any(vdir_files.get(f) for f in v)}


def parse_need_info(stdout: str) -> Optional[List[str]]:
    """core.cli prints '需补充: a; b' for status=need_info (no run.json is saved). None if absent."""
    for line in stdout.splitlines():
        if line.startswith("需补充:"):
            return [x.strip() for x in line[len("需补充:"):].split(";") if x.strip()]
    return None
