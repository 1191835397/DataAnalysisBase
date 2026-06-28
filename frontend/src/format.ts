import type { DataStatus, RuntimeStatus } from "./types";

const dataStatusLabels: Record<DataStatus, string> = {
  fresh: "正常",
  stale: "已过期",
  partial: "部分同步",
  failed: "同步失败",
  offline: "无数据"
};

const dataStatusMessages: Record<DataStatus, string> = {
  fresh: "市场快照处于可用窗口内。",
  stale: "最近快照已超过 freshness 阈值，页面仍展示最后一次成功数据。",
  partial: "最近同步未完整覆盖全市场，部分列表或统计可能缺失。",
  failed: "最近一次市场同步失败，页面仍展示可用的历史快照。",
  offline: "当前没有可用市场快照，请先执行一次市场同步。"
};

export function latestRunCaption(status: RuntimeStatus): string {
  if (!status.last_market_run) {
    return "暂无同步运行记录";
  }
  return `最近同步 ${status.last_market_run.status}，实际 ${formatInteger(
    status.last_market_run.actual
  )}，缺失 ${formatInteger(status.last_market_run.missing)}`;
}

export function dataStatusLabel(status: DataStatus): string {
  return dataStatusLabels[status];
}

export function dataStatusMessage(status: RuntimeStatus): string {
  const snapshot = formatDateTime(status.latest_snapshot_time);
  const message = dataStatusMessages[status.data_status];
  if (!status.last_market_run) {
    return `${message} 快照：${snapshot}。`;
  }
  return `${message} ${latestRunCaption(status)}，快照：${snapshot}。`;
}

export function formatInteger(value: number): string {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(value);
}

export function formatNumber(value: number | null): string {
  if (value === null) {
    return "-";
  }
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value);
}

export function formatPercent(value: number): string {
  return new Intl.NumberFormat("zh-CN", {
    style: "percent",
    maximumFractionDigits: 1
  }).format(value);
}

export function formatSignedPercent(value: number | null): string {
  if (value === null) {
    return "-";
  }
  const formatted = new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: 2,
    signDisplay: "always"
  }).format(value);
  return `${formatted}%`;
}

export function formatAmount(value: number | null): string {
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

export function formatDateTime(value: string | null): string {
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
