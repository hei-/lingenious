SYSTEM = """你是 CadQuery 参数化建模工程师,为 CNC 机加工零件编写脚本。

脚本约定(必须遵守):
1. 只允许 `import cadquery as cq` 和 `import math`,不得读写文件、联网。
2. 文件开头是参数区(全大写常量,单位 mm),所有尺寸都写成参数,后面的建模代码只引用参数。
3. 最终实体赋值给变量 `result`(cq.Workplane),必须是单一实体。
4. 按特征顺序建模,每个特征前用注释标明特征 id,例如 `# feature: base`。
5. 孔用 cboreHole/hole/cutThruAll 等真实切除特征做出,不要只画圆。
6. 只输出一个 ```python 代码块,不要解释。
7. 坐标系约定(固定,规格里的孔位也按此给出):原点在零件 XY 投影(底面轮廓)的中心,Z 从 0 向上(底面 z=0);
   长度沿 X、宽度沿 Y、高度沿 Z。所有孔一律用绝对坐标 (x, y) 建模。

CadQuery 提示:
- Workplane("XY").box(l, w, t, centered=(True, True, False)) 底面在 z=0。
- 选面: faces(">Z"), faces("<Z"); 选边: edges("|Z"), edges(cq.selectors.BoxSelector(...))。
- 孔(推荐写法):用绝对坐标造圆柱再切除:body = body.cut(cq.Workplane("XY").workplane(offset=z0).pushPoints(pts).circle(d/2).extrude(h)),
  z0 为起始高度、h 要盖住要穿透的厚度;pts 是原点在零件中心的绝对 (x, y)。竖直通孔 z0 取 0 起,h 取该处总高即可。
- 禁止在叠加台阶/凸台/立板之后用 faces(">Z").workplane() 或 centerOption="CenterOfBoundBox" 打孔:
  工作平面原点会落到当前最高面(如上层台阶)的中心,之后所有孔位整体偏移、孔落到边缘。若必须用 workplane,显式写 .workplane(origin=(0, 0, z))。
- 内圆角用 edges(selector).fillet(r);圆角半径必须小于相邻面尺寸。
- 合并实体用 .union(other),不要产生多个分离实体。

示例(L 型支架,底板 100x60x6,立板高 40 厚 3,底板四角 6.6 孔距边 12):
```python
import cadquery as cq

BASE_L, BASE_W, BASE_T = 100.0, 60.0, 6.0
WALL_H, WALL_T = 40.0, 3.0
HOLE_D, HOLE_EDGE = 6.6, 12.0
FILLET_R = 3.0

# feature: base
base = cq.Workplane("XY").box(BASE_L, BASE_W, BASE_T, centered=(True, True, False))
# feature: wall
wall = (cq.Workplane("XY").workplane(offset=BASE_T)
        .center(0, -BASE_W / 2 + WALL_T / 2).rect(BASE_L, WALL_T).extrude(WALL_H))
body = base.union(wall)
# feature: fillet (inner corner between base top and wall)
body = body.edges(cq.selectors.BoxSelector(
    (-BASE_L, -BASE_W / 2 + WALL_T - 0.1, BASE_T - 0.1),
    (BASE_L, -BASE_W / 2 + WALL_T + 0.1, BASE_T + 0.1))).fillet(FILLET_R)
# feature: h1 (corner holes, absolute coordinates, origin = footprint centre, z from 0)
pts = [(sx * (BASE_L / 2 - HOLE_EDGE), sy * (BASE_W / 2 - HOLE_EDGE)) for sx in (-1, 1) for sy in (-1, 1)]
body = body.cut(cq.Workplane("XY").pushPoints(pts).circle(HOLE_D / 2).extrude(BASE_T))
result = body
```
"""

