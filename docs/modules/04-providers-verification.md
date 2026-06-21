# providers 模块验证记录

| 属性 | 值 |
|------|-----|
| 模块 | `providers` |
| 验证状态 | `not_started` |
| 最近更新 | `2026-06-22` |
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
| `AkshareAdapter.fetch_market_spot()` 成功 | 集成测试 | `not_started` |  |
| DataFrame 正确映射为 `RawDataset` | 单元测试 | `not_started` |  |
| 单源异常被包装为 `ProviderError` | 单元测试 | `not_started` |  |
| `ProviderRegistry` 路由正确 | 单元测试 | `not_started` |  |

## 4. 边界场景

- 空数据集
- 字段缺失
- 超时或网络异常
- 非法 `DatasetType`

## 5. 已知问题

- 尚未开始实现与验证

## 6. 剩余风险

- 即使测试通过，真实市场时段仍需观察源稳定性

## 7. 验收结论

当前未达到 Phase A 交付标准；需完成 adapter、registry 与测试。
