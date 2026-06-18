# 模块接口对接矩阵

| 属性 | 值 |
|------|-----|
| 版本 | v0.1.0 |
| 状态 | 接口契约（实现期对接的单一事实来源） |
| 目标 | 把 14 个模块散落在各自 §5 的对外接口汇总成一张图：共享 DTO、谁调谁、方法签名、错误契约 |

> 关联：[MODULE_DESIGN.md](./MODULE_DESIGN.md)（边界与依赖图）· [CODING_STANDARDS.md](./CODING_STANDARDS.md)（契约先行 §A.4/B.1）· `docs/modules/`（各模块详细设计）

本文件是"接口先行"的锚点：实现某模块前，先看这里它**依赖谁的什么方法、暴露什么给谁、传什么 DTO**。详细算法与字段仍以各模块文档为准。

---

## 1. 共享契约（全部定义在 domain）

跨模块传递只用 `domain` 中的 DTO/枚举/异常，**禁止裸传 DataFrame/dict**（CODING_STANDARDS §A.4）。

### 1.1 共享 DTO（`domain/contracts.py`）

| DTO | 关键字段 | 产出方 → 消费方 |
|-----|----------|-----------------|
| `RawDataset` | source, dataset_type, security_id?, records, raw_hash, fetched_at | providers → ingest / fusion |
| `MarketRow` | snapshot_time, security_id, name, price, change_pct, volume, amount, volume_ratio, pe_ttm, pb, market_cap, industry_code, source | providers→ingest→storage→surveillance |
| `SyncResult` | task, snapshot_time, status, expected, actual, missing, errors | ingest → observability / delivery |
| `FusionResult` | security_id, canonical_counts, issues, blocked | fusion → api / delivery |

### 1.2 共享枚举（`domain/enums.py`）

| 枚举 | 取值 | 用处 |
|------|------|------|
| `Market` | SH / SZ / BJ / HK / US | SecurityId 解析 |
| `SecurityType` | stock / fund / index | 实体类型 |
| `DatasetType` | MARKET_SPOT / DAILY_BARS / VALUATION / FINANCIALS / MONEY_FLOW / NEWS / FUND_NAV | provider 路由 |
| `RunStatus` | running / success / partial / failed | 快照任务状态 |
| `DataStatus` | fresh / stale / partial / failed / offline | 对外数据状态 |
| `AlertSeverity` | info / medium / high | 告警级别 |
| `Severity` | L0 / L1 / L2 / L3 | 对账差异级别 |

### 1.3 异常层级（`domain` 或 `common/errors.py`）

```text
DABError
├── ConfigError
├── ProviderError(provider, dataset_type, cause)   # 单源失败隔离
├── StorageError
├── FusionBlockedError                              # L3 阻断
└── LLMError / MaxIterationsError
```

模块只抛自己语义的异常，不向上泄露第三方异常（CODING_STANDARDS §B.4）。

---

## 2. ID 与解析（domain 暴露）

| 符号 | 签名 | 调用方 |
|------|------|--------|
| `SecurityId.parse` | `parse(raw: str) -> SecurityId` | providers, ingest, api |
| `to_source_code` | `to_source_code(sid: SecurityId, source: str) -> str` | providers |

---

## 3. 调用矩阵（谁调谁 · 方法 · 传入/返回）

> 箭头为运行期调用方向；均为单向向下，无环（依赖图见 MODULE_DESIGN §2）。

### 3.1 采集与存储主链（Phase A/B）

| 调用方 | 被调方 | 方法 | 传入 → 返回 |
|--------|--------|------|-------------|
| ingest.MarketBulkSync | providers.ProviderRegistry | `fetch_market_spot()` | — → `RawDataset(MARKET_SPOT)` |
| ingest.FocusSync | providers.ProviderRegistry | `fetch_all(dt, sid)` | DatasetType, str → `list[RawDataset]` |
| ingest | storage.SnapshotRepo | `begin_run / write_snapshot / commit_run` | `list[MarketRow]`, RunStatus → int/None |
| ingest | storage.AggregateRepo | `refresh_latest / refresh_overview` | snapshot_time → None |
| ingest | ingest.TradingCalendar | `is_trading_day / is_ex_dividend` | date → bool |
| ingest | surveillance.SurveillanceEngine | `evaluate(snapshot_time)` | datetime → `list[Alert]`（已落库） |
| ingest | observability.Metrics | `record_sync(result, elapsed_ms)` | `SyncResult` → None |
| surveillance | storage.SnapshotRepo | `get_snapshot / previous_snapshot_time` | datetime → `list[MarketRow]` |
| surveillance | storage.AlertRepo | `insert_alerts / recent_for_dedupe` | `list[Alert]` → int |
| surveillance | observability.Metrics | `record_surveillance(n, ms)` | int → None |

### 3.2 融合与智能（Phase C/D）

