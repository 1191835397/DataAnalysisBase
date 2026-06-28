import type { IndustryItem, MarketOverview, Page, RuntimeStatus, StockItem, StockQuery } from "./types";

export type DashboardData = {
  status: RuntimeStatus;
  overview: MarketOverview;
  industries: IndustryItem[];
  stocks: Page<StockItem>;
};

export async function loadDashboardData(): Promise<DashboardData> {
  const [status, overview, industries, stocks] = await Promise.all([
    fetchJson<RuntimeStatus>("/api/v1/system/status"),
    fetchJson<MarketOverview>("/api/v1/market/overview"),
    fetchJson<IndustryItem[]>("/api/v1/industries?limit=12"),
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

export function fetchIndustryStocks(
  industryCode: string,
  query: Omit<StockQuery, "industry" | "q">
): Promise<Page<StockItem>> {
  return fetchJson<Page<StockItem>>(
    `/api/v1/industries/${encodeURIComponent(industryCode)}/stocks?${buildQuery(query)}`
  );
}

export async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url} returned ${response.status}`);
  }
  return (await response.json()) as T;
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
