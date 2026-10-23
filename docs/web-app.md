# Web 应用与介绍页

自托管 Web 应用(不依赖飞书)+ 静态介绍页。目录:

```
web/server/    FastAPI 后端,复用 core/
web/ui/        Vite + React + three.js 前端,构建到 web/ui/dist,由后端托管
web/landing/   静态介绍页(GitHub Pages),内置真实运行回放数据,无需后端
docker-compose.yml   一条命令启动(多阶段构建前端)
```

## 数据目录

`data/runs/<run_id>/meta.json`(request、material、config、created_at、status、versions:[1,2..])
`data/runs/<run_id>/v<n>/`:`part.py part.step part.glb render.png thumb.png drawing.{pdf,dxf,png} run.json log.txt`
(run.json 由 `core.agent.save` 写出;每轮含 `code`、`issues`、`seconds`。)

## API(JSON,前缀 /api)

| 方法 路径 | 说明 |
|---|---|
| `GET /api/health` | `{ok, llm_configured}` |
| `POST /api/runs` `{request, material?, process?, config?="C"}` | 创建并后台执行,返回 `{id}` |
| `POST /api/runs/{id}/modify` `{change}` | 基于最新版本生成新版本,返回 `{id, version}` |
| `GET /api/runs/{id}/events?version=n` | SSE。事件见下 |
| `GET /api/runs` | 列表(新到旧):`[{id, title, status, created_at, versions}]` |
| `GET /api/runs/{id}` | meta + 每版本的 run.json 内容 + 文件清单 |
| `GET /api/runs/{id}/v{n}/{file}` | 下载/预览产物 |
| `GET /api/examples` | 只读示例运行(来自仓库内置样例,无需 API key),结构同 `GET /api/runs/{id}`,id 前缀 `example-` |

SSE 事件(`event:` 名 + JSON `data:`):
`parsing` `spec`(PartSpec) `generating` `round`({n,seconds,exec_ok,issues[]}) `fixing`({n}) `artifact`({name}) `done`({status, version, usage}) `error`({message})。
断线重连时先回放该版本已发生的事件再续推。

Issue 字段:`rule level severity target message measured required hint`;level ∈ L0/L1/L2/L3,severity ∈ error/warning。

## 规则

- 密钥只读环境变量(`.env` 经 `--env-file`/compose 传入),任何接口不得回显。
- 执行走现有沙箱(`core.sandbox`);并发 worker 数、输入长度有上限。
- 没有 API key 时 `llm_configured=false`,前端禁用提交并引导查看示例。
- 3D 预览用 `part.glb`(由 STEP 经 CadQuery 导出 GLTF/GLB,单位 mm)。

## 实现细节(后端已落地,补充契约)

