import re

from core.agent import prompts
from core.checks import run_checks
from core.models import Assertions, HolePos, PartSpec
from core.sandbox import execute


def example_code():
    return re.search(r"```python\n(.*?)```", prompts.SYSTEM, re.S).group(1)


def test_example_executes_and_passes_checks(tmp_path):
    res = execute(example_code(), workdir=tmp_path, timeout_s=60)
    assert res.ok, res.error
    corners = [HolePos(diameter=6.6, x=sx * 38, y=sy * 18) for sx in (-1, 1) for sy in (-1, 1)]
    sp = PartSpec(assertions=Assertions(hole_count=4, hole_diameters=[6.6] * 4, hole_positions=corners))
    issues = run_checks(res.shape, sp, {}, levels=("L1", "L2", "L3"))
    assert [i for i in issues if i.severity == "error"] == []


def test_example_does_not_use_face_workplane_idiom():
    assert "centerOption" not in example_code()
    assert "faces(" not in example_code().split("# feature: h1")[1]


def test_convention_stated_in_both_prompts():
    for text in (prompts.SYSTEM, prompts.SPEC_SYSTEM):
        assert "Z" in text and "中心" in text and "底面" in text
    assert "hole_positions" in prompts.SPEC_SYSTEM
    assert "不要编造" in prompts.SPEC_SYSTEM
    assert "workplane" in prompts.SYSTEM and "偏移" in prompts.SYSTEM
    assert "绝对坐标" in prompts.generate_user("{}", "x")


def test_fix_user_includes_constraints_only_when_given():
    from core.agent import _constraints_text
    from core.models import Assertions, BBox, PartSpec
    spec = PartSpec(assertions=Assertions(bbox=BBox(x=100, y=60, z=6), hole_count=2, hole_diameters=[6, 6]))
    c = _constraints_text(spec)
    assert "100×60×6" in c and "孔数 2" in c and "Ø6" in c
    from core.agent import prompts
    assert "必须保持" in prompts.fix_user("code", "- [r] m", "req", c)
    assert "必须保持" not in prompts.fix_user("code", "- [r] m", "req")
