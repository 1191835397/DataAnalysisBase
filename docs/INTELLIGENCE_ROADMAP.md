# 智能化与扩展路线

| 属性 | 值 |
|------|-----|
| 版本 | v0.2.2 |
| 状态 | 设计（增量规划） |
| 目标 | 在 v0.2 骨架之上，把系统从「规则驱动告警」升级为「基线驱动 + LLM 叙事」的智能监管平台 |

> 关联：[DESIGN_REVIEW.md](./DESIGN_REVIEW.md) · [MARKET_SURVEILLANCE.md](./MARKET_SURVEILLANCE.md) · [AGENT_INTELLIGENCE.md](./AGENT_INTELLIGENCE.md) · [ROADMAP.md](./ROADMAP.md)

---

## 1. 设计理念演进

v0.2 当前：全市场靠**固定阈值规则**告警，LLM 只在 FocusLayer 逐只做研报。
本路线推动如下演进：

```text
基线驱动发现异常（统计，便宜，覆盖全市场）
   → 聚类成市场事件（降噪）
   → LLM 做叙事和解读（全局少量调用）
   → 重点股深度归因（FocusLayer 现有能力）
```

核心原则不变（沿用 [AGENT_INTELLIGENCE.md](./AGENT_INTELLIGENCE.md) 铁律）：

- 全市场不逐只 LLM，避免 5000×成本与幻觉
- LLM 不生产数字，只对结构化数据做叙事/解读
- 智能化优先用「便宜的统计」，LLM 用在「全局视角」与「重点股深度」

---

## 2. 智能化升级（最高优先级）

### 2.1 自适应异常检测（替代/补充固定阈值）

**问题**：`change_pct >= 9.9`、`delta_price_pct >= 3%`、`volume_ratio >= 2.0` 这类固定阈值，牛市满屏告警、熊市几乎不触发，且不区分行业波动率差异。

**方案**：在快照衍生层增加**相对基线**的异常分，纯统计、不依赖 LLM。

| 方法 | 计算 | 用途 |
|------|------|------|
| 历史分位 | 当前涨跌幅 / 量比相对自身 N 日分布的分位 | 个股「相对自己」是否异常 |
| 行业相对强弱 | `stock_change_pct - industry_change_pct_avg` | 剥离板块共性，找真异动 |
| Z-score | `(value - rolling_mean) / rolling_std` | 自适应波动率的标准化异常分 |
| 量价背离 | 价创新高但量能萎缩等组合信号 | 复合形态信号 |

**落库建议**：扩展每个快照衍生字段（见 [MARKET_SURVEILLANCE.md](./MARKET_SURVEILLANCE.md) §5.2）：

```text
zscore_change, pct_rank_change_60d,
rel_strength_vs_industry, volume_zscore
```

规则可由「绝对阈值」改为「绝对阈值 OR 相对异常分超限」，告警附带异常分用于解释。

### 2.2 告警聚类 → 市场事件叙事

**问题**：50 条孤立告警（涨停 42、放量 18）信息过载，缺少「今天发生了什么」的视角。

**方案**：

1. 按**行业 / 概念**对同一时段告警聚类
2. 聚类后用**一次** LLM 调用生成板块级叙事

```text
聚类输入：同 snapshot_time 内的 alerts，按 industry_code/concept 分组
LLM 输出：每个显著板块一句话叙事 + 关联标的列表
成本：聚类后 1~3 次 LLM/快照，而非 5000 次
```

新增表（概念）：

```sql
CREATE TABLE market_events (
    id            VARCHAR PRIMARY KEY,
    event_time    TIMESTAMP,
    scope         VARCHAR,        -- industry | concept | market
    scope_key     VARCHAR,        -- 行业码/概念名
    title         VARCHAR,        -- LLM 生成的一句话叙事
    alert_ids     JSON,           -- 关联告警
    member_ids    JSON,           -- 关联标的
    llm_generated BOOLEAN,
    created_at    TIMESTAMP
);
```

### 2.3 每日 / 盘后市场综述（全局 LLM，单次调用）

对**聚合后**的市场总览 + Top 异动 + 行业排行做一次全局综述，而非逐只。

| 项 | 说明 |
|----|------|
| 输入 | `market_overview_snapshots` + Top N 异动 + 行业排行 |
| 频率 | 盘中数次 + 盘后 1 次，每次 1 调用 |
| 输出 | 市场综述文本，落 `daily_briefs` 表，UI 顶部展示 |
| 成本 | 每次几分钱量级，可控 |

### 2.4 自然语言筛选全市场（NL → 受控查询）

让用户输入自然语言（如「今天放量上涨、PE 小于 20 的医药股」），LLM 转为**受控的 filter DSL**（非自由 SQL），后端查 `latest_market_snapshot`。

```text
NL → LLM → { filters: [{field, op, value}], sort, industry } → 后端校验 → 查询
```

约束：

- 字段、算子、范围白名单校验，拒绝非法字段
- 不让 LLM 直接出 SQL，避免注入与幻觉
- 解析失败时回退到普通筛选

