# providers 模块验证记录

| 属性 | 值 |
|------|-----|
| 模块 | `providers` |
| 验证状态 | `partial` |
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
| 真实 `dab sync market --execute` | 手动验证 | `blocked` | AKShare/Eastmoney 远端断开连接；失败 run 已落库 |
| 最近 market run 状态 | CLI/API 测试 + 手动验证 | `passed` | `dab status --json` 返回 `last_market_run` 和失败原因 |
| provider retry wrapper | 单元测试 | `passed` | 只重试 `retryable=True` 的 `ProviderError`，使用指数退避 |
| provider rate limit wrapper | 单元测试 | `passed` | 按 `requests_per_minute` 控制单进程最小间隔 |

## 4. 边界场景

- 空数据集
- 字段缺失
- 超时或网络异常
- 非法 `DatasetType`

## 5. 已知问题

- 真实 AKShare 请求已到达上游，但 Eastmoney 远端返回 `RemoteDisconnected`，尚未取得成功快照
- 联网健康检查尚未实现
- 当前已有指数退避和单进程固定间隔限流，还没有备用接口

## 6. 剩余风险

- 免费源真实请求可能被上游断开，指数退避仍可能失败，需要备用接口策略

## 7. 验收结论

当前达到最小 adapter、registry、手动同步入口、本地 provider health、指数退避 retry / 限流 wrapper 与失败 run 持久化验证标准；Phase A 完整交付仍需完成联网健康检查、上游断连备用接口策略，并取得一次成功真实快照。
