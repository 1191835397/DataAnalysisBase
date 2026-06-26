# 外部项目参考与落地建议

| 属性 | 值 |
|------|-----|
| 状态 | 参考分析 |
| 参考来源 | `D:/Project/AIProject/GithubProject/*.md` |
| 目标 | 记录可借鉴的工程流程、Agent 工作流、诊断能力、配置治理、风险约束与后续落地方式 |

本文只记录可参考的设计思路，不把外部仓库作为当前项目依赖。当前项目仍以 Phase A 的本地数据闭环为优先目标。

---

## 1. 总结

本轮参考了 6 份外部项目分析：

| 项目 | 定位 | 对本项目的主要价值 |
|------|------|--------------------|
| `obra/superpowers` | AI coding agent 工程流程技能库 | 设计、计划、TDD、调试、评审、完成前验证 |
| `ultraworkers/claw-code` | Rust-first agent CLI harness | `doctor/status`、权限边界、mock parity、JSON 输出、会话审计 |
| `affaan-m/ECC` | 跨 harness agent 操作系统 | profile/manifest、安装计划预览、状态库、治理事件、安全扫描 |
| `anthropics/financial-services` | Claude 金融工作流模板集合 | 结构化金融产物、人工复核、CLI/slash command、金融 workflow 拆分 |
| `TauricResearch/TradingAgents` | 多智能体交易研究框架 | 基本面/新闻/技术/风险视角、正反观点、组合风险摘要 |
| `666ghj/MiroFish` | 群体智能仿真与预测报告应用 | 分步任务流、图谱到 Agent Profile、长任务进度、报告工具形态、情景沙盘 |

共同结论：

- 这些项目都不适合现在作为依赖直接接入。
- 当前项目首要任务仍是跑通 `MarketBulkSync -> DuckDB -> API -> Web`。
- 可借鉴内容应拆成“工程可靠性”与“智能分析能力”两条线分阶段落地。

其中金融 Agent 类项目不适合直接接入当前项目：

- 前者是 Claude 金融服务行业 workflow / agent / skill 模板集合，运行时和插件格式面向 Anthropic 生态。
- 后者是基于 LangGraph 的多智能体交易研究框架，定位偏研究实验，不是生产交易系统。

Agent harness / workflow 类项目也不适合直接接入：

- `superpowers` 更适合作为流程方法论参考，不应把其插件和 hook 安装到当前项目。
- `claw-code` 是完整 CLI harness 实现，当前项目只需要借鉴诊断、权限、mock harness 思路。
- `ECC` 覆盖 hooks、MCP、控制面、安装器和状态库，能力强但复杂度和执行面过大。

应用型多 Agent 项目也不适合直接接入：

- `MiroFish` 是完整 Web 应用，不是当前项目的插件或底层库。
- 它强依赖 LLM、Zep Cloud、OASIS/CAMEL 和本地仿真脚本，当前阶段会显著抬高复杂度。
- 它采用 `AGPL-3.0` 许可证，不应复制代码或直接集成，除非先完成许可证合规审查。
- 它的“预测报告”更适合作为情景推演参考，不应改变本项目“不输出确定性投资结论”的边界。

---

## 2. 可参考内容

### 2.1 Superpowers

适合参考“工程流程门禁”。

可吸收点：

- 复杂任务先设计、再计划、再实现。
- 关键逻辑优先 TDD：先看到失败测试，再做最小实现。
- 系统性调试：先定位根因，再修复，不用猜测式修改。
- 完成前必须运行新鲜验证命令。
- 代码评审与接收评审时先验证再反驳/修改。

在本项目中的对应落点：

| 外部思路 | 本项目落点 |
|----------|------------|
| brainstorming | 复杂模块先补设计小节或实施记录 |
| writing-plans | `docs/modules/*-implementation.md` 中维护执行步骤 |
| TDD | `backend/tests/` 中先覆盖 domain/storage/ingest 关键路径 |
| systematic debugging | 排障记录写入模块 verification 文档 |
| verification before completion | 模块交付必须包含实际命令与结果 |

近期可落地：

