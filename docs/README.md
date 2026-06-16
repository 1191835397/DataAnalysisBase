# DataAnalysisBase 文档索引

> 多源融合 · 实体中心 · AI 辅助投资研究平台

## 文档列表

| 文档 | 说明 |
|------|------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | **主架构设计文档**（系统全貌、分层设计、数据模型、接口契约） |
| [DATA_SOURCES.md](./DATA_SOURCES.md) | 数据源说明（AKShare / Tushare / 扩展源） |
| [FUSION_RECONCILE.md](./FUSION_RECONCILE.md) | 多源融合与对账引擎设计 |
| [AGENT_INTELLIGENCE.md](./AGENT_INTELLIGENCE.md) | Agent 与 DeepSeek 智能层设计 |
| [ROADMAP.md](./ROADMAP.md) | 分阶段实施路线图与验收标准 |
| [PRODUCT_OUTCOMES.md](./PRODUCT_OUTCOMES.md) | **最终实现效果**：用户可见结果与日常使用方式 |

## 配置示例

| 文件 | 说明 |
|------|------|
| [examples/fusion_policy.yaml](./examples/fusion_policy.yaml) | 融合策略配置 |
| [examples/reconcile_thresholds.yaml](./examples/reconcile_thresholds.yaml) | 对账阈值配置 |
| [examples/watchlist.yaml](./examples/watchlist.yaml) | 自选股表示例 |
| [examples/providers.yaml](./examples/providers.yaml) | 数据源启用与优先级 |

## 快速阅读路径

1. 先读 [ARCHITECTURE.md](./ARCHITECTURE.md) 第一～四章，了解定位与总体架构
2. 读 [DATA_SOURCES.md](./DATA_SOURCES.md) 理解多源边界
3. 读 [FUSION_RECONCILE.md](./FUSION_RECONCILE.md) 理解平台核心差异化
4. 读 [AGENT_INTELLIGENCE.md](./AGENT_INTELLIGENCE.md) 理解 AI 如何接入
5. 读 [ROADMAP.md](./ROADMAP.md) 确定实施顺序
6. 读 [PRODUCT_OUTCOMES.md](./PRODUCT_OUTCOMES.md) 了解做完后能看到什么

## 版本

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1.0 | 2026-06-14 | 初始架构设计 |
