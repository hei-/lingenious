# 校验与 DFM 规则

所有判断基于 OCCT 的 B-Rep 查询,不使用 LLM。每条规则是一个独立函数(`core/checks/l1.py` `l2.py` `l3.py`),可单独开关,阈值走配置。

> 阈值说明:数值为通用经验值,待工艺人员复核,未引用任何标准。

## 校验分层

| 层级 | 目的 | 失败处理 |
|---|---|---|
| L0 执行 | 脚本能运行并产出 `result` | 回传 traceback 摘要 |
| L1 几何有效 | 模型是合法实体 | error |
| L2 需求符合 | 与 `PartSpec.assertions` 一致(LLM 推导,可申诉,见 [ADR 0003](adr/0003-disputable-l2-assertions.md)) | error |
| L3 DFM | 可制造性经验规则 | error 或 warning |

## L1 几何有效性

| 规则 id | 检查 | 方法 |
|---|---|---|
| `valid_solid` | 形状有效 | `shape.isValid()` |
| `single_solid` | 恰好一个实体 | `len(shape.Solids()) == 1` |
| `positive_volume` | 体积大于 0 | `shape.Volume()` |

## L2 需求符合度

| 规则 id | 检查 | 方法 |
|---|---|---|
| `bbox_match` | 包围盒与规格一致(容差 `tol`) | `BoundingBox()` |
| `hole_count` | 孔数一致 | 统计圆柱内表面,按轴线与半径聚合 |
| `hole_diameter` | 孔径一致 | 圆柱面半径 |
| `hole_position` | 孔位与规格一致(容差) | 轴线与参考面的距离 |
| `volume_range` | 体积落在范围内(可选) | `Volume()` |
| `hole_breakout` | 孔/槽切穿板边形成缺口(始终开启,不依赖断言) | `features.find_breakouts` |

孔识别:遍历面,筛 `GeomType == "CYLINDER"`,法向朝向材料内部(凹)且圆周覆盖大于 180° 的面视为孔壁;同轴同径的合并计一个孔。通孔与盲孔由是否两端开口判断。

## L3 DFM 规则(已实现)

> 以下阈值均为**通用经验值,待工艺人员复核**,未引用任何标准,不代表任何车间的实际能力。复核清单见 [dfm-review-checklist.md](dfm-review-checklist.md)。

| 规则 id | 检查 | 默认阈值 | 配置键 | 级别 |
|---|---|---|---|---|
| `min_wall_thickness` | 相对近平行平面对的壁厚 | < 1.5mm error,< 2.0mm warning | `min_wall_error` `min_wall_warn` | error/warning |
| `hole_edge_distance` | 孔壁到最近外边缘 | ≥ 1.5×孔径(壁厚上限 6mm) | `hole_edge_factor` `hole_edge_wall_cap` / `rules.hole_edge_distance.factor` | error |
| `internal_corner_radius` | 内凹角圆角 | 尖角 error;R<0.5 error;R<3 warning | `min_internal_radius` `recommended_internal_radius` / `rules.internal_corner_radius.{min_radius,recommended}` | error/warning |
| `hole_spacing` | 孔间壁 | ≥ 1×较小孔径 | `hole_spacing_factor` | error |
| `hole_depth_ratio` | 盲孔深/径;通孔取穿过的板厚/径 | 盲孔 >6 warning,>10 error;通孔 >6 仅 warning | `hole_depth_warn` `hole_depth_error` `hole_depth_through_warn` / `rules.hole_depth_ratio.{warn,error,through_warn}` | error/warning |
| `deep_pocket` | 封闭腔(底面四周均为内凹壁)深/最小腔宽 | > 4 warning | `deep_pocket_warn` / `rules.deep_pocket.warn` | warning |
| `thin_web_height` | 薄筋/薄壁高/厚 | > 8 warning,仅厚度 ≤ 5mm | `thin_web_warn` `thin_web_max_thickness` / `rules.thin_web_height.{warn,max_thickness}` | warning |

方法要点(均为确定性 B-Rep 查询,任何无法识别的几何返回空列表,不抛异常):

- `hole_depth_ratio`:复用 `find_holes`;盲孔用孔深(圆柱段)/孔径,不含锥底。台阶孔每段按各自孔径、段长计算。
- `deep_pocket`:平面底面的外环每条边都连接内凹壁(含底部圆角)才视为封闭腔;深度取各壁沿底面法向的最低高度;腔宽取最小卡尺宽与相对平行壁间距的较小值。圆形盲孔归 `hole_depth_ratio`,不重复报。
- `thin_web_height`:顶面的两侧邻面为反向平行平面且为凸边,间距即厚度;高度取侧面到根部内凹边(含圆角起点)的距离,两侧取较小者。无法区分"薄筋"与"悬臂薄法兰",二者都会提示。
- 每条规则可用 `dfm.rules.<id>.enabled: false` 关闭。

## 阈值配置

优先级(低到高):内置默认 < `dfm.*` < `dfm.rules.<id>.*` < `dfm.material_overrides.<材料>` < `dfm.process_overrides.<工艺>`。覆盖表中可写任何 `DEFAULTS` 键;`min_wall_thickness` 同时抬高壁厚 error/warn。

```yaml
dfm:
  material_overrides:
    "6061": {min_wall_thickness: 1.5}
    "steel": {min_wall_thickness: 2.0, hole_depth_warn: 5.0, hole_depth_error: 8.0, deep_pocket_warn: 3.0, thin_web_warn: 6.0}
  rules:
    hole_edge_distance: {factor: 1.5, enabled: true}
    internal_corner_radius: {min_radius: 0.5, recommended: 3.0}
    hole_depth_ratio: {warn: 6, error: 10}
```

steel 一行的数值同样是占位经验值,待复核。

## 未实现

`standard_hole_size`(标准钻头孔径表)与 L1 的 `no_tiny_features`(无小于 0.05mm 的边或面)仍为计划项。

## 规则接口

规则用 `core/checks/base.py` 的 `@rule(id, level)` 装饰器声明,函数签名为 `fn(shape, spec, c) -> list[Issue]`,
其中 `c` 是按上文优先级合并后的阈值字典(`dfm_cfg`)。规则需登记到 `core/checks/__init__.py` 的
`L1_RULES` / `L2_RULES` / `L3_RULES`;`run_checks` 按 L1→L2→L3 顺序执行,L1 有 error 时跳过后续层级。
完整步骤见 [CONTRIBUTING.md](../CONTRIBUTING.md#adding-a-dfm-rule)。

每条规则必须带:单元测试(正例与反例各一)、数值化的 `message`、可操作的 `hint`。

## 实现注意

- 壁厚计算在复杂几何上很难严格,MVP 仅对近平行平面对做检查,README 说明是近似。
- 孔识别放在共享工具 `checks/features.py`,L2 和 L3 复用。
- 所有长度单位 mm。
