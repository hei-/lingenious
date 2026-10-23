"""DFM-sensitive eval set (ids d1-d12). Texts describe functional geometry only and never mention fillets,
minimum walls or edge distances as manufacturing advice. Ground truth is derived from the DFM-CLEAN references
eval/refs_dfm/<id>.py (minimal fixes over the literal reading, which lives in <id>_naive.py) by
`python -m eval.build_truth_dfm` -> eval/truth_dfm.json."""
from __future__ import annotations

import json
from pathlib import Path

_XYZ = "(长度沿 X、宽度沿 Y、厚度/高度沿 Z)"

_SPECS = [
    ("d1", "medium", f"L 型铝支架{_XYZ}:底板 80×50×5,立板位于 Y 负侧的长边上,沿整条长边,高 35(自底板上表面起算)、厚 4;"
                     "底板上有 2 个直径 5 的通孔,位于 Y 正侧,孔中心距 X 向两端各 10mm、距 Y 正侧边 10mm。"),
    ("d2", "medium", f"U 型铝支架{_XYZ}:底板 70×40×5,沿 70mm 长边的两侧(Y 向两端)各有一块立板,高 25(自底板上表面起算)、厚 3、长度 70;"
                     "底板上有 2 个直径 6 的通孔,位于 X 向 ±20、Y 居中。"),
    ("d3", "easy", f"60×40×6 的铝板{_XYZ},四个角各一个直径 6 的通孔,孔中心距相邻两边各 6mm。"),
    ("d4", "easy", f"120×50×10 的铝板{_XYZ},沿板中线(Y 居中)居中排 3 个直径 10 的通孔,相邻孔中心距 14mm。"),
    ("d5", "hard", f"开口盒体{_XYZ}:外形 100×60×30,壁厚 2.5、底厚 3,顶面(+Z)开口,无孔。"),
    ("d6", "medium", f"L 型薄壁支架{_XYZ}:底板 100×60×8,立板位于 Y 负侧的长边上,沿整条长边,高 30(自底板上表面起算)、厚 1.4,无孔。"),
    ("d7", "hard", f"带筋板的底座{_XYZ}:底板 80×50×6,板面正中沿 X 向立一条通长的筋,长 80(与底板等长)、厚 1.2、高 20(自底板上表面起算),无孔。"),
    ("d8", "easy", f"60×40×25 的铝块{_XYZ},从顶面(+Z)向下钻 4 个直径 6、深 15 的盲孔,孔中心距相邻两边各 6mm。"),
    ("d9", "medium", f"80×50×12 的铝板{_XYZ},顶面居中铣一个 40×20、深 6 的矩形凹槽(40 边沿 X);"
                     "板上有 2 个直径 8 的通孔,Y 居中、X 向距中心 ±34mm。"),
    ("d10", "medium", f"L 型铝支架{_XYZ}:底板 90×50×6,立板位于 Y 负侧的长边上,沿整条长边,高 30(自底板上表面起算)、厚 3;"
                      "立板上 X 居中有一个直径 6 的通孔,孔中心距立板上沿 6mm。"),
    ("d11", "medium", f"双层阶梯块{_XYZ}:底层 80×50×10;上层 40×50×10 叠在底层 X 负端,端面和两侧面平齐,总高 20;"
                      "上层中心(X=-20,Y 居中)一个直径 8 的竖直通孔,底层外露部分有一个直径 8 的竖直通孔,位于 X=+34、Y 居中。"),
    ("d12", "hard", f"管座{_XYZ}:底板 70×70×8,中心立一根同轴圆管,外径 36、高 30(自底板上表面起算,总高 38),"
                    "内孔直径 22 贯穿底板和圆管全长;底板四角各一个直径 8 的通孔,孔中心距相邻两边各 6mm。"),
]

# which existing L3 rule each task is designed to trigger on the naive (literal) reading
DFM_RULES = {
    "d1": ["internal_corner_radius"], "d2": ["internal_corner_radius"], "d3": ["hole_edge_distance"],
    "d4": ["hole_spacing"], "d5": ["internal_corner_radius"], "d6": ["min_wall_thickness", "internal_corner_radius"],
    "d7": ["min_wall_thickness", "internal_corner_radius"], "d8": ["hole_edge_distance"],
    "d9": ["internal_corner_radius", "hole_edge_distance"], "d10": ["hole_edge_distance", "internal_corner_radius"],
    "d11": ["internal_corner_radius", "hole_edge_distance"], "d12": ["internal_corner_radius", "hole_edge_distance"],
}


def _load_truth() -> dict:
    p = Path(__file__).with_name("truth_dfm.json")
    return json.loads(p.read_text()) if p.exists() else {}


_TRUTH = _load_truth()

TASKS = [{"id": i, "level": lv, "text": tx, "truth": _TRUTH[i]} for i, lv, tx in _SPECS if i in _TRUTH]
