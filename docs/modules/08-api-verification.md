# api 模块验证记录

| 属性 | 值 |
|------|-----|
| 模块 | `api` |
| 验证状态 | `partial` |
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
| `GET /api/v1/market/overview` 返回成功 | 集成测试 | `passed` | FastAPI TestClient + 临时 DuckDB 聚合表 |
| `GET /api/v1/stocks` 支持分页筛选 | 集成测试 | `passed` | 覆盖 `filter=gainers`、分页字段和股票行 |
| `GET /api/v1/industries` 返回行业排行 | 集成测试 + 真实库检查 | `passed` | 临时 DuckDB 覆盖；真实库当前返回 `UNKNOWN` 聚合 |
| `GET /api/v1/industries/{code}/stocks` 返回行业成分股 | 集成测试 + 真实库检查 | `passed` | 覆盖 `TEST` 与 `UNKNOWN`；真实库 `UNKNOWN` 返回 5367 条 |
| `/api/v1/system/status` 支持 provider 状态 | 集成测试 | `passed` | 覆盖默认状态和 `online=true` |
| 数据库不可用时返回稳定错误 | 集成测试 | `passed` | `/api/v1/stocks` 返回 503 |
| `meta.data_status` 存在 | 集成测试 | `not_started` | 统一 Envelope 尚未落地 |
| 非法参数返回统一错误 | 单元测试 | `not_started` | 统一错误处理器尚未落地 |

## 4. 边界场景

- 空结果分页
- size 超过上限
- 库中无快照数据
- 最近快照 stale 或 failed

## 5. 已知问题

- 统一 Envelope 与统一错误处理器尚未完成
- 当前真实 AKShare 快照的行业字段为空，行业排行只有 `UNKNOWN` 聚合，需要补行业分类数据源

## 6. 剩余风险

- API 契约一旦变动需同步前端类型与文档

## 7. 验收结论

当前已完成系统状态、市场总览、股票分页列表、行业排行和行业成分股的最小 API 验证；Phase A API 完整交付仍需补行业分类数据源、统一 Envelope 和错误处理器。
