# 数据源设计文档

> 关联：[ARCHITECTURE.md](./ARCHITECTURE.md) · [FUSION_RECONCILE.md](./FUSION_RECONCILE.md)

---

## 1. 概述

DataAnalysisBase 通过 **Provider Adapter 模式** 接入多个外部数据源。业务层不直接依赖任何具体库，只通过 `ProviderRegistry` 获取 `RawDataset`。

### 1.1 数据源分类

| 类型 | 代表 | 获取方式 | 特点 |
|------|------|----------|------|
| **聚合 API 平台** | Tushare Pro | 调云端 API | 字段规范、有积分门槛、较稳定 |
| **开源抓取库** | AKShare | 本地 Python 请求公开网站 | 免费、面广、偶发失效 |
| **官方披露** | 巨潮资讯 | 爬虫 / API | 公告权威 |
| **国际市场** | yfinance | 本地库 | 港股/美股扩展 |

---

## 2. AKShare

### 2.1 基本信息

| 属性 | 值 |
|------|-----|
| 安装 | `pip install akshare` |
| 费用 | 免费 |
| Token | 不需要 |
| 官网/文档 | https://akshare.akfamily.xyz |

### 2.2 数据实际来源

AKShare 不存储数据，每次调用实时从公开金融网站抓取：

| 上游网站 | 典型用途 |
|----------|----------|
| 东方财富 (eastmoney) | 行情、资金流、板块、多数 `_em` 接口 |
| 新浪财经 (sina) | 行情、财报、`_sina` 接口 |
| 同花顺 | 部分数据 |
| 雪球 | 个股信息 `_xq` 接口 |
| 交易所官网 | 部分基础数据 |

### 2.3 本平台使用的接口映射

| DatasetType | AKShare 函数 | 说明 |
|-------------|--------------|------|
| daily_bars | `stock_zh_a_hist` | 东财日 K |
| valuation | 从实时/历史行情衍生 | PE/PB 等 |
| financials | `stock_financial_report_sina` | 利润表/资产负债表/现金流量表 |
| money_flow | `stock_individual_fund_flow` | 个股资金流 |
| news | `stock_news_em` | 个股新闻 |
| fund_nav | `fund_open_fund_info_em` | 场外基金净值 |
| index | `stock_zh_index_daily` | 指数行情 |

### 2.4 字段映射（→ Canonical）

| Canonical | AKShare 字段 |
|-----------|--------------|
| trade_date | 日期 |
| open | 开盘 |
| high | 最高 |
| low | 最低 |
| close | 收盘 |
| volume | 成交量 |
| amount | 成交额 |

### 2.5 风险与限制

| 风险 | 说明 | 应对 |
|------|------|------|
| 接口变更 | 东财改版导致函数失效 | pin 版本、监控 health_check、本地缓存 |
| IP 封禁 | 高频请求新浪源 | 限流、优先东财源 |
| 数据延迟 | 非交易所直连 | 标注 fetched_at |
| 学术声明 | 仅限研究用途 | 项目免责声明 |

### 2.6 Adapter 实现要点

```python
class AkshareAdapter(DataProvider):
    name = "akshare"
    priority = 2  # 默认低于 tushare（财务类可配置覆盖）

    def fetch(self, dataset_type, security_id, **kwargs) -> RawDataset:
        symbol = to_akshare_symbol(security_id)  # 600519.SH → 600519
        # 调用对应 akshare 函数
        # 包装为 RawDataset，计算 raw_hash
```

---

## 3. Tushare Pro

### 3.1 基本信息

| 属性 | 值 |
|------|-----|
| 安装 | `pip install tushare` |
| 费用 | 免费档 + 积分制 |
| Token | 必须，环境变量 `DAB_TUSHARE_TOKEN` |
| 官网 | https://tushare.pro |

### 3.2 数据实际来源

Tushare 作为数据平台，自行采集、清洗、入库后通过 API 提供。宣称来源包括：

- 沪深交易所
- 上市公司公告
- 指数公司
- 港交所（部分）

用户拿到的是 **已标准化的 API 响应**，不直接接触上游。

### 3.3 本平台使用的接口映射