- 将 `MODULE_DELIVERY_STANDARD.md` 作为每个模块的完成门禁。
- Phase A 的 `providers/ingest/storage` 改动必须至少有 mock 单测或集成测试。
- 完成声明必须明确“已验证 / 验证缺口”。

不建议直接采用：

- 安装其插件、hooks 或启动注入机制。
- 把通用 coding skill 原样搬进项目文档。
- 在轻量任务中强制完整 TDD/评审流程，避免流程成本过高。

### 2.2 Claw Code

适合参考“本地 CLI 诊断、权限、安全边界与 mock parity”。

可吸收点：

- `doctor` / `status`：统一检查环境、配置、凭证、服务状态。
- JSON 输出：便于自动化脚本、CI、前端或调试工具消费。
- 明确 permission mode / workspace jail 思路。
- mock parity harness：用确定性 mock 覆盖核心 tool loop 场景。
- session / usage / telemetry：记录任务运行状态、成本、失败原因。

在本项目中的对应落点：

| 外部思路 | 本项目落点 |
|----------|------------|
| `doctor` | `delivery.cli` 的 `dab doctor` |
| `status` | `dab status` 与 `/api/v1/system/status` |
| JSON output | CLI 支持 `--json` |
| mock parity | `tests/ingest` 使用 mock provider 场景 |
| permission boundary | 限定数据写入目录与 provider 凭证读取 |

近期可落地：

- `dab config validate`：校验 YAML/env，不启动同步。
- `dab doctor`：检查 `.env`、DuckDB 路径、config 文件、provider 启停。
- `dab status --json`：输出最新快照、run 状态、数据新鲜度。
- mock provider 场景：success、partial、failed、duplicate upsert。

不建议直接采用：

- Rust harness、MCP runtime、plugin runtime。
- Shell/file tool 权限系统的完整复杂度。
- Session resume / provider adapter 的通用 agent harness 能力。

### 2.3 ECC

适合参考“配置治理、profile、安装/执行计划预览、状态与安全审计”。

可吸收点：

- manifest/profile 驱动的安装或启用计划。
- `plan` 命令先预览要做什么，再执行。
- 状态库：active sessions、运行状态、治理事件、健康检查。
- `doctor` / `repair` / `security-ioc-scan` 类操作面。
- 供应链与本机执行面的安全说明。

在本项目中的对应落点：

| 外部思路 | 本项目落点 |
|----------|------------|
| install profile | `dev`、`local-live`、`offline`、`replay` 运行 profile |
| plan preview | `dab plan sync-market` / `dab plan local-live` |
| state store | DuckDB 中的 `*_runs`、system status、governance events |
| security scan | 配置/密钥/输出目录安全检查 |
| control pane | 后续 Web System Status 页面 |

近期可落地：

- 配置 profile 文档化：明确每种模式启用哪些任务、provider、频率。
- `dab plan`：预览即将执行的同步任务、写入表、provider、预计影响。
- system status 聚合：最新快照、失败 run、配置状态、provider health。

后续可考虑：

- 简单治理事件表：记录配置变更、手动同步、失败恢复、规则热加载。
- Web “System Status” 页面显示运行状态和最近错误。

不建议直接采用：

- hooks runtime。
- 跨 harness 安装器。
- control pane 的完整实现。
- 大规模 skills/agents/commands 分发模式。

### 2.4 Anthropic financial-services

适合参考“金融工作流产品化”。

可吸收点：

- 把金融场景拆成可复用工作流：研究报告、晨报、差异解释、尽调清单、客户报告等。
- 将 Agent 输出收敛为固定模板，而不是自由生成文本。
- 通过 slash command / CLI 形成稳定任务入口。
- 明确 AI 输出是草稿，需人工复核，不构成投资建议。
- 按垂直领域组织技能与工具，例如 financial-analysis、equity-research、operations。

在本项目中的对应落点：

| 外部思路 | 本项目落点 |
|----------|------------|
| workflow agent | `intelligence.agents` |
| vertical skills | `intelligence.tools` + prompt templates |
| slash command | `delivery.cli` |
| MCP connector | `providers` / 后续 MCP 数据接入 |
| 人工复核声明 | 研报、日报、告警叙事统一免责声明 |

