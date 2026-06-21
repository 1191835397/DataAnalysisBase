# api 模块实施记录

| 属性 | 值 |
|------|-----|
| 模块 | `api` |
| 状态 | `planned` |
| Phase | `A+` |
| 负责人 | `TBD` |
| 最近更新 | `2026-06-22` |
| 关联设计 | [08-api.md](./08-api.md) |

## 1. 当前目标

实现 Phase A 所需 REST 接口：市场总览、股票列表、行业列表、系统状态，并统一响应包装。

## 2. 本次范围

- `main.py`
- `deps.py`
- `envelope.py`
- `routers/market.py`
- `routers/stocks.py`
- `routers/industries.py`
- `routers/health.py`

不包含：

- 告警 WebSocket
- research / portfolio 路由

## 3. 前置依赖

- `storage`
- `observability`
- `config`
- FastAPI

## 4. 实现拆解

1. 初始化 FastAPI 应用和依赖注入
2. 实现统一 `Envelope`
3. 实现市场、股票、行业、系统状态端点
4. 补分页、排序、错误处理测试

## 5. 当前进度

### 已完成

- API 详细设计已完成

### 进行中

- 无

### 未开始

- 路由实现
- 错误处理器
- 契约测试

## 6. 关键决策

| 决策 | 原因 | 影响 |
|------|------|------|
| 所有 GET 返回统一 `Envelope` | 让前端只处理一套契约 | 便于统一 data_status |
| API 仅读聚合表和快照表 | 避免业务逻辑下沉到交付层 | 性能和职责更清晰 |

## 7. 与原设计偏差

当前无实现，暂无偏差。

## 8. 代码位置

- `backend/src/dataanalysisbase/api/`
- `backend/tests/api/`

## 9. 风险与阻塞

- 聚合表口径与分页查询一旦不稳，前端会直接受影响

## 10. 下一步动作

1. 建 FastAPI 应用骨架
2. 先打通 `GET /market/overview`
3. 再补 `stocks`、`industries`、`system/status`
