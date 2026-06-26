# providers 模块实施记录

| 属性 | 值 |
|------|-----|
| 模块 | `providers` |
| 状态 | `done` |
| Phase | `A` |
| 负责人 | `TBD` |
| 最近更新 | `2026-06-25` |
| 关联设计 | [04-providers.md](./04-providers.md) |

## 1. 当前目标

实现统一的数据源适配层，优先完成 `AkshareAdapter` 和 `ProviderRegistry`，支撑全市场快照采集。

## 2. 本次范围

- `DataProvider` 协议
- `AkshareAdapter`
- `ProviderRegistry`
- 基础健康检查与错误隔离

不包含：

- Tushare 的重点股双源对账
- 公告、yfinance 扩展源

## 3. 前置依赖

- `domain`
- `config`
- `akshare`
- 网络访问与限流策略

## 4. 实现拆解

1. 定义 provider 协议与健康状态对象
2. 实现 `AkshareAdapter.fetch_market_spot()`
3. 实现 `ProviderRegistry` 路由
4. 补 mock 测试与故障隔离测试

## 5. 当前进度

### 已完成

- 数据源设计与字段映射文档已完成
- `MarketDataProvider` / `MarketSnapshotBatch` 合约已完成
- `AkshareAdapter.fetch_market_snapshot()` 最小现货快照映射已完成
- `ProviderRegistry` 已按 `providers.yaml` 的启用状态、数据集和优先级路由 `market_spot`
- `MarketBulkSync` 已可消费 provider batch 并刷新聚合表
- `dab sync market` 已提供默认 dry-run 与显式 `--execute` 手动执行入口
- provider 本地健康检查已接入 `dab doctor` 与 `/api/v1/system/status`
- provider 联网健康检查已通过显式 `--online` / `online=true` 接入 `dab doctor`、`dab status` 与 `/api/v1/system/status`
- 最近一次 market sync run 已接入 `dab status --json` 与 `/api/v1/system/status`
- provider 指数退避 retry 与单进程最小间隔限流已按 `providers.yaml` 接入 `ProviderRegistry`
- `AkshareAdapter` 已按 `stock_zh_a_spot_em` -> `stock_zh_a_spot` 顺序提供现货快照备用接口策略
- 真实 AKShare 全市场快照验证已成功：`2026-06-26T10:56:34.716157+08:00`，`expected=5367`、`actual=5367`、`missing=0`

## 6. 关键决策

| 决策 | 原因 | 影响 |
|------|------|------|
| 具体第三方库只允许出现在 `providers` | 保持上层源无关 | 可替换数据源而不影响业务层 |
| 单源失败不阻断全链路 | 免费数据源不稳定 | 上层要支持降级状态 |

## 7. 与原设计偏差

当前无实现，暂无偏差。

## 8. 代码位置

- `backend/src/dataanalysisbase/providers/`
- `backend/tests/providers/`

## 9. 风险与阻塞

- AKShare 上游页面变动会导致接口失效
- 免费源字段格式偶发变化，需要规范化层兜底

## 10. 下一步动作

1. 前端接入 `/api/v1/market/overview` 与 `/api/v1/stocks`
2. 后端补 `/api/v1/industries` 与行业成分股接口
