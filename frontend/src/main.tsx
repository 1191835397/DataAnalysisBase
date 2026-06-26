import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Activity, BarChart3, Bell, Layers, RefreshCw, Search } from "lucide-react";

import "./styles.css";

type DataStatus = "fresh" | "stale" | "failed" | "offline";

type RuntimeStatus = {
  data_status: DataStatus;
  latest_snapshot_time: string | null;
  last_market_run: {
    status: string;
    actual: number;
    missing: number;
    error: string | null;
  } | null;
};

type MarketOverview = {
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

type StockItem = {
  security_id: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  amount: number | null;
  volume_ratio: number | null;
  industry_code: string | null;
};

type IndustryItem = {
  industry_code: string;
  stock_count: number;
  change_pct_avg: number | null;
  amount_sum: number | null;
  up_count: number;
  down_count: number;
};

type Page<T> = {
  items: T[];
  total: number;
  page: number;
  size: number;
};

type DashboardData = {
  status: RuntimeStatus;
  overview: MarketOverview;
  industries: IndustryItem[];
  stocks: Page<StockItem>;
};

const navigation = [
  { key: "overview", label: "市场总览", icon: Activity },
  { key: "industries", label: "行业", icon: Layers },
  { key: "stocks", label: "股票", icon: Search },
  { key: "alerts", label: "告警", icon: Bell }
] as const;

type ActiveView = (typeof navigation)[number]["key"];

function App() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [activeView, setActiveView] = useState<ActiveView>("overview");

  useEffect(() => {
    let isActive = true;
    setIsLoading(true);
    setError(null);

    loadDashboardData()
      .then((nextData) => {
        if (isActive) {
          setData(nextData);
        }
      })
      .catch((reason: unknown) => {
        if (isActive) {
          setError(reason instanceof Error ? reason.message : "数据加载失败");
        }
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [refreshKey]);

  const breadth = useMemo(() => {
    if (!data?.overview.stock_count) {
      return null;
    }
    return data.overview.up_count / data.overview.stock_count;
  }, [data]);

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <BarChart3 aria-hidden="true" />
          <span>DataAnalysisBase</span>
        </div>
        <nav>
          {navigation.map(({ key, label, icon: Icon }) => (
            <button
              className="nav-item"
              key={key}
              type="button"
              aria-current={activeView === key}
              onClick={() => setActiveView(key)}
            >
              <Icon aria-hidden="true" size={18} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
      </aside>
      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Phase A Live Dashboard</p>
            <h1>A 股全市场智能监管与分析平台</h1>
          </div>
          <div className="topbar-actions">
            <StatusPill status={data?.status.data_status ?? "offline"} />
            <button
              className="icon-button"
              type="button"
              aria-label="刷新数据"
              title="刷新数据"
              onClick={() => setRefreshKey((value) => value + 1)}
            >
              <RefreshCw aria-hidden="true" size={18} />
            </button>
          </div>
        </header>

        {error ? <div className="notice error">{error}</div> : null}
        {isLoading ? <div className="notice">加载市场快照...</div> : null}

        {data && activeView === "overview" ? (
          <>
            <section className="dashboard-grid" aria-label="市场总览">
              <MetricPanel
                label="全市场股票"
                value={formatInteger(data.overview.stock_count)}
                caption={`${formatDateTime(data.overview.snapshot_time)} / ${data.overview.source}`}
              />
              <MetricPanel
                label="上涨家数占比"
                value={breadth === null ? "-" : formatPercent(breadth)}
                caption={`${formatInteger(data.overview.up_count)} 上涨 / ${formatInteger(
                  data.overview.down_count
                )} 下跌 / ${formatInteger(data.overview.flat_count)} 平盘`}
              />
              <MetricPanel
                label="涨跌停"
                value={`${formatInteger(data.overview.limit_up_count)} / ${formatInteger(
                  data.overview.limit_down_count
                )}`}
                caption="涨停 / 跌停"
              />
              <MetricPanel
                label="成交额"
                value={formatAmount(data.overview.total_amount)}
                caption={latestRunCaption(data.status)}
              />
            </section>
          </>
        ) : null}

        {data && activeView === "industries" ? (
          <section className="table-panel" aria-label="行业排行">
            <div className="section-heading">
              <div>
                <p className="eyebrow">行业排行</p>
                <h2>均涨幅居前</h2>
              </div>
              <span>{formatInteger(data.industries.length)} 个行业</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>行业</th>
                    <th>成分股</th>
                    <th>均涨幅</th>
                    <th>上涨</th>
                    <th>下跌</th>
                    <th>成交额</th>
                  </tr>
                </thead>
                <tbody>
                  {data.industries.map((industry) => (
                    <tr key={industry.industry_code}>
                      <td>{industry.industry_code}</td>
                      <td>{formatInteger(industry.stock_count)}</td>
                      <td
                        className={
                          industry.change_pct_avg && industry.change_pct_avg > 0 ? "up" : "down"
                        }
                      >
                        {formatSignedPercent(industry.change_pct_avg)}
                      </td>
                      <td>{formatInteger(industry.up_count)}</td>
                      <td>{formatInteger(industry.down_count)}</td>
                      <td>{formatAmount(industry.amount_sum)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ) : null}

        {data && activeView === "stocks" ? (
          <>
            <section className="table-panel" aria-label="股票列表">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">股票列表</p>
                  <h2>涨幅居前</h2>
                </div>
                <span>{formatInteger(data.stocks.total)} 只</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>代码</th>
                      <th>名称</th>
                      <th>价格</th>
                      <th>涨跌幅</th>
                      <th>成交额</th>
                      <th>量比</th>
                      <th>行业</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.stocks.items.map((stock) => (
                      <tr key={stock.security_id}>
                        <td className="mono">{stock.security_id}</td>
                        <td>{stock.name}</td>
                        <td>{formatNumber(stock.price)}</td>
                        <td className={stock.change_pct && stock.change_pct > 0 ? "up" : "down"}>
                          {formatSignedPercent(stock.change_pct)}
                        </td>
                        <td>{formatAmount(stock.amount)}</td>
                        <td>{formatNumber(stock.volume_ratio)}</td>
                        <td>{stock.industry_code ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        ) : null}

        {data && activeView === "alerts" ? (
          <section className="empty-panel">
            <p className="eyebrow">告警</p>
            <h2>等待 surveillance 模块接入</h2>
            <p>当前阶段先完成真实市场快照、行业排行和股票列表闭环。</p>
          </section>
        ) : null}
      </section>
    </main>
  );
}

function MetricPanel({
  label,
  value,
  caption
}: {
  label: string;
  value: string;
  caption: string;
}) {
  return (
    <article className="metric-panel">
      <span>{label}</span>
      <strong>{value}</strong>
      <p>{caption}</p>
    </article>
  );
}

function StatusPill({ status }: { status: DataStatus }) {
  return <div className={`status-pill ${status}`}>{status}</div>;
}

async function loadDashboardData(): Promise<DashboardData> {
  const [status, overview, industries, stocks] = await Promise.all([
    fetchJson<RuntimeStatus>("/api/v1/system/status"),
    fetchJson<MarketOverview>("/api/v1/market/overview"),
    fetchJson<IndustryItem[]>("/api/v1/industries?limit=12"),
    fetchJson<Page<StockItem>>("/api/v1/stocks?filter=gainers&size=12")
  ]);
  return { status, overview, industries, stocks };
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url} returned ${response.status}`);
  }
  return (await response.json()) as T;
}

function latestRunCaption(status: RuntimeStatus): string {
  if (!status.last_market_run) {
    return "暂无同步运行记录";
  }
  return `最近同步 ${status.last_market_run.status}，实际 ${formatInteger(
    status.last_market_run.actual
  )}，缺失 ${formatInteger(status.last_market_run.missing)}`;
}

function formatInteger(value: number): string {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(value);
}

function formatNumber(value: number | null): string {
  if (value === null) {
    return "-";
  }
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value);
}

function formatPercent(value: number): string {
  return new Intl.NumberFormat("zh-CN", {
    style: "percent",
    maximumFractionDigits: 1
  }).format(value);
}

function formatSignedPercent(value: number | null): string {
  if (value === null) {
    return "-";
  }
  const formatted = new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: 2,
    signDisplay: "always"
  }).format(value);
  return `${formatted}%`;
}

function formatAmount(value: number | null): string {
  if (value === null) {
    return "-";
  }
  if (Math.abs(value) >= 100000000) {
    return `${formatNumber(value / 100000000)} 亿`;
  }
  if (Math.abs(value) >= 10000) {
    return `${formatNumber(value / 10000)} 万`;
  }
  return formatNumber(value);
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "无快照时间";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