| 调用方 | 被调方 | 方法 | 传入 → 返回 |
|--------|--------|------|-------------|
| ingest.FocusSync | fusion.FusionPipeline | `run(security_id, dataset_types)` | str, list → `FusionResult` |
| fusion | storage.CanonicalRepo | `save_staging / save_issues / save_canonical` | rows → None |
| analytics.AnalyticsService | storage (canonical/bars) | repo 只读 | — → bars/financials |
| ingest.EodSync | analytics.AnalyticsService | `refresh_daily(security_ids)` | list → int |
| intelligence.tools | fusion (canonical/issues) | 只读 repo | — → ToolEnvelope |
| intelligence.tools | analytics.AnalyticsService | `get_indicators(sid)` | str → `IndicatorSet` |
| intelligence.ResearchAgent | intelligence.llm.DeepSeekClient | `chat / extract_structured` | messages → LlmResponse |

### 3.3 交付层（Phase A+ / E / F）

| 调用方 | 被调方 | 方法 | 传入 → 返回 |
|--------|--------|------|-------------|
| api.routers | storage.AggregateRepo | `get_stocks_page / overview` | StockQuery → `Page` |
| api.routers | storage.AlertRepo | `query(filters, page, size)` | → `Page[Alert]` |
| api.routers | observability | `build_system_status(...)` | → `SystemStatus` |
| api.envelope | observability | `compute_data_status(latest_run, now)` | → `DataStatus` |
| api.routers(research) | intelligence.ResearchAgent | `run(task, security_id)` | → `AgentResult` |
| api.routers(portfolio) | portfolio.PortfolioService | `get_summary / upsert / delete` | → `PortfolioSummary` |
| frontend | api | REST + `WS /ws/v1/alerts` | → `Envelope<T>` |
| surveillance(高级别) | delivery.Dispatcher | `dispatch(DeliveryMessage)` | → `list[DeliveryResult]` |
| scheduler(EOD) | delivery.DailyBriefBuilder | `build(trade_date)` | → Markdown |
| delivery.DailyBriefBuilder | intelligence.daily_brief | 综述生成 | → str |
| delivery.DailyBriefBuilder | portfolio.PortfolioService | `get_summary()` | → `PortfolioSummary` |
| surveillance(持仓告警) | portfolio.PortfolioService | `pnl_context(security_id)` | → `PositionView` |

---

## 4. 各模块对外暴露的稳定签名（public API surface）

> 实现这些签名即满足上游对接；内部实现细节不在此约束。

### domain
```python
SecurityId.parse(raw: str) -> SecurityId
to_source_code(sid: SecurityId, source: str) -> str
# DTO: RawDataset, MarketRow, SyncResult, FusionResult, Alert, ...
```

### config_loader
```python
load_settings() -> Settings
load_surveillance_rules() -> SurveillanceRules
load_sync_schedule() -> SyncSchedule
load_providers() -> ProvidersConfig
load_watchlist() -> Watchlist
```

### storage
```python
class DuckDBStore:
    def __init__(self, path, read_only=False); def transaction(self); def upsert(table, rows, key) -> int; def query(sql, params) -> list[dict]
class SnapshotRepo:
    begin_run(snapshot_time, source, expected); write_snapshot(rows: list[MarketRow]) -> int
    commit_run(snapshot_time, status: RunStatus, actual, missing, field_nulls, error); latest_committed() -> datetime|None
    get_snapshot(snapshot_time) -> list[MarketRow]; previous_snapshot_time(before) -> datetime|None
class AggregateRepo: refresh_latest(t); refresh_overview(t); get_stocks_page(query) -> Page
class AlertRepo: insert_alerts(list[Alert]) -> int; recent_for_dedupe(since); query(filters, page, size) -> Page[Alert]
class CanonicalRepo: save_staging(...); save_issues(...); save_canonical(...)
```

### providers
```python
class ProviderRegistry:
    fetch_market_spot() -> RawDataset
    fetch_all(dt: DatasetType, security_id: str, **kw) -> list[RawDataset]
    health_check_all() -> dict[str, ProviderHealth]
```

### ingest
```python
class MarketBulkSync: run(snapshot_time: datetime | None = None) -> SyncResult
class FocusSync: run(watchlist: list[str]) -> SyncResult
class EodSync: run() -> SyncResult
class TradingCalendar: is_trading_day(d); is_ex_dividend(sid, d); previous_trading_day(d)
class Scheduler: register_all(); start()
```

### surveillance
```python
class SurveillanceEngine: evaluate(snapshot_time: datetime) -> list[Alert]
class IndustryAggregator: aggregate(snapshot_time: datetime) -> None
```

