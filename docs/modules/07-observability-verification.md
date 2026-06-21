# observability 模块验证记录

| 属性 | 值 |
|------|-----|
| 模块 | `observability` |
| 验证状态 | `not_started` |
| 最近更新 | `2026-06-22` |
| 关联实现 | [07-observability-implementation.md](./07-observability-implementation.md) |

## 1. 验收目标

- 能根据最近运行结果准确计算 `fresh/stale/partial/failed/offline`
- 系统状态接口能读取核心运行指标

## 2. 测试范围

- 单元测试：状态计算函数
- 集成测试：与 ingest / API 连接
- 手动验证：观察顶栏状态变化

## 3. 验证清单

| 项 | 方法 | 结果 | 备注 |
|----|------|------|------|
| `fresh` 判定正确 | 单元测试 | `not_started` |  |
| 超过阈值返回 `stale` | 单元测试 | `not_started` |  |
| 最近运行失败返回 `failed` | 单元测试 | `not_started` |  |
| 部分成功返回 `partial` | 单元测试 | `not_started` |  |
| 无运行返回 `offline` | 单元测试 | `not_started` |  |

## 4. 边界场景

- 时钟跨交易日
- 最近成功但其后失败
- 没有任何历史运行

## 5. 已知问题

- 尚未开始实现与验证

## 6. 剩余风险

- stale 阈值最终可能要按市场时段和页面类型细分

## 7. 验收结论

当前未达到交付标准；需完成状态计算与 API 联调。
