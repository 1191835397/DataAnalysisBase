# 实施摘要

> 面向编码前准备的单页摘要。关联：[REQUIREMENTS.md](./REQUIREMENTS.md) · [ARCHITECTURE.md](./ARCHITECTURE.md) · [MODULE_DESIGN.md](./MODULE_DESIGN.md) · [MODULE_INTERFACES.md](./MODULE_INTERFACES.md) · [CODING_STANDARDS.md](./CODING_STANDARDS.md) · [ROADMAP.md](./ROADMAP.md)

## 1. 当前仓库状态

- 当前仓库已从**设计文档仓库**进入 Phase A 工程骨架阶段。
- 目标产品是本地运行的 **A 股全市场智能监管与分析平台**。
- 目标技术栈已明确：`React + TypeScript + Vite`、`FastAPI`、`DuckDB`、`DeepSeek`。
- 设计资料已经覆盖到可编码级：需求、架构、模块边界、接口契约、配置样例、前后端页面/API、Phase 路线图。

结论：当前应继续沿 Phase A 主线补齐后端基础模块、全市场同步链路与首批 UI 页面。

## 2. 产品范围收敛

### v0.2 核心目标

- 全 A 股约 5000+ 标的的 30 分钟快照
- 行业排行、热力图、全市场股票列表
- 全市场监管规则与告警流
- 重点股 5 分钟深度同步、多源对账、AI 研报
- 本地 Web 仪表盘作为主交付面

### 明确不做

- AI 直接给买卖建议或预测涨跌
- 自动交易
- Level-2 高频实时系统
- 全市场财报全量深度抓取

## 3. 文档锚点

实现时建议只把下面这些文档当作高频入口：

| 用途 | 文档 |
|------|------|
| 需求基线 | [REQUIREMENTS.md](./REQUIREMENTS.md) |
| 总体架构 | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| 模块边界 | [MODULE_DESIGN.md](./MODULE_DESIGN.md) |
| 模块间接口 | [MODULE_INTERFACES.md](./MODULE_INTERFACES.md) |
| 编码硬约束 | [CODING_STANDARDS.md](./CODING_STANDARDS.md) |
| 实现顺序 | [ROADMAP.md](./ROADMAP.md) |
| 外部框架参考 | [FRAMEWORK_REFERENCES.md](./FRAMEWORK_REFERENCES.md) |
| API 细节 | [modules/08-api.md](./modules/08-api.md) |
| 前端细节 | [modules/09-frontend.md](./modules/09-frontend.md) |
| 配置样例 | [CONFIG_REFERENCE.md](./CONFIG_REFERENCE.md) 与 [examples/](./examples/) |

## 4. 推荐首版工程骨架

根据现有设计，建议首轮直接落成下面的 monorepo 结构：

```text
backend/
  pyproject.toml
  src/dataanalysisbase/
    domain/
    config_loader/
    storage/
    providers/
    ingest/
    surveillance/
    observability/
    api/
    common/
  tests/
frontend/
  package.json
  src/
config/
  providers.yaml
  sync_schedule.yaml
  surveillance_rules.yaml
  watchlist.yaml
  fusion_policy.yaml
  reconcile_thresholds.yaml
```

说明：

- `backend/` 对齐模块设计中的 Python 包路径。
- `frontend/` 独立，消费 `api` 暴露的 REST/WS。
- `config/` 由 `docs/examples/*.yaml` 和 `CONFIG_REFERENCE.md` 转化而来。
- `common/` 用于错误类型、时间工具、日志、幂等辅助等横切能力。

## 5. Phase A 最小闭环

### 目标

先跑通“全市场快照 -> 落库 -> 聚合 -> API -> Web 页面”的最小链路，不提前做 Fusion/LLM。

### 必做模块

1. `domain`
2. `config_loader`
3. `storage`
4. `providers`
5. `ingest`
6. `observability`
7. `api`
8. `frontend`

### 建议实现顺序

1. 初始化 `backend/` 与 `frontend/`
2. 建 `domain` DTO / 枚举 / ID 解析
3. 建 `storage` schema 与 repository
4. 接 `AkshareAdapter` 与 `ProviderRegistry`
5. 实现 `MarketBulkSync`
6. 刷新 `latest_market_snapshot` / `market_overview` / `industry` 聚合
7. 开 `FastAPI` 的 `overview` / `stocks` / `industries`
8. 开 `React` 三页：总览、行业、股票列表
9. 补 `data_status`、同步状态、缺失数量展示
10. 用 `make dev` 或等价命令跑通本地闭环

### Phase A 验收

- 可以手动触发一次全市场快照并落库
- 能看到市场总览、行业排行、股票列表
- UI 显示最后快照时间、数据状态、缺失数量
- 重复执行同一快照不会产生重复数据

