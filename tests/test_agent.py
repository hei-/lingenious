from core.agent import _apply_disputes
from core.models import Issue


def _i(rule, level="L2"):
    return Issue(rule=rule, level=level, message="m")


def test_dispute_demotes_only_l2_assertions():
    code = "# ASSERTION_DISPUTE: bbox_match\n# ASSERTION_DISPUTE: internal_corner_radius\n"
    out = _apply_disputes(code, [_i("bbox_match"), _i("internal_corner_radius", "L3"), _i("hole_count")])
    sev = {i.rule: i.severity for i in out}
    assert sev == {"bbox_match": "warning", "internal_corner_radius": "error", "hole_count": "error"}
    assert out[0].message.startswith("[脚本申诉")


def test_no_dispute_keeps_errors():
    assert _apply_disputes("x = 1", [_i("bbox_match")])[0].severity == "error"


class _SpecLLM:
    def __init__(self, out):
        self.out, self.seen = out, []

    def structured(self, messages, model, retries=1):
        self.seen.append(messages[-1]["content"])
        if isinstance(self.out, Exception):
            raise self.out
        return self.out


def test_update_spec_carries_updated_assertions():
    from core.agent import update_spec
    from core.models import Assertions, BBox, PartSpec
    prev = PartSpec(assertions=Assertions(bbox=BBox(x=100, y=60, z=46), hole_count=5))
    new = PartSpec(assertions=Assertions(bbox=BBox(x=100, y=60, z=50), hole_count=5), missing=["x"])
    llm = _SpecLLM(new)
    out = update_spec(llm, prev, "立板高度改成 44mm")
    assert out.assertions.bbox.z == 50 and out.missing == []
    assert "立板高度改成 44mm" in llm.seen[0] and '"z": 46' in llm.seen[0]


def test_update_spec_falls_back_to_no_assertions():
    from core.agent import update_spec
    from core.models import Assertions, BBox, PartSpec
    prev = PartSpec(assertions=Assertions(bbox=BBox(x=1, y=2, z=3)), defaults_used=["d"])
    out = update_spec(_SpecLLM(ValueError("structured output failed")), prev, "改4mm")
    assert out.assertions == Assertions()
    assert out.defaults_used[0] == "d" and "不校验尺寸断言" in out.defaults_used[1]
    assert prev.assertions.bbox is not None  # previous spec untouched


def test_defaultable_details_are_not_missing():
    from core.agent import _demote_defaultable
    from core.models import PartSpec
    s = _demote_defaultable(PartSpec(missing=["两侧壁孔沿长度方向的位置", "板厚"], defaults_used=["孔居中"]))
    assert s.missing == ["板厚"]
    assert s.defaults_used == ["孔居中", "未给出:两侧壁孔沿长度方向的位置,按默认处理"]
    assert _demote_defaultable(PartSpec(missing=[])).missing == []
