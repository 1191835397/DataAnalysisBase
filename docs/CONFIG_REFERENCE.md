# 配置参考（设计稿）

> 实现阶段将复制到项目根目录 `config/`。关联：[MARKET_SURVEILLANCE.md](./MARKET_SURVEILLANCE.md)

---

## sync_schedule.yaml

```yaml
version: "1.0"
timezone: "Asia/Shanghai"

jobs:
  market_bulk_snapshot:
    description: 全 A 股批量现货快照
    interval_minutes: 30
    trading_sessions:
      - start: "09:30"
        end: "11:30"
      - start: "13:00"
        end: "15:00"
    trading_days_only: true
    on_complete: surveillance_eval

  focus_deep_sync:
    description: 重点股深度同步
    interval_minutes: 5
    trading_sessions:
      - start: "09:30"
        end: "11:30"
      - start: "13:00"
        end: "15:00"
    trading_days_only: true

  eod_daily_bars:
    cron: "35 15 * * 1-5"

  eod_master_data:
    cron: "40 15 * * 1-5"
```

---

## surveillance_rules.yaml

```yaml
version: "1.0"

dedupe:
  window_minutes: 30

rules:
  limit_up:
    scope: market
    severity: high
    condition: { field: change_pct, op: gte, value: 9.9 }
    enabled: true

  limit_down:
    scope: market
    severity: high
    condition: { field: change_pct, op: lte, value: -9.9 }
    enabled: true

  price_spike:
    scope: market
    severity: medium
    condition: { field: delta_price_pct, op: gte, value: 3.0 }
    enabled: true

  volume_surge:
    scope: market
    severity: medium
    condition: { field: volume_ratio, op: gte, value: 2.0 }
    enabled: true

  industry_move:
    scope: industry
    severity: info
    condition: { field: industry_change_pct_avg, op: abs_gte, value: 2.0 }
    enabled: true

  focus_price_drop:
    scope: focus
    severity: medium
    condition: { field: change_pct, op: lte, value: -5.0 }
    enabled: true
```

---

其他配置见 [examples/](./examples/)：`fusion_policy.yaml`、`watchlist.yaml`、`providers.yaml`。
