# DataAnalysisBase

AI-Native 多源融合投资研究平台（个人版）

- **A 股优先**，可扩展港股 / 美股
- **多源融合**：AKShare + Tushare Pro，差异对账
- **实体中心**：以股票 / 基金 / 上市公司为核心
- **智能分析**：DeepSeek Agent 解读（不生产数字）

## 文档

完整架构设计见 **[docs/](./docs/)** 目录：

| 文档 | 说明 |
|------|------|
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | 主架构设计 |
| [docs/DATA_SOURCES.md](./docs/DATA_SOURCES.md) | 数据源说明 |
| [docs/FUSION_RECONCILE.md](./docs/FUSION_RECONCILE.md) | 融合与对账引擎 |
| [docs/AGENT_INTELLIGENCE.md](./docs/AGENT_INTELLIGENCE.md) | Agent 与 DeepSeek |
| [docs/ROADMAP.md](./docs/ROADMAP.md) | 实施路线图 |
| [docs/PRODUCT_OUTCOMES.md](./docs/PRODUCT_OUTCOMES.md) | 最终实现效果说明 |

## 状态

当前：**架构设计阶段（v0.1.0）**，代码实施尚未开始。

## 快速开始（实施后）

```bash
# 安装
pip install -e .

# 配置
cp .env.example .env
# 编辑 DEEPSEEK_API_KEY, TUSHARE_TOKEN

# 同步与对账
python -m dataanalysisbase.cli sync 600519.SH
python -m dataanalysisbase.cli reconcile 600519.SH
python -m dataanalysisbase.cli research 600519.SH
```

## 免责声明

本系统仅供个人投资研究，输出不构成投资建议。数据来源于第三方接口，请遵守相关使用条款。