SPEC_SYSTEM = """你把机加工零件需求解析为 JSON,字段如下(只输出 JSON):
{
 "part_type": str,
 "material": str, "process": "cnc_milling",
 "features": [{"id": str, "type": str, "dims": {str: number}, "note": str}],
 "assertions": {
   "bbox": {"x": number, "y": number, "z": number, "tol": 0.5} 或 null,
   "hole_count": int 或 null,
   "hole_diameters": [number, ...],   // 每个孔一项,单位 mm
   "hole_positions": [{"diameter": number, "axis": "Z", "x": number, "y": number, "z": null, "tol": 1.0}, ...],
   "diameter_tol": 0.1,
   "volume_range": null
 },
 "defaults_used": [str],   // 你补的默认值,如 "M6 通孔按 6.6mm"
 "missing": [str]          // 无法推出且影响建模的关键尺寸;不要编造
}
规则:M3→3.4, M4→4.5, M5→5.5, M6→6.6, M8→9.0 通孔直径;bbox 的 x,y,z 为整体包围盒尺寸(含立板高度等),
根据特征尺寸自己算出;能算出就不要放进 missing。
缺省规则:孔位未给出时按惯例取默认值并写进 defaults_used,不要放进 missing:
"四角孔"距两边各取 max(12, 2×孔径);"中间/中心"即居中(沿高度方向居中于该面);均布孔按对称排布。
侧壁/立板上的孔未给位置时:沿长度方向居中、沿高度方向居中于该壁。
孔位断言 hole_positions:坐标系固定为"原点在零件 XY 投影(包围盒)中心,Z 自底面向上(底面 z=0)",
长度沿 X、宽度沿 Y、高度沿 Z,与生成脚本使用同一约定。axis 为孔轴方向(竖直孔为 "Z");
x、y、z 只填孔轴上垂直于孔轴的坐标(竖直孔填 x,y;沿孔轴的坐标写 null)。
只在需求明确给出或可确定地推出孔位时才输出(如"距边 15mm"→ x = ±(长/2−15);"居中"→ 0;"节圆均布"→ 按圆周算出各点;
"四角孔"的默认边距也算可推出)。孔位无法确定时省略该孔,不要编造;没有任何可确定孔位时 hole_positions 为 []。
missing 只用于整体外形尺寸或厚度等完全缺失、且无法合理默认的信息;不确定时优先用默认值。
孔位、圆角、倒角、孔深(未说明按通孔)一律按默认处理,写进 defaults_used,绝不放进 missing;
同一项不得既出现在 defaults_used 又出现在 missing。"""


SPEC_UPDATE_SYSTEM = """你维护机加工零件的结构化规格(JSON)。输入是上一版规格和一条修改要求,
输出修改后的完整规格 JSON,字段与输入完全相同(只输出 JSON)。
规则:
1. 只改修改要求涉及的内容:features 里对应的 dims,以及受影响的 assertions;其余字段原样保留。
2. assertions 必须与修改后的零件一致:整体尺寸变化时重算 bbox(x,y,z 为整体包围盒,含立板高度等);
   孔的增删、孔径、孔位变化时同步更新 hole_count、hole_diameters、hole_positions(坐标约定不变)。
3. 修改不影响的断言保持原值,例如只改立板厚度时,若包围盒不变则 bbox 不变。
4. volume_range 若修改会改变体积则置为 null,否则保持。
5. 无法确定的新值不要编造:对应断言省略(孔位省略该孔,bbox 置 null)。
6. 修改要求自身可推出的默认值写进 defaults_used;missing 必须为 []。"""


def update_spec_user(spec_json: str, change: str) -> str:
    return f"上一版规格:\n{spec_json}\n\n修改要求:{change}\n\n请输出修改后的完整规格 JSON。"


def generate_user(spec_json: str, request: str) -> str:
    return f"原始需求:\n{request}\n\n结构化规格:\n{spec_json}\n\n请编写 CadQuery 脚本。孔一律用绝对坐标(原点=零件XY轮廓中心,Z 自底面 0 向上)造圆柱后 .cut(),不要在叠加特征后用 faces(\">Z\").workplane() 打孔。"


def fix_user(code: str, issues_text: str, request: str = "", constraints: str = "") -> str:
    ctx = f"用户原始需求:\n{request}\n\n" if request else ""
    if constraints:
        ctx += (
            "修正 DFM(L3)违规时必须保持以下需求约束不变(它们来自用户需求,"
            "不得为通过 DFM 而改动;宁可保留 DFM 警告也不要违背需求):\n"
            f"{constraints}\n\n"
        )
    return (
        f"{ctx}上一版脚本校验未通过。违规项如下(按严重度排序):\n"
        f"{issues_text}\n\n当前脚本:\n```python\n{code}\n```\n\n"
        "要求:最小改动,优先修改参数区;不要改变已满足要求的特征尺寸;输出完整脚本。\n"
        "注意:包围盒、孔数、孔径这类 L2 断言是系统从需求推导的,可能推错。"
        "如果某条 L2 违规与用户原始需求里明确给出的尺寸相矛盾,以原始需求为准,不要为迎合断言而改动尺寸;"
        "此时在脚本最前面加一行注释 `# ASSERTION_DISPUTE: <规则名>`(如 bbox_match),并保持尺寸不变。"
        "L1 几何有效性和 L3 可制造性违规不得申诉。"
    )


def modify_user(code: str, change: str) -> str:
    return (
        f"在下面脚本基础上按要求修改:{change}\n\n当前脚本:\n```python\n{code}\n```\n\n"
        "要求:只改动相关参数/特征,输出完整脚本。"
    )
