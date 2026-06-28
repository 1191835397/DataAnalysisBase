import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  ChevronLeft,
  ChevronRight,
  Layers,
  RefreshCw,
  Search
} from "lucide-react";

import { fetchIndustryStocks, fetchStocksPage, loadDashboardData, type DashboardData } from "./api";
import {
  formatAmount,
  dataStatusLabel,
  dataStatusMessage,
  formatDateTime,
  formatInteger,
  formatNumber,
  formatPercent,
  formatSignedPercent,
  latestRunCaption
} from "./format";
import type { DataStatus, Page, SortOrder, StockFilter, StockItem, StockQuery } from "./types";
import "./styles.css";

const navigation = [
  { key: "overview", label: "市场总览", icon: Activity },
  { key: "industries", label: "行业", icon: Layers },
  { key: "stocks", label: "股票", icon: Search },
  { key: "alerts", label: "告警", icon: Bell }
] as const;

const stockFilterOptions: Array<{ value: StockFilter | ""; label: string }> = [
  { value: "", label: "全部" },
  { value: "gainers", label: "上涨" },
  { value: "losers", label: "下跌" },
  { value: "limit_up", label: "涨停" },
  { value: "limit_down", label: "跌停" },
  { value: "volume", label: "放量" }
];

const stockSortOptions = [
  { value: "change_pct", label: "涨跌幅" },
  { value: "amount", label: "成交额" },
  { value: "volume_ratio", label: "量比" },
  { value: "market_cap", label: "总市值" },
  { value: "security_id", label: "代码" }
];

type ActiveView = (typeof navigation)[number]["key"];

