# api 模块验证记录

| 属性 | 值 |
|------|-----|
| 模块 | `api` |
| 验证状态 | `not_started` |
| 最近更新 | `2026-06-22` |
| 关联实现 | [08-api-implementation.md](./08-api-implementation.md) |

## 1. 验收目标

- 前端所需 Phase A 接口全部可访问
- 响应结构统一且带 `data_status`
- 错误响应结构稳定

## 2. 测试范围

- 单元测试：分页参数、错误码、响应包装
- 集成测试：FastAPI TestClient + 临时 DuckDB
- 手动验证：本地请求接口

## 3. 验证清单

| 项 | 方法 | 结果 | 备注 |
|----|------|------|------|
| `GET /market/overview` 返回成功 | 集成测试 | `not_started` |  |
| `GET /stocks` 支持分页排序 | 集成测试 | `not_started` |  |
| `GET /industries` 返回行业排行 | 集成测试 | `not_started` |  |
| `meta.data_status` 存在 | 集成测试 | `not_started` |  |
| 非法参数返回统一错误 | 单元测试 | `not_started` |  |

## 4. 边界场景

- 空结果分页
- size 超过上限
- 库中无快照数据
- 最近快照 stale 或 failed

## 5. 已知问题

- 尚未开始实现与验证

## 6. 剩余风险

- API 契约一旦变动需同步前端类型与文档

## 7. 验收结论

当前未达到交付标准；需完成路由实现和契约测试。