- `GET /api/runs/{id}` 返回 meta 全部字段,加 `runs`(`{"1": run.json 内容|null}`)和 `files`(`{"1": ["part.py",...]}`);meta 另含 `version_status`(`{"1":"success"}`)、`changes`(`{"2":"修改指令"}`)。`status` ∈ queued/running/success/need_info/failed/error。示例另有 `example:true`。
- 额外 SSE 事件 `artifact_failed`({name,message}):渲染/GLB/工程图失败时发出,不影响 `done`。`artifact` 事件的 `name` 为文件名(drawing 产出 pdf/dxf/png 各一条)。
- 事件持久化在 `v<n>/events.jsonl`;`/events` 不带 version 取最新版本;示例只回放一个 `done`。
- `part.glb`:单位 mm,根节点带 -90°绕 X 旋转(CAD Z 向上 → glTF Y 向上),由 `web/server/meshing.py` 镶嵌写出。
- 错误码:无 key 503;示例 modify 403;同一 run 有版本在跑 409;无成功版本可改 409;队列满 429;输入超长 422。
- 环境变量:`LINGENIOUS_DATA`(默认 `./data`)、`LINGENIOUS_MAX_WORKERS`(默认 2)、`LINGENIOUS_CONFIG`、`LINGENIOUS_UI_DIST`、`LINGENIOUS_ACCESS_TOKEN`;全表与 `LINGENIOUS__*` 覆盖见 [configuration.md](configuration.md)。
- **访问口令(可选)**:设置 `LINGENIOUS_ACCESS_TOKEN` 后,除 `/api/health`、`/api/auth/login`、`/api/auth/logout` 外的所有 `/api/*`(含示例、文件下载、SSE)需要口令,否则 401 `{"detail":"unauthorized"}`。两种方式:`Authorization: Bearer <口令>`(常量时间比较),或 `POST /api/auth/login {"token": "..."}` 种下 `HttpOnly; SameSite=Strict` 的会话 Cookie(值是口令的 HMAC 派生值,不是口令本身;HTTPS 下加 `Secure`),使 `<img>`/`<a>`/EventSource 无需自定义头;`POST /api/auth/logout` 清除。登录失败按客户端 IP 在内存中退避(连续 5 次后指数退避,上限 300 s,期间返回 429 + `Retry-After`;反向代理后看到的是代理 IP,需在代理处限速)。`/api/health` 增加 `auth_required` 与 `authenticated`。静态前端保持公开;前端在 `auth_required && !authenticated` 或任何 401 时显示登录页,顶栏有退出按钮。口令不写日志、不回显。
- 运行:`uvicorn web.server.app:app`;容器:`docker compose up --build`(仅绑定 127.0.0.1:8000,命名卷 `data` 挂到 `/app/data`;加固与无认证说明见 [SECURITY.md](../SECURITY.md))。
- 示例由 `scripts/make_examples.py` 生成(需 `DEEPSEEK_API_KEY` 与 cadquery,即在镜像内运行):每个需求经后端同一 job 代码路径真实运行 3 次,原样发布其中一次到 `examples/<name>/`(bracket 含 v1 + 修改 v2,plate、u_bracket 各 v1);`meta.json` 的 `selection`(`{runs, picked, reason, summary}`)说明挑选依据(优先全部成功且有真实修复轮,不编辑产出),`GET /api/examples` 原样返回 `selection` 与 `source`;3 次运行的 run.json 摘要留在 `out/examples_runs/`(不入库)。`synthetic`(`{"2": "说明"}`)与轮次 `reconstructed: true` 字段仍受支持(向后兼容),表示非 LLM 产出的版本 / 事后重建的轮次;当前示例均不使用。
- `Issue.location`:`[x,y,z]` mm 或 null,为检查所在的脚本坐标系(与 `part.step`/`part.glb` 一致,Z 向上;glb 的根节点旋转只是把 Z 向上转成 Y 向上,加载后对 location 施加同一变换即可)。由 `hole_edge_distance`(孔轴中点)、`internal_corner_radius`(最长尖角边中点 / 圆角面中心)、`min_wall_thickness`、`hole_spacing`(两孔轴中点连线中点)、`hole_depth_ratio`、`hole_breakout`、`hole_position`(最近的孔)、`deep_pocket`、`thin_web_height` 填写;`bbox_match`/`hole_count`/`hole_diameter`/`volume_range`/L1 为 null。message 文本不变。
- 每轮几何:某轮脚本执行成功时写 `v<n>/rounds/r<k>.glb`(k=轮次号),`run.json` 的 `rounds[].glb` 为相对路径(执行失败则无此字段);`round` 事件的载荷同样带 `glb`,并紧跟一条 `artifact`(`name:"rounds/r<k>.glb"`);`files` 清单包含这些文件;通过 `GET /api/runs/{id}/v{n}/rounds/r{k}.glb` 获取(白名单正则 `^rounds/r\d{1,3}\.glb$`)。
- 文件大小:`GET /api/runs/{id}`(及 `/api/examples` 每项)另含 `file_sizes`(`{"1": {"part.step": 48213, ...}}`,与 `files` 平行,字节数;不存在的文件不列出)。
- 下载文件名:`GET /api/runs/{id}/v{n}/{file}?download=1` 返回 `Content-Disposition: attachment; filename="<ascii 兜底>"; filename*=UTF-8''<名字>`,名字为 `<title>_v<n>.<ext>`(title 只保留字母/数字/中日韩字符与 `._-`,其他折叠为 `_`,最长 60):`part.step→.step`、`part.py→.py`、`drawing.pdf→.pdf`、`drawing.dxf→.dxf`、`drawing.png→_drawing.png`、`render.png→_render.png`、`run.json→_run.json`、`log.txt→_log.txt`、`rounds/r<k>.glb→_r<k>.glb`。不带参数时保持内联(预览)。前端 `src/lib/files.ts` 与 `web/server/store.py` 的 `download_name` 规则一致。
- 打包下载:`GET /api/runs/{id}/v{n}/bundle.zip`(示例同样可用)流式返回该版本面向用户的文件(STEP、part.py、drawing.pdf/dxf/png、render.png、run.json、log.txt;不含 glb、events、meta),zip 内文件名同上,附件名 `<title>_v<n>.zip`;访问令牌中间件同样适用;未知 run/示例/版本或无文件返回 404。
- `thumb.png`:成功版本额外生成的卡片缩略图(仅等轴测视图、透明背景、480×360,z-buffer 软渲染,`core.render.render_thumb`);`render.png`(四视图)不变。在 `files` 白名单内,产出时发 `artifact`(`thumb.png`),失败发 `artifact_failed`。示例的 thumb 与其余产物一起由 `scripts/make_examples.py` 生成(`scripts/make_example_glb.py` 仅为缺 glb/thumb 的旧样例补齐)。前端缩略图优先用 `thumb.png`,缺失时回退到 `render.png`。
