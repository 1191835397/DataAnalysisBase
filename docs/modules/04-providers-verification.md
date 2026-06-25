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

## 4. 边界场景

- 空数据集
- 字段缺失
- 超时或网络异常
- 非法 `DatasetType`

## 5. 已知问题

- 尚未进行真实 AKShare 联网手动验证
- 联网健康检查尚未实现
- 限流策略尚未实现

## 6. 剩余风险

- 即使测试通过，真实市场时段仍需观察源稳定性

## 7. 验收结论

当前达到最小 adapter、registry、手动同步入口和本地 provider health 单元验证标准；Phase A 完整交付仍需完成限流、联网健康检查与真实联网手动验证。
