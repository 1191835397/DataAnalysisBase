# providers 模块验证记录

| 属性 | 值 |
|------|-----|
| 模块 | `providers` |
| 验证状态 | `passed` |
| 最近更新 | `2026-06-25` |
| 关联实现 | [04-providers-implementation.md](./04-providers-implementation.md) |

## 1. 验收目标

- 可以拉取一份全市场现货快照并封装为 `RawDataset`
- 单源错误能被隔离并结构化返回
- Provider 健康状态可查询

## 2. 测试范围

- 单元测试：字段映射、raw_hash、路由逻辑
- 集成测试：mock `akshare` 返回 DataFrame 转 `RawDataset`
- 手动验证：执行一次市场快照拉取

## 3. 验证清单

| 项 | 方法 | 结果 | 备注 |
|----|------|------|------|
| `AkshareAdapter.fetch_market_snapshot()` 成功 | 单元测试 | `passed` | Fake DataFrame-like 输入，不联网 |
| DataFrame 正确映射为 `MarketSnapshotBatch` / `MarketRow` | 单元测试 | `passed` | 覆盖代码、名称、价格、涨跌幅、量比、估值、行业 |
| 单源异常被包装为 `ProviderError` | 单元测试 | `passed` | 覆盖 fetcher 异常 |
| `ProviderRegistry` 路由正确 | 单元测试 | `passed` | 覆盖优先级、禁用 provider、未知 provider |
| `dab sync market` 默认 dry-run | 单元测试 | `passed` | 不调用 provider，不写 DuckDB |
| provider 本地健康检查 | 单元测试 | `passed` | 覆盖依赖存在、token 缺失、禁用 provider、未知 provider |
| `/api/v1/system/status` provider health | API 测试 | `passed` | 返回 `providers` 列表 |
| provider 联网健康检查 | 单元测试 + CLI/API 测试 | `passed` | 显式 `--online` / `online=true` 才探测上游端点，不拉取行情数据 |
| 真实 `dab sync market --execute` | 手动验证 | `passed` | 2026-06-26 10:56:34 +08:00，`expected=5367`、`actual=5367`、`missing=0` |
| 最近 market run 状态 | CLI/API 测试 + 手动验证 | `passed` | `dab status --json` 返回 `last_market_run` 和失败原因 |
| provider retry wrapper | 单元测试 | `passed` | 只重试 `retryable=True` 的 `ProviderError`，使用指数退避 |
| provider rate limit wrapper | 单元测试 | `passed` | 按 `requests_per_minute` 控制单进程最小间隔 |
| AKShare 备用现货接口 | 单元测试 | `passed` | `stock_zh_a_spot_em` 失败后 fallback 到 `stock_zh_a_spot`，不联网 |

## 4. 边界场景

- 空数据集
- 字段缺失
- 超时或网络异常
- 非法 `DatasetType`

## 5. 已知问题

- 免费源仍可能因上游策略、接口变更或网络权限失败，需要保留失败 run 与 status 诊断

## 6. 剩余风险

- AKShare/Eastmoney 免费接口稳定性不可保证，后续仍需观察失败率并评估 Tushare / 其他源补充

## 7. 验收结论

当前达到最小 adapter、registry、手动同步入口、本地 provider health、显式联网健康检查、指数退避 retry / 限流 wrapper、AKShare 备用现货接口、失败 run 持久化与真实成功快照验证标准。`dab status --online --json` 已返回 `data_status=fresh` 和最近成功 market run。
