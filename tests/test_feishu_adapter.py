"""Pure-function tests for the Feishu Bitable adapter (no network / docker)."""
import datetime

from adapters.feishu_bitable import logic

RUN_OK = {"status": "success", "spec": {"missing": []}, "rounds": [{}, {}], "final_issues": [
    {"rule": "min_wall_thickness", "level": "L3", "severity": "warning", "message": "壁厚偏薄", "hint": "加厚"}]}
RUN_FAIL = {"status": "failed", "rounds": [{}], "final_issues": [
    {"rule": "bbox_match", "level": "L2", "severity": "error", "message": "X 不符"}]}


def test_parse_records_and_cells():
    data = {"fields": ["需求描述", "材料", "状态", "修改要求", "迭代轮数", "版本"],
            "record_id_list": ["r1"],
            "data": [["L 支架", ["6061"], ["待处理"], None, 2.0, 1]]}
    r = logic.parse_records(data)[0]
    assert r["record_id"] == "r1" and r["material"] == "6061" and r["status"] == "待处理"
    assert r["change"] == "" and r["rounds"] == 2 and r["version"] == 1


def test_cell_text_rich():
    assert logic.cell_text([{"text": "a"}, {"text": "b"}]) == "ab"
    assert logic.cell_text(None) == ""


def _rec(status, desc="x", change=""):
    return {"status": status, "desc": desc, "change": change}


def test_decide():
    assert logic.decide(_rec("待处理")) == "new"
    assert logic.decide(_rec("待处理", desc="")) is None
    assert logic.decide(_rec("已通过", change="改4mm")) == "modify"
    assert logic.decide(_rec("已通过")) is None
    assert logic.decide(_rec("生成中", change="x")) is None
    assert logic.decide(_rec("需人工", change="x")) is None


def test_pending_work():
    recs = [dict(_rec("待处理"), record_id="a"), dict(_rec("已通过"), record_id="b"),
            dict(_rec("已通过", change="c"), record_id="c")]
    assert [(k, r["record_id"]) for k, r in logic.pending_work(recs)] == [("new", "a"), ("modify", "c")]


def test_report_pass_lists_passed_groups_and_warnings():
    t = logic.format_dfm_report(RUN_OK)
    assert "通过(1 条告警)" in t
    assert "[通过] 实体有效" in t and "[通过] 包围盒" in t
    assert "[告警] min_wall_thickness" in t and "建议: 加厚" in t
    assert "[通过] 孔边距" in t and "[通过] 最小壁厚" not in t


def test_report_fail():
    t = logic.format_dfm_report(RUN_FAIL)
    assert "未通过" in t and "[违规] bbox_match" in t
    assert "【L2 需求符合度】未通过" in t


def test_status_mapping():
    assert logic.decide_status(RUN_OK) == "已通过"
    assert logic.decide_status({"status": "need_info"}) == "需补充"
    assert logic.decide_status(RUN_FAIL) == "需人工"


def test_build_update_fields_new():
    now = datetime.datetime(2026, 1, 2, 3, 4)
    f = logic.build_update_fields(RUN_OK, "第1轮:通过", 2, 1, now=now)
    assert f["状态"] == ["已通过"] and f["迭代轮数"] == 2 and f["版本"] == 1
    assert f["更新时间"] == "2026-01-02 03:04" and "修改要求" not in f


def test_build_update_fields_modify_appends_and_clears():
    f = logic.build_update_fields(RUN_OK, "第3轮:通过", 3, 2, prev_log="第1轮:通过", change="立板改4mm")
    assert f["修改要求"] is None
    assert f["迭代日志"].startswith("第1轮:通过") and "立板改4mm" in f["迭代日志"] and f["迭代日志"].endswith("第3轮:通过")


def test_need_info():
    run = {"status": "need_info", "spec": {"missing": ["孔径", "厚度"]}}
    f = logic.build_update_fields(run, "", 0, 1)
    assert f["状态"] == ["需补充"] and f["需补充信息"] == "孔径;厚度" and f["DFM 报告"] == ""
    assert logic.parse_need_info("xx\n需补充: 孔径; 厚度\n") == ["孔径", "厚度"]
    assert logic.parse_need_info("nothing") is None


def test_error_fields():
    f = logic.error_fields("boom", prev_log="old")
    assert f["状态"] == ["需人工"] and f["迭代日志"].startswith("old") and "boom" in f["迭代日志"]


def test_attachment_plan():
    p = logic.attachment_plan({"render.png": True, "part.step": True, "part.py": True, "drawing.pdf": True}, 1)
    assert p == {"渲染图": ["render.png"], "STEP": ["part.step"], "参数化脚本": ["part.py"], "工程图": ["drawing.pdf"]}
    assert "工程图" not in logic.attachment_plan({"render.png": True}, 1)
