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
  amount: number | null;
  volume_ratio: number | null;
  industry_code: string | null;
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
