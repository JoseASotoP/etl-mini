#!/usr/bin/env bash
set -euo pipefail
python -m pip install --upgrade pip
pip install duckdb pandas pyyaml requests streamlit
mkdir -p data data/parquet data/reports
python - <<'PY'
import duckdb
con = duckdb.connect('data/warehouse.duckdb')
con.execute("""
CREATE TABLE IF NOT EXISTS etl_runs (
  run_id TEXT PRIMARY KEY,
  started_at TIMESTAMP,
  finished_at TIMESTAMP,
  group_name TEXT,
  status TEXT,
  error TEXT,
  sources_count INTEGER,
  rows_total INTEGER,
  duration_s DOUBLE
)""")
con.execute("""
CREATE TABLE IF NOT EXISTS etl_metrics (
  run_id TEXT,
  source_name TEXT,
  table_name TEXT,
  rows_loaded INTEGER,
  duration_s DOUBLE,
  dq_pass BOOLEAN,
  dq_violations INTEGER,
  loaded_at TIMESTAMP
)""")
con.close()
PY
echo "Bootstrap OK. Siguiente: streamlit run app/serve.py  |  python -m app.runner --group daily"