不建议直接采用：

- Claude plugin / skill 文件格式
- Managed Agents API 部署结构
- 面向投行 / KYC / 基金运营的无关工作流

### 2.5 TradingAgents

适合参考“多角色投研流程”。

可吸收点：

- Analyst Team：基本面、新闻、情绪、技术等维度分工。
- Bull / Bear Researcher：正反观点辩论。
- Risk Management Team：激进、中性、保守等风险视角。
- Portfolio Manager：组合层面汇总。
- 用图流程组织多步骤分析，保留中间状态。

在本项目中的对应落点：

| 外部角色 | 本项目轻量实现 |
|----------|----------------|
| fundamental analyst | `get_fused_financials` + `compare_peers` |
| news analyst | `search_documents` + `event_timeline` |
| technical analyst | `analytics.indicators` |
| sentiment analyst | Phase E/F 新闻事件情绪抽取 |
| bull researcher | 研报中的“正向因素”段 |
| bear researcher | 研报中的“反向风险”段 |
| risk agents | 数据质量、对账 L3、估值异常、持仓暴露检查 |
| portfolio manager | Phase F `portfolio` 摘要与持仓风险视图 |

不建议直接采用：

- 交易决策 agent
- 自动买卖建议
- 完整 LangGraph 依赖
- 面向真实资金交易的行动输出

### 2.6 MiroFish

适合参考“材料驱动的分步分析、长任务进度、报告工具与情景沙盘形态”。

可吸收点：

- 分步任务流：种子材料、图谱构建、Agent Profile、仿真运行、报告生成、交互追问。
- 图谱思路：把文本、事件、实体和关系组织成可检索上下文。
- 报告工具形态：深度洞察检索、全景搜索、快速核验、模拟 Agent 采访。
- 长任务状态：图谱构建、仿真准备、报告生成都有进度、日志和产物。
- 产物目录：项目、仿真、报告按独立 artifact 保存，便于复查。

在本项目中的对应落点：

| 外部思路 | 本项目落点 |
|----------|------------|
| 分步任务 UI | 数据同步、质量检查、告警聚类、报告生成、人工复核 |
| 图谱构建 | 后续事件图、行业/概念/标的关系图，当前仍 DuckDB-first |
| `insight_forge` | 深度检索 DuckDB 中行情、财务、告警、新闻、对账结果 |
| `panorama_search` | 市场总览、行业排行、历史区间、Top 异动拉取 |
| `quick_search` | 对报告中的数字、日期、来源做快速核验 |
| `interview_agents` | 生成正向因素、反向风险、风险复核等模拟分析视角 |
| Task progress | DuckDB 持久化 sync/report/LLM task run 与 progress logs |
| Artifact layout | 报告、日报、告警聚类结果按 run id 保存，支持复盘 |

近期可落地：

- 把长任务状态从一开始设计成可持久化模型，避免只存在进程内存。
- 在 `dab status` 和 `/api/v1/system/status` 中预留 run 状态、最近失败、数据新鲜度聚合能力。
- Phase D 的结构化研报模板加入“深度检索、全景检索、快速核验、模拟视角”四类工具痕迹。

后续可考虑：

- Phase F 增加“市场事件沙盘”或“政策/新闻事件情景推演”模块。
- 对行业、概念、标的、新闻事件建立轻量事件图或关系图。
- 在 Web 端为复杂任务提供分步进度页和 artifact 查看页。

不建议直接采用：

- `AGPL-3.0` 代码直接复制或集成。
- Zep Cloud 作为当前阶段图谱依赖。
- OASIS/CAMEL 多 Agent 仿真链路。
- “预测万物”产品定位。
- 用模拟 Agent 输出替代真实数据、人工复核或风险约束。

---

## 3. 当前项目应保持的边界

这些边界不因参考外部框架而改变：

- 不做自动交易。
- 不输出买卖建议或涨跌预测。
- 全市场层不做 5000 只股票逐只 LLM 解读。
- LLM 不生产数字，所有数字必须来自本地 Tool / DB。
- 数据源访问仍只通过 `providers`。
- SQL 写入仍只通过 `storage`。
- 未解决 L3 对账差异时，禁止输出确定性投资结论。