## 6. 数据与配置关键约束

### 同步频率

- 全市场：30 分钟快照
- 重点股：5 分钟深度同步
- 全市场日 K / 主数据：日终任务

### 数据状态

对外统一使用：

- `fresh`
- `stale`
- `partial`
- `failed`
- `offline`

前后端必须都围绕这个状态模型实现，不要各写一套。

### 幂等主键

首批最关键的是快照写入幂等：

- `market_snapshots`: `(snapshot_time, security_id, source)`

### 配置外置

这些必须走配置文件或环境变量，禁止硬编码：

- provider 启停与优先级
- 快照调度
- surveillance 规则与去重窗口
- watchlist
- DeepSeek / Tushare 等密钥

## 7. 编码期硬约束

从现有规范提炼，最重要的是这几条：

- 只有 `providers` 模块允许直接依赖 `akshare` / `tushare`
- 只有 `storage` 模块允许直接写 SQL
- 跨模块只传 DTO，禁止裸传 `DataFrame` / `dict`
- 公开接口必须完整类型注解
- 计算逻辑尽量写成纯函数，IO 留在边界层
- API 使用 DuckDB 只读连接，写进程串行
- 所有时间都用带时区的 `Asia/Shanghai`
- LLM 不生成数字，数字必须来自本地工具或数据库

## 8. 已知文档不一致与编码前先统一项

这些不是阻塞问题，但建议在开工前统一口径：

| 项 | 现状 | 建议 |
|----|------|------|
| `MODULE_INTERFACES.md` 版本 | 仍写 `v0.1.0` | 升到与当前设计一致的版本号，避免误判 |
| `REQUIREMENTS.md` | `2.1`、`FR-S06/07`、`FR-D05/06` 有重复段落 | 清理重复条目，减少后续引用歧义 |
| 路线图术语 | 有些文档写 `Phase E` 后再补 `Phase F` | 保留现状即可，但后续所有任务拆解应明确是否含 F |
| 目录路径 | 架构文档提到 `src/dataanalysisbase/...`，仓库尚未初始化 | 直接按模块设计创建，避免后面迁移 |

## 9. 实现时的最小决策集

如果现在开始写代码，建议先固定以下决策，不要边写边摇摆：

- Python `3.11+`
- `pyproject.toml` 作为 Python 单一入口
- `ruff + mypy + pytest`
- `FastAPI` 提供 REST + WS
- `DuckDB` 作为单机主库
- `React 18 + TypeScript + Vite`
- `TanStack Query/Table + ECharts`

## 10. 下一步建议

最合理的下一步是直接进入 `Phase A` 工程初始化：

1. 创建 `backend/ frontend/ config/`
2. 落 `pyproject.toml`、基础包结构、测试结构
3. 把 `docs/examples/*.yaml` 复制为运行期配置模板
4. 先实现 `domain + storage + providers + ingest` 的最小链路

如果目标是尽快看到可运行页面，优先级应是：

`MarketBulkSync > AggregateRepo > FastAPI > React 三页`

## 11. 外部项目参考

已对 `superpowers`、`claw-code`、`ECC`、`anthropics/financial-services`、`TauricResearch/TradingAgents` 与 `666ghj/MiroFish` 做参考分析，结论见 [FRAMEWORK_REFERENCES.md](./FRAMEWORK_REFERENCES.md)。

当前不直接引入外部 Agent 框架、agent harness、hooks、LangGraph、Zep Cloud、OASIS/CAMEL 或 AGPL 项目代码。可吸收的内容分三类：

- Phase A/B：优先落地 `dab config validate`、`dab doctor`、`dab status --json`、mock provider 同步测试、System Status API。
- Phase B/D：借鉴 MiroFish 的任务流形态，补长任务状态持久化、进度日志、报告 artifact 和复杂任务分步 UI。
- Phase D：把 `ResearchAgent` 升级为结构化投研产物生成器，包含正反观点、风险检查、Tool trace、数据来源、快速核验、全景检索与人工复核声明。
- Phase F：用轻量 pipeline 做告警聚类叙事、每日市场综述、自然语言筛选、持仓/组合风险摘要和可选市场事件沙盘。

这些能力不得改变当前边界：不做自动交易，不给买卖建议，LLM 不生产数字，模拟视角或情景推演必须明确标注，未解决 L3 对账差异时禁止确定性结论。

首批已按“项目内化”方式落地：

- `dab config validate`
- `dab doctor`
- `dab status --json`
- `/api/v1/system/status`

这些命令和接口只做本地配置、状态、数据新鲜度诊断，不安装或接管任何外部 harness 生态。