| DatasetType | Tushare 接口 | 积分参考 |
|-------------|--------------|----------|
| daily_bars | `pro.daily()` | 基础 |
| valuation | `pro.daily_basic()` | 基础 |
| financials | `pro.fina_indicator()` | 2000+ |
| financials | `pro.income/balancesheet/cashflow` | 2000+ |
| money_flow | `pro.moneyflow()` | 2000+ |
| news | `pro.news()` | 有限 |
| index | `pro.index_daily()` | 基础 |
| macro | `pro.cn_gdp/cpi/pmi` | 不等 |

### 3.4 字段映射（→ Canonical）

| Canonical | Tushare 字段 |
|-----------|--------------|
| security_id | ts_code |
| trade_date | trade_date |
| close | close |
| pe_ttm | pe_ttm |
| pb | pb |
| roe | roe |
| revenue | total_revenue (income) |

### 3.5 积分与降级策略

```yaml
# 无积分时的降级行为
tushare:
  on_insufficient_points:
    daily_bars: use_akshare_only
    financials: use_akshare_only
    alert: true
```

### 3.6 Adapter 实现要点

```python
class TushareAdapter(DataProvider):
    name = "tushare"
    priority = 1

    def __init__(self, token: str):
        self.pro = ts.pro_api(token)

    def fetch(self, dataset_type, security_id, **kwargs) -> RawDataset:
        ts_code = security_id  # 已是 600519.SH 格式
        # 调用 pro 接口，处理积分不足异常
```

---

## 4. 巨潮资讯（CninfoAdapter，M4）

### 4.1 用途

- 公告原文（权威）
- 业绩预告、年报 PDF 链接
- RAG 知识库主来源

### 4.2 状态

首期 `enabled: false`，M4 阶段实现。

---

## 5. yfinance（YfinanceAdapter，M6）

### 5.1 用途

- 港股：`00700.HK`
- 美股：`AAPL.US`

### 5.2 状态

首期 `enabled: false`，M6 阶段实现。

---

## 6. ProviderRegistry 设计

### 6.1 注册与路由

```python
class ProviderRegistry:
    def __init__(self, config: ProvidersConfig):
        self.providers = self._load_providers(config)

    def fetch_all(self, dataset_type: DatasetType, security_id: str, **kwargs) -> list[RawDataset]:
        """并行从所有支持该类型的 Provider 拉取"""
        providers = [p for p in self.providers if p.supports(dataset_type)]
        return parallel_fetch(providers, dataset_type, security_id, **kwargs)

    def health_check_all(self) -> dict[str, ProviderHealth]:
        ...
```

### 6.2 并行拉取与错误隔离

```
fetch_all(daily_bars, 600519.SH)
  ├── akshare  → OK  → RawDataset
  └── tushare  → FAIL → 记录错误，不阻断 akshare
```

### 6.3 限流

| Provider | 默认限制 |
|----------|----------|
| akshare | 30 req/min |
| tushare | 按积分档位 |

---

## 7. 代码规范化

### 7.1 各源代码格式

| 源 | 输入示例 | 内部格式 |
|----|----------|----------|
| 用户输入 | `600519` | `600519.SH` |
| AKShare | `600519` | `600519.SH` |
| Tushare | `600519.SH` | `600519.SH` |
| 新浪 | `sh600519` | `600519.SH` |

### 7.2 security_aliases 表

解决同一证券在不同源的代码差异：

```sql
INSERT INTO security_aliases VALUES
  ('akshare', '600519', '600519.SH'),
  ('tushare', '600519.SH', '600519.SH'),
  ('sina', 'sh600519', '600519.SH');
```

---

## 8. 数据源选型建议

| 数据类型 | 主源 | 备源 | 说明 |
|----------|------|------|------|
| 日 K 线 | Tushare | AKShare | 互相校验收盘价 |
| 估值 PE/PB | 双源 median | — | 容忍小差异 |
| 财务指标 | Tushare | AKShare | 有积分时 Tushare 权威 |
| 资金流 | AKShare | Tushare | 东财资金流更及时 |
| 新闻 | AKShare | — | 多源合并去重 |
| 公告 | 巨潮 | AKShare | 后期 RAG 主源 |
| 基金净值 | AKShare | Tushare | — |

---

## 9. 扩展新数据源 Checklist

1. 实现 `DataProvider` 接口
2. 编写 `normalizer` 字段映射
3. 在 `providers.yaml` 注册
4. 在 `fusion_policy.yaml` 配置融合策略
5. 补充单元测试（mock 上游响应）
6. 更新本文档接口映射表

---

*关联配置：[examples/providers.yaml](./examples/providers.yaml)*