### analytics
```python
class AnalyticsService:
    compute_indicators(security_id, days=120) -> IndicatorSet
    compute_financial_derived(security_id, years=3) -> list[FinancialDerived]
    refresh_daily(security_ids: list[SecurityId]) -> int
    find_similar_patterns(...) -> list[SimilarMatch]   # F
    correlation(base_id, peer_ids, days=120) -> dict[str, float]  # F
```

### fusion
```python
class FusionPipeline: run(security_id: str, dataset_types: list[DatasetType]) -> FusionResult
```

### intelligence
```python
class ResearchAgent: run(task: str, security_id: str) -> AgentResult
class DeepSeekClient: chat(messages, tools=None, response_format=None); extract_structured(text, schema)
def daily_brief(market, alerts) -> str          # F
def nl_query(text: str) -> FilterDSL            # F
```

### portfolio
```python
class PortfolioService:
    list_positions() -> list[Position]; upsert_position(p) -> Position; delete_position(id)
    get_summary() -> PortfolioSummary
    pnl_context(security_id) -> PositionView | None
```

### observability
```python
def compute_data_status(latest_run, now, stale_after_min=45) -> DataStatus
def build_system_status(snapshot_repo, registry, metrics, now) -> SystemStatus
class Metrics: record_sync(result, ms); record_surveillance(n, ms); record_llm(model, tokens, cost); snapshot() -> MetricsSnapshot
```

### api
```python
# 全部 GET 返回 Envelope[T]，列表类 data 为 Page；端点清单见 UI_DESIGN §5.3
# 依赖注入：get_store(read_only) / get_snapshot_repo / get_alert_repo / get_aggregate_repo
```

### delivery
```python
class DailyBriefBuilder: build(trade_date: date) -> str
class Dispatcher: dispatch(msg: DeliveryMessage) -> list[DeliveryResult]
# CLI: dab sync|research|ask|reconcile|status
```

### frontend
```text
消费 api 的 REST/WS；不暴露后端可调用接口（终端用户界面）
```

---

## 5. 两条主数据流（端到端对接验证用）

### 5.1 全市场监管流（Phase A→B）
```text
Scheduler →(30min守卫) MarketBulkSync.run
  → ProviderRegistry.fetch_market_spot() → RawDataset
  → 映射 list[MarketRow] → SnapshotRepo.write_snapshot (幂等)
  → commit_run + AggregateRepo.refresh_latest/overview
  → SurveillanceEngine.evaluate(t) → AlertRepo.insert_alerts
  → Metrics.record_sync
  → api 读聚合表/告警 (read_only) → Envelope(meta.data_status) → frontend (+WS 推 alert/snapshot_complete)
```

### 5.2 重点股深度流（Phase C→D→F）
```text
FocusSync.run(watchlist)
  → ProviderRegistry.fetch_all(dt, sid) → list[RawDataset]
  → FusionPipeline.run → canonical_* + reconciliation_issues (L3 阻断)
  → AnalyticsService.refresh_daily → analytics_indicators
  → ResearchAgent.run (tools 只读 canonical/issues/analytics, 数字⊆Tool, L3→confidence0)
  → api POST /research → AgentResult → frontend 研报 Tab
  → portfolio.pnl_context 为持仓告警附盈亏 (F)
```

---

## 6. 跨模块错误与降级契约

| 场景 | 抛出/状态 | 上游处理 |
|------|-----------|----------|
| 单源拉取失败 | `ProviderError`（隔离） | registry 跳过该源，其他源继续 |
| tushare 积分不足 | `ProviderError`(可降级) | ingest 用 akshare 单源 |
| 全市场 actual=0 / 偏少 | `RunStatus.failed/partial` | observability→`DataStatus`，api 仍回上一快照 |
| 对账 L3 未解决 | `FusionBlockedError` / blocked=true | 跳过 canonical 写入，intelligence confidence=0 |
| LLM 不可用 | `LLMError` | 研报降级"仅数据表格无解读"；api 503 `LLM_UNAVAILABLE` |
| 快照 stale/failed | meta.data_status | api 不报 500，前端顶栏黄/红 |

全链 `data_status` 透传，前端永不裸读可能过期数据（CODING_STANDARDS §B.10）。

---

## 7. 实现顺序与"接口先行"检查

落地序列（依赖向下）：

```text
domain → config_loader → storage → providers(akshare) → ingest → observability → api → frontend
（C: providers.tushare + ingest.focus + analytics；D: fusion + intelligence；F: portfolio + 叙事）
```

每个模块开工前自检：

- [ ] 它依赖的上游签名已在本文件 §4 列出且已实现（或先以 Protocol/stub 占位）
- [ ] 它产出/消费的 DTO 已在 domain 定义（§1.1）
- [ ] 它暴露给下游的签名与 §3 调用矩阵一致
- [ ] 错误按 §6 契约抛出与降级

---

*本文件为跨模块对接总览；签名以各模块详细设计 `docs/modules/` 为准，二者冲突时以模块文档为准并回填本文件。*
