CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS securities (
    security_id VARCHAR PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    market VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    type VARCHAR NOT NULL,
    currency VARCHAR NOT NULL DEFAULT 'CNY',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS industries (
    industry_code VARCHAR PRIMARY KEY,
    industry_name VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS market_snapshot_runs (
    snapshot_time TIMESTAMPTZ NOT NULL,
    source VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    expected INTEGER NOT NULL DEFAULT 0,
    actual INTEGER NOT NULL DEFAULT 0,
    missing INTEGER NOT NULL DEFAULT 0,
    field_nulls JSON,
    error TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    PRIMARY KEY (snapshot_time, source)
);

CREATE TABLE IF NOT EXISTS api_sync_jobs (
    job_id VARCHAR PRIMARY KEY,
    status VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    result JSON,
    error TEXT,
    cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
    message TEXT NOT NULL DEFAULT '',
    elapsed_seconds INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS market_snapshots (
    snapshot_time TIMESTAMPTZ NOT NULL,
    security_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    price DOUBLE,
    change_pct DOUBLE,
    volume DOUBLE,
    amount DOUBLE,
    turnover_rate DOUBLE,
    volume_ratio DOUBLE,
    pe_ttm DOUBLE,
    pb DOUBLE,
    market_cap DOUBLE,
    industry_code VARCHAR,
    source VARCHAR NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (snapshot_time, security_id, source)
);

CREATE TABLE IF NOT EXISTS latest_market_snapshot (
    snapshot_time TIMESTAMPTZ NOT NULL,
    security_id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    price DOUBLE,
    change_pct DOUBLE,
    volume DOUBLE,
    amount DOUBLE,
    turnover_rate DOUBLE,
    volume_ratio DOUBLE,
    pe_ttm DOUBLE,
    pb DOUBLE,
    market_cap DOUBLE,
    industry_code VARCHAR,
    source VARCHAR NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS market_overview_snapshots (
    snapshot_time TIMESTAMPTZ PRIMARY KEY,
    stock_count INTEGER NOT NULL,
    up_count INTEGER NOT NULL,
    down_count INTEGER NOT NULL,
    flat_count INTEGER NOT NULL,
    limit_up_count INTEGER NOT NULL,
    limit_down_count INTEGER NOT NULL,
    total_amount DOUBLE,
    source VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS industry_snapshots (
    snapshot_time TIMESTAMPTZ NOT NULL,
    industry_code VARCHAR NOT NULL,
    stock_count INTEGER NOT NULL,
    change_pct_avg DOUBLE,
    amount_sum DOUBLE,
    up_count INTEGER NOT NULL,
    down_count INTEGER NOT NULL,
    source VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (snapshot_time, industry_code, source)
);
