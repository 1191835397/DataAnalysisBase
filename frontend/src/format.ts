import type { RuntimeStatus } from "./types";

export function latestRunCaption(status: RuntimeStatus): string {
  if (!status.last_market_run) {
    return "暂无同步运行记录";
  }
  return `最近同步 ${status.last_market_run.status}，实际 ${formatInteger(
    status.last_market_run.actual
  )}，缺失 ${formatInteger(status.last_market_run.missing)}`;
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
