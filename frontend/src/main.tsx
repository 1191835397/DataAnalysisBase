import React from "react";
import { createRoot } from "react-dom/client";
import { Activity, BarChart3, Bell, Layers, Search } from "lucide-react";

import "./styles.css";

const navigation = [
  { label: "市场总览", icon: Activity },
  { label: "行业", icon: Layers },
  { label: "股票", icon: Search },
  { label: "告警", icon: Bell }
];

function App() {
  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <BarChart3 aria-hidden="true" />
          <span>DataAnalysisBase</span>
        </div>
        <nav>
          {navigation.map(({ label, icon: Icon }) => (
            <button className="nav-item" key={label} type="button">
              <Icon aria-hidden="true" size={18} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
      </aside>
      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Phase A Skeleton</p>
            <h1>A 股全市场智能监管与分析平台</h1>
          </div>
          <div className="status-pill">offline</div>
        </header>
        <section className="dashboard-grid" aria-label="Phase A dashboard preview">
          <article className="metric-panel">
            <span>市场总览</span>
            <strong>等待快照</strong>
            <p>接入 `/api/v1/market/overview` 后展示宽度、成交额和告警摘要。</p>
          </article>
          <article className="metric-panel">
            <span>行业排行</span>
            <strong>等待聚合</strong>
            <p>接入 `industry_snapshots` 后展示热力图和行业成分股入口。</p>
          </article>
          <article className="metric-panel wide">
            <span>全市场股票</span>
            <strong>服务端分页</strong>
            <p>下一步接入 `/api/v1/stocks`，保持每页不超过 200 行。</p>
          </article>
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