### 2.5 相似形态 / 相似标的检索

把个股近 N 日归一化行情向量化，用向量库找「走势相似的股票」或「历史相似形态」。

| 项 | 说明 |
|----|------|
| 向量化 | 近 N 日归一化收益序列 / 形态特征 |
| 存储 | Chroma（已用于新闻 RAG，可复用） |
| 用途 | 个股详情页「相似标的」、形态选股 |

### 2.6 关联与传导分析

| 能力 | 说明 |
|------|------|
| 概念 / 产业链联动 | 同概念、同龙头、供应链上下游关联标的发现 |
| 资金流关联 | 主力 / 北向在关联标的间的协同变动 |
| 基金穿透反查 | 扩展 [FUSION_RECONCILE.md](./FUSION_RECONCILE.md) §8：自选股「被哪些基金重仓/增减持」 |

---

## 3. 产品完善（实用缺口）

| 缺口 | 说明 | 优先级 |
|------|------|--------|
| **持仓 / 组合管理** | 当前只有 watchlist（关注），缺持仓成本、盈亏、仓位占比、行业敞口。让重点股从「我关注」升级为「我持有」，告警有盈亏语境 | 高 |
| **告警生命周期** | 告警增加 已读 / 已处理 / 忽略 / 加自选 状态，支持「上次该告警后该股怎么走」复盘 | 中高 |
| **规则即信号回测** | 把监管规则当信号源做事件回测：「过去一年触发 volume_surge 的股票 5 日后平均表现」，验证规则有效性 | 中 |
| **自定义规则 / 看板 UI** | 界面上配规则、组看板，而非改 YAML | 中 |
| **历史回放时间轴** | 把 PRD 的 replay 模式做成 UI 时间轴，拖动查看任意时刻全市场状态 | 中 |

### 3.1 持仓模型（概念）

```sql
CREATE TABLE positions (
    id            VARCHAR PRIMARY KEY,
    security_id   VARCHAR NOT NULL,
    quantity      DOUBLE,
    avg_cost      DOUBLE,
    opened_at     TIMESTAMP,
    note          TEXT
);
```

衍生：持仓市值、浮动盈亏、行业 / 个股敞口占比，叠加到告警与个股详情。

### 3.2 告警状态扩展

在 `surveillance_alerts` 增加：

```text
status        -- new | read | handled | ignored
handled_at, handled_note
```

---

## 4. 数据正确性（隐藏陷阱，必须明确）

> 这几点不写清楚，实现后会「看起来对、其实错」。处理细节同步补充到 [MARKET_SURVEILLANCE.md](./MARKET_SURVEILLANCE.md) §5.2。

| 陷阱 | 后果 | 处理 |
|------|------|------|
| **除权除息日** | `delta_price_pct` 价格跳水，误报暴跌/跌停 | 趋势 diff 用前复权价，或读除权标记当天跳过价格类规则 |
| **首次快照无 T-1** | `delta_price_pct` 无定义 | 首快照以**昨收**为基准 |
| **停牌 / 新股 / ST** | 误报零变化或异常；涨跌幅规则口径不同 | 规则显式排除停牌；新股/ST 用专属阈值 |
| **交易日历缺失** | 日终任务、节假日判断错乱 | 交易日历列为 Phase A 显式交付物 |
| **全市场无对账** | 全市场数据质量盲区 | 全市场**抽样**交叉校验（随机抽 N 只比对源），作为质量指标，而非逐只对账 |

---

## 5. 工程与可观测

| 点 | 说明 |
|----|------|
| 指标体系 | 同步耗时、成功率、告警量、LLM 调用与成本，落 `/system/status` |
| 配置热加载 | 改规则 / 阈值不重启 |
| 数据导出 / 备份 | DuckDB 定期备份；报告 / 告警导出 CSV |
| 测试夹具 | 固定历史快照做回归，支撑 replay 模式 |

---

## 6. 推荐落地顺序

```text
第一步（性价比最高，纯统计）
  自适应异常检测：行业相对 + 历史分位 + Z-score
        ↓
第二步（全局视角，低成本 LLM）
  告警聚类 → 市场事件叙事 + 每日市场综述
        ↓
第三步（交互智能）
  自然语言筛选全市场（NL → 受控查询）
        ↓
第四步（产品闭环）
  持仓管理 + 告警生命周期 + 规则回测
        ↓
第五步（进阶）
  相似形态检索 + 关联传导分析
```

这些能力对应 [ROADMAP.md](./ROADMAP.md) 的 **Phase F**，建议在 Phase A~D 的全市场底座与重点股能力稳定后启动；其中「数据正确性」（§4）属于**前置必做**，应在 Phase B 监管引擎实现时一并处理。

---

## 7. 边界（仍不做）

延续 [DESIGN_REVIEW.md](./DESIGN_REVIEW.md) 的边界，智能化升级**不改变**以下底线：

- 不做秒级全市场实时行情
- 不对 5000 只股票全量 LLM 研报
- AI 不直接给买卖结论
- LLM 不生产数字，只做叙事与解读