---

## 4. 分阶段落地建议

### Phase A：工程可靠性优先

当前优先级仍是：

```text
MarketBulkSync -> DuckDB -> AggregateRepo -> FastAPI -> React 三页
```

此阶段只吸收外部框架的“工程纪律”：

- 输出保留来源与时间戳。
- API 返回 `data_status`。
- 同步、聚合、告警都有可追踪状态。
- UI 明确展示 stale / partial / failed。
- 关键同步链路必须有 mock 测试。

建议新增近期任务：

```text
dab config validate
dab doctor
dab status --json
mock provider ingest tests
```

### Phase B：监管与状态面板

借鉴 `claw-code` 与 `ECC`，在监管引擎落地时同步完善：

- `/api/v1/system/status`
- Web System Status 页面
- provider health 状态
- 最近同步失败原因
- 告警数量、规则版本、数据新鲜度
- `dab plan` 预览本地任务

### Phase D：升级 ResearchAgent 为结构化投研产物生成器

建议在现有 `AGENT_INTELLIGENCE.md` 基础上增强研报结构：

```text
1. 数据概览
2. 正向因素（bull_points）
3. 反向风险（bear_points）
4. 估值与同业对比
5. 多源对账说明
6. 风险检查结果
7. 待人工复核问题
8. 免责声明
```

建议新增或强化字段：

- `tool_trace`：记录 Tool 名称、数据表、数据日期、置信度。
- `used_sources`：列出结构化数据来源。
- `confidence`：继承 Tool envelope 与 L2/L3 对账规则。
- `review_required`：默认 true。
- `has_unresolved_l3`：为 true 时阻断确定性结论。

建议的轻量流程：

```text
Tool 取数 -> 数据质量检查 -> 正反观点生成 -> 风险检查 -> 研报合成 -> 幻觉检测
```

### Phase F：引入轻量多角色流程，而不是完整多 Agent 框架

建议采用确定性 pipeline，而不是先引入 LangGraph：

```text
structured_data
  -> fundamental_view
  -> market_news_view
  -> technical_view
  -> bull_bear_summary
  -> risk_review
  -> final_research_summary
```

适合落地的能力：

- 告警聚类后生成市场事件叙事。
- 每日市场综述。
- 自然语言筛选全市场（NL -> 受控 filter DSL）。
- 持仓 / 组合风险摘要。
- 规则触发后的历史表现回测。

---

## 5. 具体优化清单

| 优先级 | 建议 | 阶段 | 说明 |
|--------|------|------|------|
| 高 | `dab config validate` | Phase A | 校验 YAML/env，减少启动期失败 |
| 高 | `dab doctor` | Phase A | 检查配置、DuckDB、provider、数据目录 |
| 高 | `dab status --json` | Phase A/B | 输出最新快照和运行状态，便于自动化 |
| 高 | mock provider 同步测试 | Phase A | 覆盖 success/partial/failed/幂等 |
| 高 | 模块完成前强制记录验证结果 | Phase A+ | 借鉴 superpowers 的完成前验证 |
| 中高 | `dab plan` 执行预览 | Phase B | 借鉴 ECC profile/plan 思路 |
| 中高 | System Status API / 页面 | Phase B | 展示数据状态、provider health、最近错误 |
| 中高 | 长任务状态与进度日志持久化 | Phase B/D | 借鉴 MiroFish 的任务流，但状态落 DuckDB |
| 高 | 研报模板加入正反观点和风险检查 | Phase D | 借鉴 TradingAgents，但不输出交易动作 |
| 高 | Tool 调用链路记录 `tool_trace` | Phase D | 支撑审计、复核、幻觉检测 |
| 中高 | 研报工具拆成深度检索、全景检索、快速核验、模拟视角 | Phase D | 借鉴 MiroFish ReportAgent 工具形态 |
| 高 | AI 输出默认标记需人工复核 | Phase D | 借鉴金融服务工作流的复核约束 |
| 高 | 未解决 L3 差异阻断确定性结论 | Phase D | 已有设计，应在实现中强制 |
| 中 | 复杂任务分步 UI 与 artifact 查看 | Phase B/F | 用于同步、聚类、报告生成、复盘 |
| 中高 | 市场事件叙事只对聚类告警调用 LLM | Phase F | 避免 5000x LLM 成本 |
| 中 | NLQ 转受控筛选 DSL | Phase F | LLM 只翻译条件，不生成 SQL |
| 中 | 持仓风险摘要 | Phase F | 借鉴 portfolio manager 思路 |
| 中 | 规则即信号回测 | Phase F | 验证监管规则是否有解释价值 |
| 低 | 市场事件沙盘 / 情景推演 | Phase F+ | 借鉴 MiroFish 仿真思想，只做辅助推演 |
| 低 | LangGraph / 图式编排 | 后续评估 | 等确定性 pipeline 复杂度超过阈值再考虑 |

