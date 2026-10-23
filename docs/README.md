# Documentation / 文档索引

Lingenious (零件匠) is a parametric CAD agent for CNC machining: an LLM writes CadQuery scripts, and
deterministic B-Rep checks (validity, requirement match, DFM) judge and drive repairs. Start with the
[README](../README.md) ([简体中文](../README.zh-CN.md)).

面向 CNC 机加工的参数化 CAD 智能体:LLM 写 CadQuery 脚本,确定性的 B-Rep 校验(几何有效性、需求符合度、可制造性)负责判断并驱动修正。先看根目录 [README](../README.zh-CN.md)。

**Language / 语言:** architecture and ADRs are written in English (the primary README language); the user
and process-engineering references are in Chinese. 架构与 ADR 为英文;用户文档与工艺复核清单为中文。

## Users / 使用者

| Document | Content | Language |
|---|---|---|
| [configuration.md](configuration.md) | 全部 `config.yaml` 键、环境变量、`LINGENIOUS__` 覆盖、镜像与多架构构建 | 中文 |
| [web-app.md](web-app.md) | Web 应用:数据目录、REST/SSE 接口、访问口令、产物与下载 | 中文 |
| [dfm-rules.md](dfm-rules.md) | L0–L3 校验分层与 DFM 规则、阈值与优先级 | 中文 |

## Contributors / 贡献者

| Document | Content | Language |
|---|---|---|
| [architecture.md](architecture.md) | Modules, data flow, `run.json` and outputs, extension points | English |
| [adr/](adr/README.md) | Architecture Decision Records: why the system is built this way | English |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Dev loop, adding rules and eval tasks, code style, releases | English |
| [AGENTS.md](../AGENTS.md) | Short guide for AI coding agents and humans: layout, commands, conventions | English |

## Process engineers / 工艺人员

| Document | Content | Language |
|---|---|---|
| [dfm-review-checklist.md](dfm-review-checklist.md) | DFM 规则与阈值复核清单(可直接填写结论) | 中文 |

## Optional components / 可选组件

| Document | Content | Language |
|---|---|---|
| [adapters/feishu_bitable/README.md](../adapters/feishu_bitable/README.md) | Feishu Bitable demo adapter: setup, table schema, trigger rules | English |
