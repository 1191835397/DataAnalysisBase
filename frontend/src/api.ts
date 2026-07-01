import type {
  IndustryItem,
  MarketAlert,
  MarketAlertGroup,
  MarketSyncHistory,
  MarketOverview,
  MarketSyncJob,
  Page,
  RuntimeStatus,
  AlertStatus,
  StockDetail,
  StockItem,
  StockQuery,
} from "./types";

export type DashboardData = {
  status: RuntimeStatus;
  overview: MarketOverview;
  industries: IndustryItem[];
  stocks: Page<StockItem>;
};

export class SyncConflictError extends Error {
  constructor(
    message: string,
    readonly jobId: string
  ) {
    super(message);
    this.name = "SyncConflictError";
  }
}

export async function loadDashboardData(): Promise<DashboardData> {
  const [status, overview, industries, stocks] = await Promise.all([
    fetchJson<RuntimeStatus>("/api/v1/system/status"),
    fetchJson<MarketOverview>("/api/v1/market/overview"),
    fetchJson<IndustryItem[]>("/api/v1/industries?limit=80"),
    fetchStocksPage({
      page: 1,
      size: 12,
      sort: "change_pct",
      order: "desc",
      filter: "gainers"
    })
  ]);
  return { status, overview, industries, stocks };
}

export function fetchStocksPage(query: StockQuery): Promise<Page<StockItem>> {
  return fetchJson<Page<StockItem>>(`/api/v1/stocks?${buildQuery(query)}`);
}

export function fetchStockDetail(securityId: string, alertLimit = 20): Promise<StockDetail> {
  const params = new URLSearchParams({ alert_limit: String(alertLimit) });
  return fetchJson<StockDetail>(
    `/api/v1/stocks/${encodeURIComponent(securityId)}?${params.toString()}`
  );
}

export function fetchIndustryStocks(
  industryCode: string,
  query: Omit<StockQuery, "industry" | "q">
): Promise<Page<StockItem>> {
  return fetchJson<Page<StockItem>>(
    `/api/v1/industries/${encodeURIComponent(industryCode)}/stocks?${buildQuery(query)}`
  );
}

export function startMarketSync(): Promise<MarketSyncJob> {
  return fetchJson<MarketSyncJob>("/api/v1/sync/market", { method: "POST" });
}

export function fetchMarketSyncJob(jobId: string): Promise<MarketSyncJob> {
  return fetchJson<MarketSyncJob>(`/api/v1/sync/market/${encodeURIComponent(jobId)}`);
}

export function cancelMarketSync(jobId: string): Promise<MarketSyncJob> {
  return fetchJson<MarketSyncJob>(`/api/v1/sync/market/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST"
  });
}

export function fetchLatestMarketSyncJob(): Promise<MarketSyncJob | null> {
  return fetchJsonOrEmpty<MarketSyncJob>("/api/v1/sync/market/latest");
}

export function fetchMarketSyncJobs(limit = 20): Promise<MarketSyncJob[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  return fetchJson<MarketSyncJob[]>(`/api/v1/sync/market/jobs?${params.toString()}`);
}

export function fetchMarketSyncHistory(
  page = 1,
  size = 20,
  recent = 20
): Promise<MarketSyncHistory> {
  const params = new URLSearchParams({
    page: String(page),
    size: String(size),
    recent: String(recent)
  });
  return fetchJson<MarketSyncHistory>(`/api/v1/sync/market/history?${params.toString()}`);
}

export function fetchMarketAlerts(limit = 50): Promise<MarketAlert[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  return fetchJson<MarketAlert[]>(`/api/v1/alerts/market?${params.toString()}`);
}

export function fetchMarketAlertGroups(limit = 50): Promise<MarketAlertGroup[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  return fetchJson<MarketAlertGroup[]>(`/api/v1/alerts/market/groups?${params.toString()}`);
}

export function updateMarketAlertStatus(
  alertId: string,
  status: AlertStatus
): Promise<MarketAlert> {
  return fetchJson<MarketAlert>(`/api/v1/alerts/market/${encodeURIComponent(alertId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status })
  });
}

export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw await responseError(url, response);
  }
  return (await response.json()) as T;
}

async function fetchJsonOrEmpty<T>(url: string, init?: RequestInit): Promise<T | null> {
  const response = await fetch(url, init);
  if (response.status === 204) {
    return null;
  }
  if (!response.ok) {
    throw await responseError(url, response);
  }
  return (await response.json()) as T;
}

async function responseError(url: string, response: Response): Promise<Error> {
  let payload: { detail?: unknown } | null = null;
  try {
    payload = (await response.json()) as { detail?: unknown };
  } catch {
    return new Error(`${url} returned ${response.status}`);
  }
  if (typeof payload.detail === "string") {
    return new Error(payload.detail);
  }
  if (isSyncConflictDetail(payload.detail)) {
    return new SyncConflictError(payload.detail.message, payload.detail.job_id);
  }
  return new Error(`${url} returned ${response.status}`);
}

function isSyncConflictDetail(value: unknown): value is { message: string; job_id: string } {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const detail = value as { message?: unknown; job_id?: unknown };
  return typeof detail.message === "string" && typeof detail.job_id === "string";
}

function buildQuery(query: StockQuery | Omit<StockQuery, "industry" | "q">): string {
  const params = new URLSearchParams();
  params.set("page", String(query.page));
  params.set("size", String(query.size));
  params.set("sort", query.sort);
  params.set("order", query.order);
  if ("q" in query && query.q) {
    params.set("q", query.q);
  }
  if (query.filter) {
    params.set("filter", query.filter);
  }
  if ("industry" in query && query.industry) {
    params.set("industry", query.industry);
  }
  return params.toString();
}