---

## 6. 验证要求

任何吸收外部框架思想的实现，都必须满足现有项目门禁：

- CLI 诊断命令必须支持可自动化的 JSON 输出。
- `doctor` 不得泄露 API key、token、webhook 等密钥。
- `plan` 只能预览或解释影响，真实写入必须由明确执行命令触发。
- mock provider 测试不得联网。
- 单元测试覆盖模板渲染、Tool envelope、confidence 计算。
- Agent 集成测试使用 mock LLM，不联网。
- 幻觉检测验证输出数字必须来自 Tool 返回。
- L3 阻断测试必须证明不会生成确定性投资结论。
- NLQ 测试必须证明非法字段、非法算子会被拒绝。
- 日报 / 研报必须包含数据日期、来源、免责声明。
- 任何模拟视角或情景推演必须明确标注为“模拟/推演”，不得写成事实或预测结论。
- 长任务状态不得只依赖进程内存；至少要能从 DuckDB 或 artifact 恢复最近状态。
- 不得复制或直接集成 `AGPL-3.0` 项目代码，除非完成许可证合规审查。

---

## 7. 当前结论

现在不引入外部 Agent 框架或 agent harness；先把 Phase A 数据闭环做稳。

近期已落地：`dab config validate`、`dab doctor`、`dab status --json`、`dab plan sync-market`、`dab sync market` dry-run、provider 本地健康检查、最近 market run 状态、mock provider 同步测试。

后续最值得落地的是：把 Phase D 的 `ResearchAgent` 做成结构化投研产物生成器，并在 Phase F 用轻量 pipeline 实现正反观点、风险检查、市场事件叙事、组合风险摘要和可选情景推演。

---

## 8. 本项目化落地方式

外部项目的能力只通过本项目自己的文档、CLI、API、测试体系落地：

| 外部思想 | 本项目化产物 | 接入边界 |
|----------|--------------|----------|
| Superpowers 流程纪律 | `MODULE_DELIVERY_STANDARD.md`、模块 implementation/verification 文档、测试先行约束 | 不安装 skills/hooks/bootstrap |
| ECC 治理/诊断形态 | `dab config validate`、`dab doctor`、`dab status --json`、`dab plan sync-market`、`dab sync market` dry-run、provider 本地健康检查、最近 market run 状态、`/api/v1/system/status` | 不接管多 harness 配置，不引入 hooks runtime |
| Claw Code mock parity | mock provider 同步测试、状态 JSON 输出 | 不引入 agent CLI harness |
| 金融工作流模板 | Phase D 结构化研报模板 | 不接入 Claude 插件生态 |
| 多角色投研 | Phase F 轻量 pipeline | 不引入 LangGraph，不输出交易动作 |
| MiroFish 分步仿真与报告形态 | 长任务状态、报告工具拆分、复杂任务分步 UI、未来市场事件沙盘 | 不复制 AGPL 代码，不接入 Zep/OASIS/CAMEL |

已落地方向：

- Phase A 先提供最小诊断面：`dab config validate`、`dab doctor`、`dab status --json`、`dab plan sync-market`、`dab sync market` dry-run、provider 本地健康检查、最近 market run 状态、`/api/v1/system/status`。
- 已补齐 mock provider 同步测试。
- 后续补齐 Web System Status 页面、provider 限流、联网健康检查和真实联网验证。
