# 配置与环境变量

两层配置:`config.yaml`(算法/阈值,随镜像发布)和环境变量(部署相关、密钥)。

## config.yaml

| 键 | 默认 | 说明 |
|---|---|---|
| `llm.base_url` | `https://api.deepseek.com` | 任何 OpenAI 兼容接口 |
| `llm.model` | `deepseek-chat` | 模型名 |
| `llm.api_key_env` | `DEEPSEEK_API_KEY` | **存放密钥的环境变量名**(不是密钥本身);换供应商时改这里并设置对应变量 |
| `llm.temperature` | `0.2` | 采样温度 |
| `agent.max_rounds` | `4` | 生成 + 修复的最大轮数 |
| `sandbox.timeout_s` | `60` | 单次脚本执行的墙钟超时(秒) |
| `sandbox.mem_mb` | `4096` | 子进程地址空间上限(RLIMIT_AS,MB);省略时 4096 |
| `dfm.*` | 见文件 | 阈值:`hole_edge_factor` `hole_edge_wall_cap` `min_wall_error/warn` `min_internal_radius` `recommended_internal_radius` `hole_depth_warn/error/through_warn` `deep_pocket_warn` `thin_web_warn` `thin_web_max_thickness` |
| `dfm.material_overrides.<材料>` | 6061, steel | 按材料覆盖任意上述键;`min_wall_thickness` 同时抬高壁厚 error/warn |
| `dfm.process_overrides.<工艺>` | 空 | 按工艺覆盖,优先级最高 |
| `dfm.rules.<规则id>.enabled/warn/error/...` | 空 | 单条规则开关与阈值,优先级低于 material/process 覆盖 |
| `web.max_workers` | 2 | Web 并发 worker 数(可被 `LINGENIOUS_MAX_WORKERS` 覆盖) |

优先级(低到高):内置默认 < `dfm.*` < `dfm.rules.*` < `material_overrides` < `process_overrides`。规则详情见 [dfm-rules.md](dfm-rules.md)。

## 用环境变量覆盖 config.yaml 的任意键

形如 `LINGENIOUS__<段>__<段>…=值`(**双下划线**分隔层级,不区分大小写),值按 YAML 解析(`3`→整数,`0.5`→浮点,`true`→布尔,`[1, 2]`→列表,其余为字符串)。对 CLI(`core.cli`、`core.modify_cli`)、评测(`eval.runner`)和 Web 服务生效(实现:`core/config.py`)。

```bash
LINGENIOUS__AGENT__MAX_ROUNDS=3
LINGENIOUS__LLM__MODEL=deepseek-reasoner
LINGENIOUS__SANDBOX__TIMEOUT_S=120
LINGENIOUS__DFM__MIN_WALL_WARN=2.5
LINGENIOUS__DFM__MATERIAL_OVERRIDES__6061__MIN_WALL_THICKNESS=1.0
```

说明:键名转小写写入(已存在的键按不区分大小写匹配);中间层不存在会自动创建;类型不做校验,错误值会在使用处报错。`LINGENIOUS_DATA` 这类单下划线变量不是覆盖项。覆盖在进程启动时读取一次,改后需重启。

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY`(或 `llm.api_key_env` 指定的名字) | 无 | LLM 密钥。未设置时 Web 只能看示例(`llm_configured=false`,创建任务返回 503) |
| `LINGENIOUS_DATA` | `./data`(镜像内 `/app/data`) | Web 数据目录(任务、产物、示例 glb 缓存) |
| `LINGENIOUS_MAX_WORKERS` | 2(compose 同) | 并发 worker 数;非法值回退到 `web.max_workers` |
| `LINGENIOUS_CONFIG` | 仓库 `config.yaml` | Web 使用的配置文件路径 |
| `LINGENIOUS_UI_DIST` | `web/ui/dist` | 前端构建产物目录;目录不存在则只提供 API |
| `LINGENIOUS_ACCESS_TOKEN` | 空(不鉴权) | 设置后除 `/api/health` 外的所有 `/api` 需要口令,见 [web-app.md](web-app.md) 与 [SECURITY.md](../SECURITY.md) |
| `LINGENIOUS__…` | 无 | 覆盖 config.yaml,见上 |
| `APT_MIRROR` / `PIP_INDEX_URL` | 官方源 | 构建镜像用的软件源;设置为同名环境变量时,Makefile 与 `scripts/run.sh` 作为 build-arg 传入 |

容器内另有固定设置:`PYTHONPATH=/app` `MPLBACKEND=Agg` `MPLCONFIGDIR=/tmp/mpl` `XDG_CACHE_HOME=/tmp/.cache`(只读根文件系统下需要 tmpfs `/tmp`)。

## 镜像与多架构构建

`web/Dockerfile` 的运行时镜像只复制 `core/` `web/server/` `web/ui/dist` `examples/` `config.yaml` `pyproject.toml`(不含 docs、tests、eval、adapters、web/landing、node)。构建需要 BuildKit(Docker ≥ 23 默认开启,旧版设 `DOCKER_BUILDKIT=1`),pip/npm/apt 使用缓存挂载,依赖层只随 `requirements.lock` 变化。

`make web-multiarch`(buildx,默认 `PLATFORMS=linux/amd64,linux/arm64`,不推送;`PUSH=1 TAG=<repo:tag>` 推送)。**arm64 现状**:实测锁文件中除 `cadquery-ocp==7.7.2` 外所有依赖都有 aarch64 manylinux 轮子;`cadquery-ocp 7.7.2`(cadquery 2.5.2 固定)在 Linux 只发布 x86_64 轮子(`manylinux_2_35_x86_64`),aarch64 轮子从 8.x 才有。所以 arm64 构建目前会在 `pip install` 处失败,Release 工作流默认只构建 amd64(QEMU + buildx 已配置,待 cadquery 升级后设置仓库变量 `WEB_PLATFORMS=linux/amd64,linux/arm64`)。
