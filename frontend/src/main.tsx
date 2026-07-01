import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  ChevronLeft,
  ChevronRight,
  DatabaseZap,
  Layers,
  RefreshCw,
  Search
} from "lucide-react";

import {
  cancelMarketSync,
  fetchMarketAlertGroups,
  fetchMarketSyncHistory,
  fetchMarketSyncJob,
  fetchLatestMarketSyncJob,
  fetchIndustryStocks,
  fetchStockDetail,
  fetchStocksPage,
  loadDashboardData,
  startMarketSync,
  SyncConflictError,
  updateMarketAlertStatus,
  type DashboardData
} from "./api";
import {
  formatAmount,
  dataStatusLabel,
  dataStatusMessage,
  formatDateTime,
  formatDuration,
  formatInteger,
  formatNumber,
  formatPercent,
  formatSignedPercent,
  latestRunCaption,
  syncResultCaption
} from "./format";
import type {
  DataStatus,
  AlertStatus,
  IndustryItem,
  MarketAlert,
  MarketAlertGroup,
  MarketSyncFailureSummary,
  MarketSyncJob,
  Page,
  SortOrder,
  StockDetail,
  StockFilter,
  StockItem,
  StockQuery,
} from "./types";
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
type AlertSeverityFilter = MarketAlert["severity"] | "all";
type AlertKindFilter = MarketAlert["kind"] | "system" | "all";
type AlertStatusFilter = AlertStatus | "all";

const alertSeverityOptions: Array<{ value: AlertSeverityFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "high", label: "高" },
  { value: "medium", label: "中" },
  { value: "info", label: "信息" }
];

const alertKindOptions: Array<{ value: AlertKindFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "system", label: "系统" },
  { value: "limit_up", label: "涨停" },
  { value: "limit_down", label: "跌停" },
  { value: "volume_surge", label: "放量" },
  { value: "extreme_move", label: "异常涨跌幅" }
];

