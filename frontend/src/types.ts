export type DataStatus = "fresh" | "stale" | "partial" | "failed" | "offline";

export type RuntimeStatus = {
  data_status: DataStatus;
  latest_snapshot_time: string | null;
  last_market_run: {
    status: string;
    actual: number;
    missing: number;
    error: string | null;
  } | null;
};

export type RunStatus = "running" | "success" | "partial" | "failed";

export type SyncResult = {
  task: string;
  status: RunStatus;
  expected: number;
  actual: number;
  missing: number;
  snapshot_time: string | null;
  errors: string[];
  logs: SyncLogEntry[];
};

export type SyncLogEntry = {
  at: string;
  stage: string;
  level: string;
  message: string;
  details: Record<string, unknown>;
};

export type MarketSyncJob = {
  job_id: string;
  status: RunStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  result: SyncResult | null;
  error: string | null;
  cancel_requested: boolean;
  elapsed_seconds: number;
  message: string;
  artifact_path: string | null;
};

export type MarketSyncFailureSummary = {
  recent: number;
  total: number;
  failed: number;
  partial: number;
  latest_failed_at: string | null;
};

export type MarketSyncHistory = {
  jobs: Page<MarketSyncJob>;
  failure_summary: MarketSyncFailureSummary;
};

export type AlertSeverity = "high" | "medium" | "info";
export type AlertStatus = "new" | "read" | "handled" | "ignored";

export type MarketAlert = {
  alert_id: string;
  rule_id: string | null;
  severity: AlertSeverity;
  kind:
    | "data_stale"
    | "sync_failed"
    | "partial_sync"
    | "offline"
    | "limit_up"
    | "limit_down"
    | "volume_surge"
    | "extreme_move";
  status: AlertStatus;
  title: string;
  message: string;
  triggered_at: string;
  first_triggered_at: string | null;
  last_triggered_at: string | null;
  trigger_count: number;
  security_id: string | null;
  name: string | null;
  industry_code: string | null;
  metric: string | null;
  value: number | null;
  threshold: number | null;
  snapshot_time: string | null;
};

export type MarketAlertGroup = {
  group_id: string;
  severity: AlertSeverity;
  kinds: MarketAlert["kind"][];
  status: AlertStatus;
  title: string;
  message: string;
  triggered_at: string;
  first_triggered_at: string | null;
  last_triggered_at: string | null;
  alert_count: number;
  security_id: string | null;
  name: string | null;
  industry_code: string | null;
  snapshot_time: string | null;
  alerts: MarketAlert[];
};

export type MarketOverview = {
  snapshot_time: string;
  stock_count: number;
  up_count: number;
  down_count: number;
  flat_count: number;
  limit_up_count: number;
  limit_down_count: number;
  total_amount: number | null;
  source: string;
};

export type StockItem = {
  snapshot_time: string;
  security_id: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  volume: number | null;
  amount: number | null;
  turnover_rate: number | null;
  volume_ratio: number | null;
  pe_ttm: number | null;
  pb: number | null;
  market_cap: number | null;
  industry_code: string | null;
  is_suspended: boolean;
  source: string;
  fetched_at: string;
};

export type StockDetail = {
  snapshot: StockItem;
  alerts: MarketAlert[];
};

export type IndustryItem = {
  industry_code: string;
  stock_count: number;
  change_pct_avg: number | null;
  amount_sum: number | null;
  up_count: number;
  down_count: number;
};

export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  size: number;
};

export type StockFilter = "gainers" | "losers" | "limit_up" | "limit_down" | "volume";

export type SortOrder = "asc" | "desc";

export type StockQuery = {
  page: number;
  size: number;
  sort: string;
  order: SortOrder;
  q?: string;
  filter?: StockFilter;
  industry?: string;
};
