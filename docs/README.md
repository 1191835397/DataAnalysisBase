# DataAnalysisBase 文档索引

> 本地 A 股全市场智能监管与分析平台 · 设计 v0.2.0

## 阅读顺序（推荐）

```text
1. REQUIREMENTS.md      → 要做什么
2. ARCHITECTURE.md      → 总体怎么搭
3. MARKET_SURVEILLANCE → 全市场 + 监管
4. UI_DESIGN.md         → 仪表盘长什么样
5. DESIGN_REVIEW.md     → 设计是否能达成目标
6. INTELLIGENCE_ROADMAP → 怎么更智能、更完善
7. MODULE_DESIGN.md     → 各模块怎么拆、怎么实现
8. CODING_STANDARDS.md  → 代码风格与工程原则（编码期强制）
9. PRODUCT_OUTCOMES.md  → 做完能看到什么
10. ROADMAP.md          → 实现顺序
```

## 文档列表

| 文档 | 说明 |
|------|------|
| [REQUIREMENTS.md](./REQUIREMENTS.md) | **产品需求规格（PRD）** v0.2 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | **主架构设计**（双层架构、分层、存储） |
| [MODULE_DESIGN.md](./MODULE_DESIGN.md) | **模块总览与边界**（14 模块、依赖图、Phase 对照） |
| [modules/](./modules/README.md) | **单模块详细设计**（可编码级：类、方法、状态机、DDL、测试） |
| [MODULE_INTERFACES.md](./MODULE_INTERFACES.md) | **模块接口对接矩阵**（共享 DTO、调用矩阵、暴露签名、错误契约） |
| [CODING_STANDARDS.md](./CODING_STANDARDS.md) | **编码规范与工程原则**（代码风格 + 设计范式，编码期强制） |
| [MARKET_SURVEILLANCE.md](./MARKET_SURVEILLANCE.md) | 全市场层、行业、监管引擎、调度 |
| [UI_DESIGN.md](./UI_DESIGN.md) | React 仪表盘六页、REST/WebSocket API |
| [DESIGN_REVIEW.md](./DESIGN_REVIEW.md) | 当前设计评审、优化点与剩余风险 |
| [INTELLIGENCE_ROADMAP.md](./INTELLIGENCE_ROADMAP.md) | 智能化与扩展路线（自适应异常、事件叙事、NL 查询、持仓、正确性陷阱） |
| [PRODUCT_OUTCOMES.md](./PRODUCT_OUTCOMES.md) | 最终实现效果与用户场景 |
| [DATA_SOURCES.md](./DATA_SOURCES.md) | AKShare / Tushare 数据源 |
| [FUSION_RECONCILE.md](./FUSION_RECONCILE.md) | 重点股多源融合与对账 |
| [AGENT_INTELLIGENCE.md](./AGENT_INTELLIGENCE.md) | DeepSeek Agent 设计 |
| [ROADMAP.md](./ROADMAP.md) | 设计阶段 + Phase A~E 路线图 |
| [CONFIG_REFERENCE.md](./CONFIG_REFERENCE.md) | 同步调度与监管规则配置 |

## 配置示例

| 文件 | 说明 |
|------|------|
| [examples/fusion_policy.yaml](./examples/fusion_policy.yaml) | 融合策略（重点股） |
| [examples/reconcile_thresholds.yaml](./examples/reconcile_thresholds.yaml) | 对账阈值 |
| [examples/watchlist.yaml](./examples/watchlist.yaml) | 重点股自选 |
| [examples/providers.yaml](./examples/providers.yaml) | 数据源启用 |

调度与监管配置见 [CONFIG_REFERENCE.md](./CONFIG_REFERENCE.md)（实现时复制到 `config/`）。

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1.0 | 2026-06-14 | 多源融合 + CLI 研究助手 |
| v0.2.0 | 2026-06-14 | 全 A 股监管 + Web 仪表盘 + 双层架构 |
| v0.2.2 | 2026-06-17 | 智能化路线：自适应异常、事件叙事、NL 查询、持仓、正确性陷阱 |

## 当前状态

**设计文档阶段已完成，尚未开始编码。** 实现从 [ROADMAP.md](./ROADMAP.md) Phase A 启动。