const alertStatusOptions: Array<{ value: AlertStatusFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "new", label: "新告警" },
  { value: "read", label: "已读" },
  { value: "handled", label: "已处理" },
  { value: "ignored", label: "忽略" }
];

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
  const [selectedStockId, setSelectedStockId] = useState<string | null>(null);
  const [stockDetail, setStockDetail] = useState<StockDetail | null>(null);
  const [isStockDetailLoading, setIsStockDetailLoading] = useState(false);
  const [stockDetailError, setStockDetailError] = useState<string | null>(null);
  const [syncJob, setSyncJob] = useState<MarketSyncJob | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [syncMessageTone, setSyncMessageTone] = useState<"success" | "error" | "info">("info");
  const [syncTicker, setSyncTicker] = useState(0);
  const [isCancellingSync, setIsCancellingSync] = useState(false);
  const [syncJobs, setSyncJobs] = useState<MarketSyncJob[]>([]);
  const [syncHistoryPage, setSyncHistoryPage] = useState(1);
  const [syncHistoryTotal, setSyncHistoryTotal] = useState(0);
  const [syncFailureSummary, setSyncFailureSummary] = useState<MarketSyncFailureSummary | null>(null);
  const [isSyncHistoryLoading, setIsSyncHistoryLoading] = useState(false);
  const [syncHistoryError, setSyncHistoryError] = useState<string | null>(null);
  const [syncHistoryKey, setSyncHistoryKey] = useState(0);
  const [alertGroups, setAlertGroups] = useState<MarketAlertGroup[]>([]);
  const [isAlertsLoading, setIsAlertsLoading] = useState(false);
  const [alertsError, setAlertsError] = useState<string | null>(null);
  const [alertsKey, setAlertsKey] = useState(0);
  const isSyncing = syncJob?.status === "running";

  useEffect(() => {
    let isActive = true;
    fetchLatestMarketSyncJob()
      .then((job) => {
        if (!isActive || !job) {
          return;
        }
        setSyncJob(job);
        if (job.status === "running") {
          setSyncMessageTone("info");
          setSyncMessage("检测到后台市场同步正在执行...");
          return;
        }
        handleCompletedSyncJob(job, { refresh: false });
      })
      .catch((reason: unknown) => {
        if (isActive) {
          setSyncMessageTone("error");
          setSyncMessage(reason instanceof Error ? reason.message : "最近同步任务加载失败");
        }
      });

    return () => {
      isActive = false;
    };
  }, []);

  useEffect(() => {
    let isActive = true;
    setIsSyncHistoryLoading(true);
    setSyncHistoryError(null);

    fetchMarketSyncHistory(syncHistoryPage, 10, 20)
      .then((history) => {
        if (isActive) {
          setSyncJobs(history.jobs.items);
          setSyncHistoryTotal(history.jobs.total);
          setSyncFailureSummary(history.failure_summary);
        }
      })
      .catch((reason: unknown) => {
        if (isActive) {
          setSyncHistoryError(reason instanceof Error ? reason.message : "同步历史加载失败");
        }
      })
      .finally(() => {
        if (isActive) {
          setIsSyncHistoryLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [syncHistoryKey, syncHistoryPage]);

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
    let isActive = true;
    setIsAlertsLoading(true);
    setAlertsError(null);

    fetchMarketAlertGroups(50)
      .then((items) => {
        if (isActive) {
          setAlertGroups(items);
        }
      })
      .catch((reason: unknown) => {
        if (isActive) {
          setAlertsError(reason instanceof Error ? reason.message : "告警加载失败");
        }
      })
      .finally(() => {
        if (isActive) {
          setIsAlertsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [alertsKey]);

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

  useEffect(() => {
    if (!selectedStockId) {
      setStockDetail(null);
      setStockDetailError(null);
      return;
    }

    let isActive = true;
    setIsStockDetailLoading(true);
    setStockDetailError(null);

    fetchStockDetail(selectedStockId, 20)
      .then((detail) => {
        if (isActive) {
          setStockDetail(detail);
        }
      })
      .catch((reason: unknown) => {
        if (isActive) {
          setStockDetail(null);
          setStockDetailError(reason instanceof Error ? reason.message : "股票详情加载失败");
        }
      })
      .finally(() => {
        if (isActive) {
          setIsStockDetailLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [selectedStockId, refreshKey, alertsKey]);

  useEffect(() => {
    if (!syncJob || syncJob.status !== "running") {
      return;
    }

    let isActive = true;
    const poll = () => {
      fetchMarketSyncJob(syncJob.job_id)
        .then((nextJob) => {
          if (!isActive) {
            return;
          }
          setSyncJob(nextJob);
          setSyncJobs((jobs) =>
            [nextJob, ...jobs.filter((item) => item.job_id !== nextJob.job_id)].slice(0, 20)
          );
          if (nextJob.status === "running") {
            setSyncMessage(runningSyncMessage(nextJob));
            setSyncMessageTone(nextJob.cancel_requested || nextJob.elapsed_seconds >= 180 ? "error" : "info");
            return;
          }
          handleCompletedSyncJob(nextJob);
        })
        .catch((reason: unknown) => {
          if (isActive) {
            setSyncJob(null);
            setSyncMessageTone("error");
            setSyncMessage(reason instanceof Error ? reason.message : "同步状态查询失败");
          }
        });
    };
    const intervalId = window.setInterval(poll, 2500);
    poll();

    return () => {
      isActive = false;
      window.clearInterval(intervalId);
    };
  }, [syncJob?.job_id, syncJob?.status]);

  useEffect(() => {
    if (!isSyncing) {
      return;
    }
    const intervalId = window.setInterval(() => {
      setSyncTicker((value) => value + 1);
    }, 1000);
    return () => {
      window.clearInterval(intervalId);
    };
  }, [isSyncing]);

  useEffect(() => {
    if (!syncJob || syncJob.status !== "running") {
      return;
    }
    setSyncMessage(runningSyncMessage(syncJob));
    setSyncMessageTone(
      syncJob.cancel_requested || syncElapsedSeconds(syncJob) >= 180 ? "error" : "info"
    );
  }, [syncJob?.job_id, syncJob?.status, syncJob?.elapsed_seconds, syncTicker]);

  const breadth = useMemo(() => {
    if (!data?.overview.stock_count) {
      return null;
    }
    return data.overview.up_count / data.overview.stock_count;
  }, [data]);
  const industryCoverage = useMemo(() => {
    if (!data?.industries.length) {
      return null;
    }
    return buildIndustryCoverage(data.industries);
  }, [data]);

  function selectIndustry(industryCode: string) {
    setSelectedIndustry(industryCode);
    setIndustryPage(1);
  }

  function focusIndustry(industryCode: string) {
    setActiveView("industries");
    selectIndustry(industryCode);
  }

  function selectStock(securityId: string) {
    setSelectedStockId(securityId);
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

  function refreshDashboard() {
    setRefreshKey((value) => value + 1);
    setAlertsKey((value) => value + 1);
  }

  function refreshSyncHistory() {
    setSyncHistoryPage(1);
    setSyncHistoryKey((value) => value + 1);
  }

  function handleStartMarketSync() {
    startSyncJob();
  }

  function startSyncJob(message?: string) {
    setSyncMessage(null);
    setSyncMessageTone("info");
    if (message) {
      setSyncMessage(message);
    }

    startMarketSync()
      .then((job) => {
        setSyncJob(job);
        setSyncJobs((jobs) => [job, ...jobs.filter((item) => item.job_id !== job.job_id)].slice(0, 20));
        setSyncMessage(runningSyncMessage(job));
        refreshSyncHistory();
      })
      .catch((reason: unknown) => {
        if (reason instanceof SyncConflictError) {
          setSyncJob({
            job_id: reason.jobId,
            status: "running",
            created_at: new Date().toISOString(),
            started_at: null,
            finished_at: null,
            result: null,
            error: null,
            cancel_requested: false,
            elapsed_seconds: 0,
            message: "正在抓取 AKShare 全市场快照",
            artifact_path: null
          });
          setSyncMessageTone("info");
          setSyncMessage("已有市场同步正在后台执行...");
          refreshSyncHistory();
          return;
        }
        setSyncMessageTone("error");
        setSyncMessage(reason instanceof Error ? reason.message : "市场同步失败");
      });
  }

  function handleRetryMarketSync(job: MarketSyncJob) {
    if (isSyncing) {
      return;
    }
    startSyncJob(`正在重新执行同步任务，来源 ${job.job_id.slice(0, 8)}`);
  }

  function handleSelectAlert(group: MarketAlertGroup) {
    if (!group.security_id) {
      return;
    }
    setActiveView("stocks");
    selectStock(group.security_id);
    setStockSearch(group.security_id);
    updateStockQuery({ q: group.security_id, filter: undefined });
  }

  function handleUpdateAlertStatus(alertIds: string[], status: AlertStatus) {
    const uniqueAlertIds = Array.from(new Set(alertIds));
    if (uniqueAlertIds.length === 0) {
      return;
    }
    setAlertsError(null);
    Promise.all(uniqueAlertIds.map((alertId) => updateMarketAlertStatus(alertId, status)))
      .then(() => {
        setAlertsKey((value) => value + 1);
      })
      .catch((reason: unknown) => {
        setAlertsError(reason instanceof Error ? reason.message : "告警状态更新失败");
      });
  }

  function handleCancelMarketSync() {
    if (!syncJob || syncJob.status !== "running") {
      return;
    }
    setIsCancellingSync(true);
    cancelMarketSync(syncJob.job_id)
      .then((job) => {
        setSyncJob(job);
        setSyncJobs((jobs) =>
          jobs.map((item) => (item.job_id === job.job_id ? job : item))
        );
        setSyncMessageTone("error");
        setSyncMessage(runningSyncMessage(job));
        refreshSyncHistory();
      })
      .catch((reason: unknown) => {
        setSyncMessageTone("error");
        setSyncMessage(reason instanceof Error ? reason.message : "取消同步失败");
      })
      .finally(() => {
        setIsCancellingSync(false);
      });
  }

  function handleCompletedSyncJob(job: MarketSyncJob, options: { refresh: boolean } = { refresh: true }) {
    setSyncJobs((jobs) => [job, ...jobs.filter((item) => item.job_id !== job.job_id)].slice(0, 20));
    if (job.result) {
      setSyncMessageTone(job.result.status === "success" ? "success" : "error");
      setSyncMessage(`${syncResultCaption(job.result)}，耗时 ${formatDuration(job.elapsed_seconds)}`);
    } else {
      setSyncMessageTone("error");
      setSyncMessage(job.error || "市场同步失败");
    }
    if (options.refresh) {
      refreshDashboard();
      refreshSyncHistory();
    }
  }

  function runningSyncMessage(job: MarketSyncJob): string {
    return `${job.message}，已耗时 ${formatDuration(syncElapsedSeconds(job))}`;
  }

  function syncElapsedSeconds(job: MarketSyncJob): number {
    if (job.status !== "running") {
      return job.elapsed_seconds;
    }
    const createdAt = new Date(job.created_at).getTime();
    if (Number.isNaN(createdAt)) {
      return job.elapsed_seconds;
    }
    return Math.max(Math.floor((Date.now() - createdAt) / 1000), job.elapsed_seconds);
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
              className="sync-button"
              type="button"
              disabled={isSyncing}
              onClick={handleStartMarketSync}
            >
              <DatabaseZap aria-hidden="true" size={17} />
              <span>{isSyncing ? "同步中" : "同步"}</span>
            </button>
            {isSyncing ? (
              <button
                className="cancel-button"
                type="button"
                disabled={isCancellingSync || syncJob?.cancel_requested}
                onClick={handleCancelMarketSync}
              >
                取消
              </button>
            ) : null}
            <button
              className={`icon-button ${isLoading ? "is-spinning" : ""}`}
              type="button"
              aria-label="刷新数据"
              title="刷新数据"
              disabled={isLoading || isSyncing}
              onClick={refreshDashboard}
            >
              <RefreshCw aria-hidden="true" size={18} />
            </button>
          </div>
        </header>

        <DataHealthNotice status={data?.status ?? null} />
        {error ? <div className="notice error">{error}</div> : null}
        {syncMessage ? (
          <div className={`notice ${syncMessageTone === "info" ? "" : syncMessageTone}`}>
            {syncMessage}
          </div>
        ) : null}
        {isSyncing ? <div className="notice">正在同步全市场快照...</div> : null}
        {isLoading ? <div className="notice">加载市场快照...</div> : null}
        <SyncHistoryPanel
          jobs={syncJobs}
          page={syncHistoryPage}
          size={10}
          total={syncHistoryTotal}
          failureSummary={syncFailureSummary}
          isLoading={isSyncHistoryLoading}
          error={syncHistoryError}
          isRetryDisabled={isSyncing}
          onPageChange={setSyncHistoryPage}
          onRetry={handleRetryMarketSync}
        />

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
            {industryCoverage ? (
              <>
                <section className="dashboard-grid industry-summary" aria-label="行业覆盖概览">
                  <MetricPanel
                    label="已识别行业"
                    value={formatInteger(industryCoverage.knownIndustryCount)}
                    caption={`${formatInteger(industryCoverage.knownStockCount)} 只有行业归属`}
                  />
                  <MetricPanel
                    label="UNKNOWN 占比"
                    value={formatPercent(industryCoverage.unknownRatio)}
                    caption={`${formatInteger(industryCoverage.unknownStockCount)} / ${formatInteger(
                      industryCoverage.totalStockCount
                    )} 未归类`}
                  />
                  <MetricPanel
                    label="行业上涨占比"
                    value={formatPercent(industryCoverage.upRatio)}
                    caption={`${formatInteger(industryCoverage.upCount)} 上涨 / ${formatInteger(
                      industryCoverage.downCount
                    )} 下跌`}
                  />
                  <MetricPanel
                    label="已归类成交额"
                    value={formatAmount(industryCoverage.knownAmount)}
                    caption={`全市场 ${formatAmount(industryCoverage.totalAmount)}`}
                  />
                </section>
                {industryCoverage.unknownRatio > 0.2 ? (
                  <div className="notice industry-warning">
                    行业映射覆盖不足，UNKNOWN 占比 {formatPercent(industryCoverage.unknownRatio)}。
                    当前热力图仍可用于检查已归类样本，但不能代表全市场行业分布。
                  </div>
                ) : null}
                <IndustryHeatmap
                  industries={data.industries}
                  selectedIndustry={selectedIndustry}
                  onSelectIndustry={selectIndustry}
                />
              </>
            ) : null}
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
                    <StockTable
                      stocks={industryStocks.items}
                      selectedStockId={selectedStockId}
                      onSelectStock={selectStock}
                    />
                    <Pagination
                      page={industryStocks.page}
                      size={industryStocks.size}
                      total={industryStocks.total}
                      onPageChange={setIndustryPage}
                    />
                    <StockDetailPanel
                      detail={stockDetail}
                      selectedStockId={selectedStockId}
                      isLoading={isStockDetailLoading}
                      error={stockDetailError}
                      onSelectIndustry={focusIndustry}
                      onUpdateAlertStatus={handleUpdateAlertStatus}
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
                <StockTable
                  stocks={stockPage.items}
                  selectedStockId={selectedStockId}
                  onSelectStock={selectStock}
                />
                <Pagination
                  page={stockPage.page}
                  size={stockPage.size}
                  total={stockPage.total}
                  onPageChange={(page) => updateStockQuery({ page }, false)}
                />
                <StockDetailPanel
                  detail={stockDetail}
                  selectedStockId={selectedStockId}
                  isLoading={isStockDetailLoading}
                  error={stockDetailError}
                  onSelectIndustry={focusIndustry}
                  onUpdateAlertStatus={handleUpdateAlertStatus}
                />
              </>
            ) : null}
          </section>
        ) : null}

        {activeView === "alerts" ? (
          <AlertPanel
            groups={alertGroups}
            isLoading={isAlertsLoading}
            error={alertsError}
            onSelectAlert={handleSelectAlert}
            onUpdateAlertStatus={handleUpdateAlertStatus}
          />
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

type IndustryCoverage = {
  totalStockCount: number;
  knownStockCount: number;
  unknownStockCount: number;
  knownIndustryCount: number;
  totalAmount: number | null;
  knownAmount: number | null;
  upCount: number;
  downCount: number;
  unknownRatio: number;
  upRatio: number;
};

function IndustryHeatmap({
  industries,
  selectedIndustry,
  onSelectIndustry
}: {
  industries: IndustryItem[];
  selectedIndustry: string | null;
  onSelectIndustry: (industryCode: string) => void;
}) {
  const sortedIndustries = [...industries].sort(
    (left, right) => Math.abs(right.change_pct_avg ?? 0) - Math.abs(left.change_pct_avg ?? 0)
  );
  const maxAmount = Math.max(...industries.map((industry) => industry.amount_sum ?? 0), 0);

  return (
    <section className="table-panel industry-heatmap-panel" aria-label="行业热力图">
      <div className="section-heading">
        <div>
          <p className="eyebrow">行业热力</p>
          <h2>涨跌幅与成交额分布</h2>
        </div>
        <span>{formatInteger(sortedIndustries.length)} 个行业</span>
      </div>
      <div className="industry-heatmap">
        {sortedIndustries.map((industry) => (
          <button
            className={`industry-tile ${heatClass(industry.change_pct_avg)}`}
            key={industry.industry_code}
            type="button"
            aria-pressed={selectedIndustry === industry.industry_code}
            onClick={() => onSelectIndustry(industry.industry_code)}
          >
            <span>{displayIndustry(industry.industry_code)}</span>
            <strong>{formatSignedPercent(industry.change_pct_avg)}</strong>
            <em>{formatInteger(industry.stock_count)} 只</em>
            <div className="heat-volume-track" aria-hidden="true">
              <div
                className="heat-volume-bar"
                style={{ width: `${heatAmountWidth(industry.amount_sum, maxAmount)}%` }}
              />
            </div>
          </button>
        ))}
      </div>
    </section>
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

function SyncHistoryPanel({
  jobs,
  page,
  size,
  total,
  failureSummary,
  isLoading,
  error,
  isRetryDisabled,
  onPageChange,
  onRetry
}: {
  jobs: MarketSyncJob[];
  page: number;
  size: number;
  total: number;
  failureSummary: MarketSyncFailureSummary | null;
  isLoading: boolean;
  error: string | null;
  isRetryDisabled: boolean;
  onPageChange: (page: number) => void;
  onRetry: (job: MarketSyncJob) => void;
}) {
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const selectedJob = jobs.find((job) => job.job_id === selectedJobId) ?? jobs[0] ?? null;

  return (
    <section className="table-panel sync-history-panel" aria-label="同步历史">
      <div className="section-heading">
        <div>
          <p className="eyebrow">同步历史</p>
          <h2>最近同步任务</h2>
        </div>
        <span>{isLoading ? "加载中" : `${formatInteger(total)} 条`}</span>
      </div>
      {failureSummary ? <SyncFailureSummary summary={failureSummary} /> : null}
      {error ? <div className="inline-notice error">{error}</div> : null}
      {jobs.length === 0 && !isLoading ? <div className="inline-notice">暂无同步历史</div> : null}
      {jobs.length > 0 ? (
        <div className="table-wrap">
          <table className="sync-history-table">
            <thead>
              <tr>
                <th>任务</th>
                <th>状态</th>
                <th>开始</th>
                <th>耗时</th>
                <th>数量</th>
                <th>取消</th>
                <th>信息</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr
                  className="clickable-row"
                  key={job.job_id}
                  aria-selected={selectedJob?.job_id === job.job_id}
                  onClick={() => setSelectedJobId(job.job_id)}
                >
                  <td className="mono">{job.job_id.slice(0, 8)}</td>
                  <td>
                    <span className={`sync-status ${job.status}`}>{syncStatusLabel(job)}</span>
                  </td>
                  <td>{formatDateTime(job.started_at ?? job.created_at)}</td>
                  <td>{formatDuration(syncElapsedSecondsForDisplay(job))}</td>
                  <td>{syncJobResultSummary(job)}</td>
                  <td>{job.cancel_requested ? "是" : "否"}</td>
                  <td title={job.error ?? job.message}>{syncJobMessage(job)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {total > 0 ? (
        <Pagination page={page} size={size} total={total} onPageChange={onPageChange} />
      ) : null}
      {selectedJob ? (
        <SyncJobDetail
          job={selectedJob}
          isRetryDisabled={isRetryDisabled}
          onRetry={() => onRetry(selectedJob)}
        />
      ) : null}
    </section>
  );
}

function SyncFailureSummary({ summary }: { summary: MarketSyncFailureSummary }) {
  return (
    <div className="sync-failure-summary">
      <DetailItem label={`最近 ${formatInteger(summary.recent)} 次`} value={formatInteger(summary.total)} />
      <DetailItem label="失败" value={formatInteger(summary.failed)} />
      <DetailItem label="部分同步" value={formatInteger(summary.partial)} />
      <DetailItem label="最近失败" value={formatDateTime(summary.latest_failed_at)} />
    </div>
  );
}

function SyncJobDetail({
  job,
  isRetryDisabled,
  onRetry
}: {
  job: MarketSyncJob;
  isRetryDisabled: boolean;
  onRetry: () => void;
}) {
  const canRetry = job.status !== "running" && !isRetryDisabled;
  return (
    <div className="sync-job-detail">
      <div className="sync-job-detail-header">
        <div>
          <p className="eyebrow">任务详情</p>
          <h3 className="mono">{job.job_id}</h3>
        </div>
        <button
          className="retry-button"
          type="button"
          disabled={!canRetry}
          onClick={onRetry}
        >
          重新同步
        </button>
      </div>
      <div className="sync-job-detail-grid">
        <DetailItem label="状态" value={syncStatusLabel(job)} />
        <DetailItem label="创建" value={formatDateTime(job.created_at)} />
        <DetailItem label="开始" value={formatDateTime(job.started_at)} />
        <DetailItem label="结束" value={formatDateTime(job.finished_at)} />
        <DetailItem label="耗时" value={formatDuration(syncElapsedSecondsForDisplay(job))} />
        <DetailItem label="取消请求" value={job.cancel_requested ? "是" : "否"} />
        <DetailItem label="实际 / 预期" value={syncJobResultSummary(job)} />
        <DetailItem label="缺失" value={job.result ? formatInteger(job.result.missing) : "-"} />
        <DetailItem label="快照" value={formatDateTime(job.result?.snapshot_time ?? null)} />
        <DetailItem label="任务状态" value={job.result ? runStatusLabel(job.result.status) : "-"} />
        <DetailItem label="Artifact" value={job.artifact_path ? artifactFileName(job.artifact_path) : "-"} />
      </div>
      {job.artifact_path ? (
        <div className="sync-job-detail-message">
          <strong>Artifact 路径</strong>
          <span>{job.artifact_path}</span>
        </div>
      ) : null}
      <div className="sync-job-detail-message">
        <strong>{job.error ? "错误" : "信息"}</strong>
        <span>{syncJobDetailMessage(job)}</span>
      </div>
      {job.result?.logs.length ? <SyncJobLogList logs={job.result.logs} /> : null}
    </div>
  );
}

function SyncJobLogList({ logs }: { logs: NonNullable<MarketSyncJob["result"]>["logs"] }) {
  return (
    <div className="sync-job-log-list">
      <strong>运行日志</strong>
      <div>
        {logs.map((entry, index) => (
          <div className="sync-job-log-entry" key={`${entry.stage}-${entry.at}-${index}`}>
            <span className={`sync-log-level ${entry.level}`}>{syncLogLevelLabel(entry.level)}</span>
            <span>{formatDateTime(entry.at)}</span>
            <span>{syncStageLabel(entry.stage)}</span>
            <p>{entry.message}</p>
            {Object.keys(entry.details).length ? (
              <code>{formatSyncLogDetails(entry.details)}</code>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="detail-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function syncStatusLabel(job: MarketSyncJob): string {
  if (job.cancel_requested && job.status !== "running") {
    return "已取消";
  }
  return runStatusLabel(job.status);
}

function runStatusLabel(status: MarketSyncJob["status"]): string {
  const labels: Record<MarketSyncJob["status"], string> = {
    running: "运行中",
    success: "成功",
    partial: "部分",
    failed: "失败"
  };
  return labels[status];
}

function syncJobResultSummary(job: MarketSyncJob): string {
  if (!job.result) {
    return "-";
  }
  return `${formatInteger(job.result.actual)} / ${formatInteger(job.result.expected)}`;
}

function syncJobMessage(job: MarketSyncJob): string {
  if (job.error) {
    return job.error;
  }
  if (job.result) {
    return `缺失 ${formatInteger(job.result.missing)}`;
  }
  return job.message;
}

function syncJobDetailMessage(job: MarketSyncJob): string {
  if (job.error) {
    return job.error;
  }
  if (job.result?.errors.length) {
    return job.result.errors.join("；");
  }
  return job.message;
}

function syncLogLevelLabel(level: string): string {
  const labels: Record<string, string> = {
    info: "信息",
    warning: "警告",
    error: "错误"
  };
  return labels[level] ?? level;
}

function syncStageLabel(stage: string): string {
  const labels: Record<string, string> = {
    provider_fetch: "抓取",
    snapshot_run: "运行记录",
    snapshot_write: "快照写入",
    aggregate_refresh: "聚合刷新",
    sync_result: "结果",
    sync_exception: "异常",
    sync_cancel: "取消"
  };
  return labels[stage] ?? stage;
}

function formatSyncLogDetails(details: Record<string, unknown>): string {
  return Object.entries(details)
    .map(([key, value]) => `${key}=${formatSyncLogValue(value)}`)
    .join("，");
}

function formatSyncLogValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map(formatSyncLogValue).join("|");
  }
  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function artifactFileName(path: string): string {
  return path.split(/[\\/]/).pop() || path;
}

function syncElapsedSecondsForDisplay(job: MarketSyncJob): number {
  if (job.status !== "running") {
    return job.elapsed_seconds;
  }
  const createdAt = new Date(job.created_at).getTime();
  if (Number.isNaN(createdAt)) {
    return job.elapsed_seconds;
  }
  return Math.max(Math.floor((Date.now() - createdAt) / 1000), job.elapsed_seconds);
}

function alertSeverityLabel(severity: MarketAlert["severity"]): string {
  const labels: Record<MarketAlert["severity"], string> = {
    high: "高",
    medium: "中",
    info: "信息"
  };
  return labels[severity];
}

function buildIndustryCoverage(industries: IndustryItem[]): IndustryCoverage {
  const totalStockCount = industries.reduce((sum, industry) => sum + industry.stock_count, 0);
  const unknown = industries.find((industry) => industry.industry_code === "UNKNOWN") ?? null;
  const unknownStockCount = unknown?.stock_count ?? 0;
  const knownStockCount = Math.max(totalStockCount - unknownStockCount, 0);
  const knownIndustries = industries.filter((industry) => industry.industry_code !== "UNKNOWN");
  const totalAmount = sumNullable(industries.map((industry) => industry.amount_sum));
  const knownAmount = sumNullable(knownIndustries.map((industry) => industry.amount_sum));
  const upCount = industries.reduce((sum, industry) => sum + industry.up_count, 0);
  const downCount = industries.reduce((sum, industry) => sum + industry.down_count, 0);
  return {
    totalStockCount,
    knownStockCount,
    unknownStockCount,
    knownIndustryCount: knownIndustries.length,
    totalAmount,
    knownAmount,
    upCount,
    downCount,
    unknownRatio: totalStockCount === 0 ? 0 : unknownStockCount / totalStockCount,
    upRatio: totalStockCount === 0 ? 0 : upCount / totalStockCount
  };
}

function sumNullable(values: Array<number | null>): number | null {
  const numbers = values.filter((value): value is number => value !== null);
  if (numbers.length === 0) {
    return null;
  }
  return numbers.reduce((sum, value) => sum + value, 0);
}

function heatClass(value: number | null): string {
  if (value === null || value === 0) {
    return "neutral";
  }
  if (value >= 2) {
    return "hot-up";
  }
  if (value > 0) {
    return "up";
  }
  if (value <= -2) {
    return "hot-down";
  }
  return "down";
}

function heatAmountWidth(value: number | null, maxAmount: number): number {
  if (value === null || maxAmount <= 0) {
    return 0;
  }
  return Math.max(8, Math.min((value / maxAmount) * 100, 100));
}

function alertStatusLabel(status: AlertStatus): string {
  const labels: Record<AlertStatus, string> = {
    new: "新",
    read: "已读",
    handled: "已处理",
    ignored: "忽略"
  };
  return labels[status];
}

function alertKindLabel(kind: MarketAlert["kind"]): string {
  const labels: Record<MarketAlert["kind"], string> = {
    data_stale: "数据过期",
    sync_failed: "同步失败",
    partial_sync: "部分同步",
    offline: "无数据",
    limit_up: "涨停",
    limit_down: "跌停",
    volume_surge: "放量",
    extreme_move: "异常涨跌幅"
  };
  return labels[kind];
}

function alertGroupTargetLabel(group: MarketAlertGroup): string {
  if (!group.security_id) {
    return "系统";
  }
  return `${group.name ?? "-"} ${group.security_id}`;
}

function alertGroupKindLabel(group: MarketAlertGroup): string {
  return group.kinds.map(alertKindLabel).join(" / ");
}

function groupMatchesKind(group: MarketAlertGroup, kind: AlertKindFilter): boolean {
  if (kind === "all") {
    return true;
  }
  if (kind === "system") {
    return group.security_id === null;
  }
  return group.kinds.includes(kind);
}

function formatAlertValue(alert: MarketAlert): string {
  if (alert.value === null) {
    return "-";
  }
  if (alert.metric === "change_pct" || alert.kind === "limit_up" || alert.kind === "limit_down") {
    return `${formatNumber(alert.value)}%`;
  }
  return formatNumber(alert.value);
}

function formatAlertThreshold(alert: MarketAlert): string {
  if (alert.threshold === null) {
    return "-";
  }
  if (alert.metric === "change_pct" || alert.kind === "limit_up" || alert.kind === "limit_down") {
    return `${formatNumber(alert.threshold)}%`;
  }
  return formatNumber(alert.threshold);
}

function formatPercentFromNullable(value: number | null): string {
  if (value === null) {
    return "-";
  }
  return `${formatNumber(value)}%`;
}

function StatusPill({ status }: { status: DataStatus }) {
  return <div className={`status-pill ${status}`}>{dataStatusLabel(status)}</div>;
}

function AlertPanel({
  groups,
  isLoading,
  error,
  onSelectAlert,
  onUpdateAlertStatus
}: {
  groups: MarketAlertGroup[];
  isLoading: boolean;
  error: string | null;
  onSelectAlert: (group: MarketAlertGroup) => void;
  onUpdateAlertStatus: (alertIds: string[], status: AlertStatus) => void;
}) {
  const [severityFilter, setSeverityFilter] = useState<AlertSeverityFilter>("all");
  const [kindFilter, setKindFilter] = useState<AlertKindFilter>("all");
  const [statusFilter, setStatusFilter] = useState<AlertStatusFilter>("all");
  const [expandedGroupId, setExpandedGroupId] = useState<string | null>(null);
  const visibleGroups = groups.filter(
    (group) =>
      (severityFilter === "all" || group.severity === severityFilter) &&
      (kindFilter === "all" || groupMatchesKind(group, kindFilter)) &&
      (statusFilter === "all" || group.status === statusFilter)
  );
  const highCount = groups.filter((group) => group.severity === "high").length;
  return (
    <section className="table-panel" aria-label="市场告警">
      <div className="section-heading">
        <div>
          <p className="eyebrow">告警</p>
          <h2>市场监控告警</h2>
        </div>
        <span>
          {isLoading
            ? "加载中"
            : `${formatInteger(groups.length)} 组 / ${formatInteger(highCount)} 高优先级`}
        </span>
      </div>
      <div className="controls-bar alert-controls">
        <div className="segmented-control" aria-label="告警等级筛选">
          {alertSeverityOptions.map((option) => (
            <button
              key={option.value}
              type="button"
              aria-pressed={severityFilter === option.value}
              onClick={() => setSeverityFilter(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
        <label>
          类型
          <select
            value={kindFilter}
            onChange={(event) => setKindFilter(event.target.value as AlertKindFilter)}
          >
            {alertKindOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          状态
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as AlertStatusFilter)}
          >
            {alertStatusOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {error ? <div className="inline-notice error">{error}</div> : null}
      {groups.length === 0 && !isLoading ? <div className="inline-notice">暂无告警</div> : null}
      {groups.length > 0 && visibleGroups.length === 0 ? (
        <div className="inline-notice">当前筛选下暂无告警</div>
      ) : null}
      {visibleGroups.length > 0 ? (
        <div className="table-wrap">
          <table className="alerts-table">
            <thead>
              <tr>
                <th>等级</th>
                <th>状态</th>
                <th>类型</th>
                <th>标的</th>
                <th>触发项</th>
                <th>触发时间</th>
                <th>原因</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {visibleGroups.map((group) => (
                <React.Fragment key={group.group_id}>
                  <tr
                    className={group.security_id ? "clickable-row" : undefined}
                    aria-selected={expandedGroupId === group.group_id}
                    onClick={() => {
                      setExpandedGroupId(
                        expandedGroupId === group.group_id ? null : group.group_id
                      );
                    }}
                    onDoubleClick={() => onSelectAlert(group)}
                  >
                    <td>
                      <span className={`alert-severity ${group.severity}`}>
                        {alertSeverityLabel(group.severity)}
                      </span>
                    </td>
                    <td>
                      <span className={`alert-status ${group.status}`}>
                        {alertStatusLabel(group.status)}
                      </span>
                    </td>
                    <td>{alertGroupKindLabel(group)}</td>
                    <td>
                      {group.security_id ? (
                        <button
                          className="link-button"
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            onSelectAlert(group);
                          }}
                        >
                          {alertGroupTargetLabel(group)}
                        </button>
                      ) : (
                        alertGroupTargetLabel(group)
                      )}
                    </td>
                    <td>{formatInteger(group.alert_count)}</td>
                    <td>{formatDateTime(group.triggered_at)}</td>
                    <td title={group.message}>{group.message}</td>
                    <td>
                      <AlertActionButtons
                        alertIds={group.alerts.map((alert) => alert.alert_id)}
                        currentStatus={group.status}
                        onUpdate={onUpdateAlertStatus}
                      />
                    </td>
                  </tr>
                  {expandedGroupId === group.group_id ? (
                    <tr className="alert-detail-row">
                      <td colSpan={8}>
                        <AlertGroupDetails
                          group={group}
                          onSelectAlert={onSelectAlert}
                          onUpdateAlertStatus={onUpdateAlertStatus}
                        />
                      </td>
                    </tr>
                  ) : null}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

function AlertGroupDetails({
  group,
  onSelectAlert,
  onUpdateAlertStatus
}: {
  group: MarketAlertGroup;
  onSelectAlert: (group: MarketAlertGroup) => void;
  onUpdateAlertStatus: (alertIds: string[], status: AlertStatus) => void;
}) {
  return (
    <div className="alert-group-detail">
      <div className="alert-group-detail-header">
        <div>
          <strong>{group.title}</strong>
          <span>{group.message}</span>
        </div>
        {group.security_id ? (
          <button className="retry-button" type="button" onClick={() => onSelectAlert(group)}>
            定位
          </button>
        ) : null}
      </div>
      <div className="alert-trigger-list">
        {group.alerts.map((alert) => (
          <div className="alert-trigger" key={alert.alert_id}>
            <span className={`alert-severity ${alert.severity}`}>
              {alertSeverityLabel(alert.severity)}
            </span>
            <span className={`alert-status ${alert.status}`}>
              {alertStatusLabel(alert.status)}
            </span>
            <strong>{alertKindLabel(alert.kind)}</strong>
            <span>{formatAlertValue(alert)} / {formatAlertThreshold(alert)}</span>
            <p>{alert.message}</p>
            <AlertActionButtons
              alertIds={[alert.alert_id]}
              currentStatus={alert.status}
              onUpdate={onUpdateAlertStatus}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

function AlertActionButtons({
  alertIds,
  currentStatus,
  onUpdate
}: {
  alertIds: string[];
  currentStatus: AlertStatus;
  onUpdate: (alertIds: string[], status: AlertStatus) => void;
}) {
  return (
    <div className="alert-actions">
      <button
        type="button"
        disabled={currentStatus === "read"}
        onClick={(event) => {
          event.stopPropagation();
          onUpdate(alertIds, "read");
        }}
      >
        已读
      </button>
      <button
        type="button"
        disabled={currentStatus === "handled"}
        onClick={(event) => {
          event.stopPropagation();
          onUpdate(alertIds, "handled");
        }}
      >
        处理
      </button>
      <button
        type="button"
        disabled={currentStatus === "ignored"}
        onClick={(event) => {
          event.stopPropagation();
          onUpdate(alertIds, "ignored");
        }}
      >
        忽略
      </button>
    </div>
  );
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

function StockDetailPanel({
  detail,
  selectedStockId,
  isLoading,
  error,
  onSelectIndustry,
  onUpdateAlertStatus
}: {
  detail: StockDetail | null;
  selectedStockId: string | null;
  isLoading: boolean;
  error: string | null;
  onSelectIndustry: (industryCode: string) => void;
  onUpdateAlertStatus: (alertIds: string[], status: AlertStatus) => void;
}) {
  if (!selectedStockId) {
    return (
      <div className="stock-detail empty-stock-detail">
        <p className="eyebrow">个股详情</p>
        <h3>选择一只股票查看快照与告警历史</h3>
      </div>
    );
  }
  if (error) {
    return <div className="inline-notice error">{error}</div>;
  }
  if (isLoading && !detail) {
    return <div className="inline-notice">加载 {selectedStockId} 详情...</div>;
  }
  if (!detail) {
    return null;
  }

  const stock = detail.snapshot;
  return (
    <div className="stock-detail">
      <div className="stock-detail-header">
        <div>
          <p className="eyebrow">个股详情</p>
          <h3>
            {stock.name} <span className="mono">{stock.security_id}</span>
          </h3>
        </div>
        <button
          className="retry-button"
          type="button"
          onClick={() => onSelectIndustry(stock.industry_code ?? "UNKNOWN")}
        >
          {displayIndustry(stock.industry_code)}
        </button>
      </div>
      {isLoading ? <div className="inline-notice">刷新个股详情...</div> : null}
      <div className="stock-detail-grid">
        <DetailItem label="最新价" value={formatNumber(stock.price)} />
        <DetailItem label="涨跌幅" value={formatSignedPercent(stock.change_pct)} />
        <DetailItem label="成交额" value={formatAmount(stock.amount)} />
        <DetailItem label="成交量" value={formatNumber(stock.volume)} />
        <DetailItem label="换手率" value={formatPercentFromNullable(stock.turnover_rate)} />
        <DetailItem label="量比" value={formatNumber(stock.volume_ratio)} />
        <DetailItem label="交易状态" value={stock.is_suspended ? "停牌" : "交易中"} />
        <DetailItem label="市盈率 TTM" value={formatNumber(stock.pe_ttm)} />
        <DetailItem label="市净率" value={formatNumber(stock.pb)} />
        <DetailItem label="总市值" value={formatAmount(stock.market_cap)} />
        <DetailItem label="快照时间" value={formatDateTime(stock.snapshot_time)} />
        <DetailItem label="数据源" value={stock.source} />
        <DetailItem label="抓取时间" value={formatDateTime(stock.fetched_at)} />
      </div>
      <div className="stock-alert-history">
        <div className="section-heading compact-heading">
          <div>
            <p className="eyebrow">告警历史</p>
            <h3>最近触发记录</h3>
          </div>
          <span>{formatInteger(detail.alerts.length)} 条</span>
        </div>
        {detail.alerts.length === 0 ? (
          <div className="inline-notice">该股票暂无持久化告警记录</div>
        ) : (
          <div className="alert-trigger-list stock-alert-list">
            {detail.alerts.map((alert) => (
              <div className="alert-trigger" key={alert.alert_id}>
                <span className={`alert-severity ${alert.severity}`}>
                  {alertSeverityLabel(alert.severity)}
                </span>
                <span className={`alert-status ${alert.status}`}>
                  {alertStatusLabel(alert.status)}
                </span>
                <strong>{alertKindLabel(alert.kind)}</strong>
                <span>{formatDateTime(alert.triggered_at)}</span>
                <p>{alert.message}</p>
                <AlertActionButtons
                  alertIds={[alert.alert_id]}
                  currentStatus={alert.status}
                  onUpdate={onUpdateAlertStatus}
                />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StockTable({
  stocks,
  selectedStockId,
  onSelectStock
}: {
  stocks: StockItem[];
  selectedStockId: string | null;
  onSelectStock: (securityId: string) => void;
}) {
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
            <tr
              className="clickable-row"
              key={stock.security_id}
              aria-selected={selectedStockId === stock.security_id}
              onClick={() => onSelectStock(stock.security_id)}
            >
              <td>
                <button
                  className="link-button mono"
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onSelectStock(stock.security_id);
                  }}
                >
                  {stock.security_id}
                </button>
              </td>
              <td>
                <span className="stock-name-cell">
                  {stock.name}
                  {stock.is_suspended ? <span className="stock-status suspended">停牌</span> : null}
                </span>
              </td>
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