function App() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [activeView, setActiveView] = useState<ActiveView>("overview");
  const [selectedIndustry, setSelectedIndustry] = useState<string | null>(null);
  const [industryPage, setIndustryPage] = useState(1);
  const [industryStocks, setIndustryStocks] = useState<Page<StockItem> | null>(null);
  const [isIndustryLoading, setIsIndustryLoading] = useState(false);
  const [industryError, setIndustryError] = useState<string | null>(null);
  const [stockQuery, setStockQuery] = useState<StockQuery>({
    page: 1,
    size: 20,
    sort: "change_pct",
    order: "desc",
    filter: "gainers"
  });
  const [stockSearch, setStockSearch] = useState("");
  const [stockPage, setStockPage] = useState<Page<StockItem> | null>(null);
  const [isStockLoading, setIsStockLoading] = useState(false);
  const [stockError, setStockError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;
    setIsLoading(true);
    setError(null);

    loadDashboardData()
      .then((nextData) => {
        if (isActive) {
          setData(nextData);
          setStockPage(nextData.stocks);
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

  useEffect(() => {
    if (!selectedIndustry) {
      setIndustryStocks(null);
      return;
    }

    let isActive = true;
    setIsIndustryLoading(true);
    setIndustryError(null);

    fetchIndustryStocks(selectedIndustry, {
      page: industryPage,
      size: 12,
      sort: "change_pct",
      order: "desc"
    })
      .then((nextPage) => {
        if (isActive) {
          setIndustryStocks(nextPage);
        }
      })
      .catch((reason: unknown) => {
        if (isActive) {
          setIndustryError(reason instanceof Error ? reason.message : "行业成分股加载失败");
        }
      })
      .finally(() => {
        if (isActive) {
          setIsIndustryLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [selectedIndustry, industryPage, refreshKey]);

  useEffect(() => {
    let isActive = true;
    setIsStockLoading(true);
    setStockError(null);

    fetchStocksPage(stockQuery)
      .then((nextPage) => {
        if (isActive) {
          setStockPage(nextPage);
        }
      })
      .catch((reason: unknown) => {
        if (isActive) {
          setStockError(reason instanceof Error ? reason.message : "股票列表加载失败");
        }
      })
      .finally(() => {
        if (isActive) {
          setIsStockLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [stockQuery, refreshKey]);

  const breadth = useMemo(() => {
    if (!data?.overview.stock_count) {
      return null;
    }
    return data.overview.up_count / data.overview.stock_count;
  }, [data]);

  function selectIndustry(industryCode: string) {
    setSelectedIndustry(industryCode);
    setIndustryPage(1);
  }

  function updateStockQuery(patch: Partial<StockQuery>, resetPage = true) {
    setStockQuery((current) => ({
      ...current,
      ...patch,
      page: resetPage ? 1 : (patch.page ?? current.page)
    }));
  }

  function submitStockSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    updateStockQuery({ q: stockSearch.trim() || undefined });
  }

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
            <RuntimeSummary status={data?.status ?? null} />
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

        <DataHealthNotice status={data?.status ?? null} />
        {error ? <div className="notice error">{error}</div> : null}
        {isLoading ? <div className="notice">加载市场快照...</div> : null}

        {data && activeView === "overview" ? (
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
        ) : null}

        {data && activeView === "industries" ? (
          <>
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
                      <tr
                        className="clickable-row"
                        key={industry.industry_code}
                        aria-selected={selectedIndustry === industry.industry_code}
                        onClick={() => selectIndustry(industry.industry_code)}
                      >
                        <td>{displayIndustry(industry.industry_code)}</td>
                        <td>{formatInteger(industry.stock_count)}</td>
                        <td className={valueClass(industry.change_pct_avg)}>
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

            {selectedIndustry ? (
              <section className="table-panel" aria-label="行业成分股">
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">行业成分股</p>
                    <h2>{displayIndustry(selectedIndustry)}</h2>
                  </div>
                  <span>
                    {industryStocks ? `${formatInteger(industryStocks.total)} 只` : "加载中"}
                  </span>
                </div>
                {industryError ? <div className="inline-notice error">{industryError}</div> : null}
                {isIndustryLoading ? <div className="inline-notice">加载行业成分股...</div> : null}
                {industryStocks ? (
                  <>
                    <StockTable stocks={industryStocks.items} />
                    <Pagination
                      page={industryStocks.page}
                      size={industryStocks.size}
                      total={industryStocks.total}
                      onPageChange={setIndustryPage}
                    />
                  </>
                ) : null}
              </section>
            ) : (
              <section className="empty-panel">
                <p className="eyebrow">行业成分股</p>
                <h2>选择一个行业查看成分股</h2>
                <p>空行业会聚合为 UNKNOWN，便于定位未覆盖的行业映射。</p>
              </section>
            )}
          </>
        ) : null}

        {data && activeView === "stocks" ? (
          <section className="table-panel" aria-label="股票列表">
            <div className="section-heading">
              <div>
                <p className="eyebrow">股票列表</p>
                <h2>全市场筛选</h2>
              </div>
              <span>{stockPage ? `${formatInteger(stockPage.total)} 只` : "加载中"}</span>
            </div>
            <StockControls
              query={stockQuery}
              search={stockSearch}
              onSearchChange={setStockSearch}
              onSearchSubmit={submitStockSearch}
              onQueryChange={updateStockQuery}
            />
            {stockError ? <div className="inline-notice error">{stockError}</div> : null}
            {isStockLoading ? <div className="inline-notice">加载股票列表...</div> : null}
            {stockPage ? (
              <>
                <StockTable stocks={stockPage.items} />
                <Pagination
                  page={stockPage.page}
                  size={stockPage.size}
                  total={stockPage.total}
                  onPageChange={(page) => updateStockQuery({ page }, false)}
                />
              </>
            ) : null}
          </section>
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

function RuntimeSummary({ status }: { status: DashboardData["status"] | null }) {
  if (!status) {
    return <div className="runtime-summary">等待数据状态</div>;
  }
  return (
    <div className="runtime-summary">
      <span>快照 {formatDateTime(status.latest_snapshot_time)}</span>
      <span>{latestRunCaption(status)}</span>
    </div>
  );
}

function DataHealthNotice({ status }: { status: DashboardData["status"] | null }) {
  if (!status || status.data_status === "fresh") {
    return null;
  }
  return (
    <div className={`data-health-notice ${status.data_status}`}>
      <AlertTriangle aria-hidden="true" size={18} />
      <div>
        <strong>{dataStatusLabel(status.data_status)}</strong>
        <span>{dataStatusMessage(status)}</span>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: DataStatus }) {
  return <div className={`status-pill ${status}`}>{dataStatusLabel(status)}</div>;
}

function StockControls({
  query,
  search,
  onSearchChange,
  onSearchSubmit,
  onQueryChange
}: {
  query: StockQuery;
  search: string;
  onSearchChange: (value: string) => void;
  onSearchSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  onQueryChange: (patch: Partial<StockQuery>, resetPage?: boolean) => void;
}) {
  return (
    <div className="controls-bar">
      <form className="search-box" onSubmit={onSearchSubmit}>
        <Search aria-hidden="true" size={16} />
        <input
          aria-label="搜索代码或名称"
          placeholder="代码或名称"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
        />
        <button type="submit">搜索</button>
      </form>
      <label>
        筛选
        <select
          value={query.filter ?? ""}
          onChange={(event) =>
            onQueryChange({ filter: (event.target.value || undefined) as StockFilter | undefined })
          }
        >
          {stockFilterOptions.map((option) => (
            <option key={option.value || "all"} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        排序
        <select value={query.sort} onChange={(event) => onQueryChange({ sort: event.target.value })}>
          {stockSortOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        方向
        <select
          value={query.order}
          onChange={(event) => onQueryChange({ order: event.target.value as SortOrder })}
        >
          <option value="desc">降序</option>
          <option value="asc">升序</option>
        </select>
      </label>
      <label>
        每页
        <select
          value={query.size}
          onChange={(event) => onQueryChange({ size: Number(event.target.value) })}
        >
          {[12, 20, 50, 100].map((size) => (
            <option key={size} value={size}>
              {size}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

function StockTable({ stocks }: { stocks: StockItem[] }) {
  if (stocks.length === 0) {
    return <div className="inline-notice">没有匹配的股票</div>;
  }
  return (
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
          {stocks.map((stock) => (
            <tr key={stock.security_id}>
              <td className="mono">{stock.security_id}</td>
              <td>{stock.name}</td>
              <td>{formatNumber(stock.price)}</td>
              <td className={valueClass(stock.change_pct)}>{formatSignedPercent(stock.change_pct)}</td>
              <td>{formatAmount(stock.amount)}</td>
              <td>{formatNumber(stock.volume_ratio)}</td>
              <td>{displayIndustry(stock.industry_code)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Pagination({
  page,
  size,
  total,
  onPageChange
}: {
  page: number;
  size: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  const maxPage = Math.max(Math.ceil(total / size), 1);
  const start = total === 0 ? 0 : (page - 1) * size + 1;
  const end = Math.min(page * size, total);
  return (
    <div className="pagination">
      <span>
        {formatInteger(start)}-{formatInteger(end)} / {formatInteger(total)}
      </span>
      <div>
        <button
          className="icon-button"
          type="button"
          aria-label="上一页"
          title="上一页"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeft aria-hidden="true" size={17} />
        </button>
        <span>
          {formatInteger(page)} / {formatInteger(maxPage)}
        </span>
        <button
          className="icon-button"
          type="button"
          aria-label="下一页"
          title="下一页"
          disabled={page >= maxPage}
          onClick={() => onPageChange(page + 1)}
        >
          <ChevronRight aria-hidden="true" size={17} />
        </button>
      </div>
    </div>
  );
}

function valueClass(value: number | null): string {
  if (value === null || value === 0) {
    return "";
  }
  return value > 0 ? "up" : "down";
}

function displayIndustry(value: string | null): string {
  return value || "UNKNOWN";
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
