# frontend 模块实施记录

| 属性 | 值 |
|------|-----|
| 模块 | `frontend` |
| 状态 | `in_progress` |
| Phase | `A+` |
| 负责人 | `TBD` |
| 最近更新 | `2026-06-23` |
| 关联设计 | [09-frontend.md](./09-frontend.md) |

## 1. 当前目标

完成 Phase A 的三页前端：市场总览、行业页、股票列表，并落统一顶栏状态展示。

## 2. 本次范围

- React + Vite 工程初始化
- `AppShell`
- `MarketOverviewPage`
- `IndustryPage`
- `StockListPage`
- 基础 API client 与类型

不包含：

- 告警页
- 重点股页
- 个股详情页

## 3. 前置依赖

- `api`
- React 18
- TypeScript
- TanStack Query/Table
- ECharts

## 4. 实现拆解

1. 初始化前端工程与路由
2. 搭 `AppShell` 和状态栏
3. 接市场总览和行业页
4. 接股票列表、分页、排序、筛选
5. 补页面联调与错误态

## 5. 当前进度

### 已完成

- 前端页面设计与交互约束已完成
- 已初始化 `frontend/` Vite + React + TypeScript 工程骨架
- 已创建 Phase A 占位仪表盘、Vite proxy、基础样式
- 已安装 npm 依赖并生成 `package-lock.json`
- 已用 `/api/v1/system/status`、`/api/v1/market/overview`、`/api/v1/stocks` 替换市场总览和股票列表占位数据
- 已用 `/api/v1/industries` 接入行业排行视图
- 已用 `/api/v1/industries/{code}/stocks` 接入行业成分股入口
- `npm.cmd run build` 已通过

### 进行中

- 前端页面与本地后端 dev server 视觉联调

### 未开始

- 真实行业分类数据源接入

## 6. 关键决策

| 决策 | 原因 | 影响 |
|------|------|------|
| 先做三页闭环 | 最快建立“市场可见”体验 | 告警和重点股后置 |
| 强制展示 `data_status` | 避免用户误读旧数据 | 顶栏与 Banner 必须统一 |

## 7. 与原设计偏差

当前无实现，暂无偏差。

## 8. 代码位置

- `frontend/src/`
- `frontend/src/pages/`
- `frontend/src/components/`

## 9. 风险与阻塞

- 如果 API 分页和排序口径不稳定，前端表格体验会反复返工

## 10. 下一步动作

1. 补浏览器截图级视觉验证
2. 补真实行业分类数据源后优化行业页
3. 拆分 `main.tsx` 中的页面、API client 和格式化工具
