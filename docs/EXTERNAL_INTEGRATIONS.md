# 外部开源集成策略

> 目标：把重型金融分析工具纳入框架能力版图，但不把它们放进主运行链路。默认系统保持轻量、可诊断、可降级；重工具通过可选依赖、隔离模块和 CLI/API 插槽逐步启用。

## 1. 结论

当前项目应立即吸收这些开源项目的能力边界和接口位置，但采用 optional dependency + adapter 的方式接入：

| 层级 | 候选项目 | 当前策略 |
|------|----------|----------|
| 数据源 | AKShare、efinance、Tushare、yfinance | 优先补 `efinance` / Tushare 作为 AKShare 行业和基金数据备用源 |
| 组合绩效 | QuantStats | 等 portfolio 持仓与收益序列稳定后，用于 HTML/Markdown 绩效报告 |
| 组合优化 | PyPortfolioOpt、Riskfolio-Lib | 等持仓、收益矩阵、风险约束落地后接入 |
| 回测 | vectorbt | 等日 K、信号表、规则事件稳定后，用于规则即信号回测 |
| 机器学习研究 | Microsoft Qlib | 放入 research sandbox，不进入主同步/告警链路 |
| 交易引擎 | QuantConnect LEAN | 仅作为外部引擎候选，不进入本项目默认能力 |
| 强化学习 | FinRL | 仅作为实验研究候选，不进入主产品链路 |

## 2. 集成原则

- 主依赖只放平台必需组件；重工具一律放 `optional-dependencies`。
- 第三方库 import 只出现在对应 adapter / engine 模块内，不穿透到 domain、storage、api。
- 不因为工具存在就启用功能；必须有配置、doctor 检查、dry-run plan 和测试。
- 任何回测、优化、研究能力都不输出买卖建议，只输出可解释指标、报告或候选结果。
- 交易执行类能力默认不做；如果未来接 LEAN，也只能作为外部研究/模拟引擎。

## 3. 依赖分组

`backend/pyproject.toml` 已预留可选分组：

```toml
[project.optional-dependencies]
providers = ["akshare", "efinance", "pandas", "tushare"]
backtest = ["vectorbt"]
portfolio = ["PyPortfolioOpt", "quantstats"]
risk = ["Riskfolio-Lib"]
research = ["pyqlib"]
```

这些分组只声明能力边界，不代表当前主流程已经启用。

## 4. 推荐落地顺序

1. `efinance` / Tushare 行业映射备用源  
   目标是生成有效 `data/industry_mapping.csv`，解决当前 AKShare 行业接口返回 0 条的问题。Tushare `stock_basic` adapter 插槽已接入，真实效果需配置 token 后验证；`efinance` 行业映射候选槽位已接入，但 2026-06-27 真实探测显示 `get_realtime_quotes()` 返回字段不包含行业字段，不能直接生成行业映射。

2. QuantStats 报告插槽  
   在 portfolio 模块有持仓和收益序列后，提供 `dab report portfolio` 生成本地报告。

3. vectorbt 规则回测插槽  
   在日 K、信号表和 surveillance 规则事件稳定后，验证规则触发后的历史表现。

4. PyPortfolioOpt / Riskfolio-Lib 组合分析  
   在持仓、收益矩阵和风险指标稳定后，输出组合敞口、风险贡献和优化建议的计算结果。

5. Qlib research sandbox  
   在 canonical 数据和特征表稳定后，把 Qlib 作为独立研究环境接入，不影响主系统同步和告警。

## 5. 当前优先级判断

| 项目 | 当前价值 | 优先级 | 原因 |
|------|----------|--------|------|
| efinance | 数据源备用 | 中 | 可作为行情/基金备用源；已确认实时行情默认字段不含行业字段，不能直接补行业映射 |
| Tushare | 数据源备用/对账 | 高 | 可提供更稳定 A 股基础信息，适合生成行业映射 |
| QuantStats | 绩效报告 | 中 | 需要先有 portfolio 收益序列 |
| PyPortfolioOpt | 组合优化 | 中 | 需要先有持仓和收益矩阵 |
| Riskfolio-Lib | 风险优化 | 中低 | 比 PyPortfolioOpt 更重，适合后续增强 |
| vectorbt | 回测 | 中 | 需要日 K、信号表和规则事件 |
| Qlib | ML 研究平台 | 低到中 | 强大但重，适合隔离 research 模块 |
| LEAN | 交易引擎 | 低 | 项目默认不做自动交易 |
| FinRL | 强化学习研究 | 低 | 容易偏离个人分析助手主目标 |

## 6. 对当前项目的直接动作

- provider 层：已新增 `TushareAdapter.fetch_industry_mapping()` 与 `EfinanceAdapter.fetch_industry_mapping()` 候选槽位，统一写入同一个 `data/industry_mapping.csv` 插槽；`efinance` 目前按可选依赖懒加载，不进入默认主链路，真实响应缺少行业字段时会明确失败。
- observability 层：doctor 检查可选依赖是否安装、功能是否启用、目标文件是否有效。
- delivery 层：所有重功能先提供 dry-run plan，再提供 `--execute`。
- docs 层：每引入一个可选工具，都要记录边界、数据来源、失败降级和验证命令。

## 7. 不做的事

- 不把 Qlib、vectorbt、QuantStats 等重工具加入默认安装。
- 不让回测/优化/强化学习模块参与实时告警主链路。
- 不输出买卖建议、不自动下单、不绕过 provider/storage 边界。
