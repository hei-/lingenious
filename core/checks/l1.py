"""L1: geometric validity."""
from __future__ import annotations

from core.models import Issue
from .base import rule


@rule("valid_solid", "L1")
def valid_solid(shape, spec, c):
    if shape.isValid():
        return []
    return [Issue(rule="valid_solid", level="L1", message="形状未通过 OCCT 有效性检查(isValid=False)",
                  hint="检查是否存在自相交、零厚度或布尔运算失败;简化最后一步的布尔/圆角/抽壳操作,或略微错开重合的面")]


@rule("single_solid", "L1")
def single_solid(shape, spec, c):
    n = len(shape.Solids())
    if n == 1:
        return []
    return [Issue(rule="single_solid", level="L1", measured=float(n), required=1.0,
                  message=f"模型包含 {n} 个实体,要求恰好 1 个",
                  hint="多个实体说明零件未连成一体:让各部分有重叠体积后再 union;若为 0 个,检查是否误把线框/面作为结果" if n else
                  "结果中没有实体(0 个):确认 result 是实体而非线框/面,检查 extrude/cut 是否把实体全部切掉")]


@rule("positive_volume", "L1")
def positive_volume(shape, spec, c):
    v = shape.Volume()
    if v > 1e-6:
        return []
    return [Issue(rule="positive_volume", level="L1", measured=float(v), required=0.0,
                  message=f"体积为 {v:.3f} mm³,要求大于 0",
                  hint="体积非正通常是面法向反向或截面未闭合;确认草图封闭并沿正确方向拉伸")]
