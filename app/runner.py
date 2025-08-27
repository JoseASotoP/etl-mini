# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Runner de ETL por grupos con configuración YAML, DQ y ledger en DuckDB.

Carga fuentes via adaptadores, aplica reglas de calidad (dq.yml) y registra
métricas en tablas `etl_runs` y `etl_metrics`. Genera además un health JSON.

Ejemplos:
    $ python -m app.runner --group daily
    $ python -m app.runner --config config/sources.yml --dq config/dq.yml
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

import duckdb
import pandas as pd
import yaml

from app.utils import load_settings
from .adapters.base import get_adapter
from .adapters import csv_local, http_json  # noqa: F401  (registro de adaptadores)

CONFIG_DEFAULT = "config/sources.yml"
DQ_DEFAULT = "config/dq.yml"


def ensure_ledger(db_path: str):
    con = duckdb.connect(db_path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS etl_runs (
            run_id       VARCHAR PRIMARY KEY,
            started_at   TIMESTAMP,
            finished_at  TIMESTAMP,
            group_name   VARCHAR,
            status       VARCHAR,
            rows_total   BIGINT,
            duration_s   DOUBLE
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS etl_metrics (
            run_id         VARCHAR,
            source_name    VARCHAR,
            table_name     VARCHAR,
            rows_loaded    BIGINT,
            dq_pass        BOOLEAN,
            dq_violations  INTEGER,
            duration_s     DOUBLE,
            loaded_at      TIMESTAMP
        )
    """)
    con.execute("""
        CREATE VIEW IF NOT EXISTS v_etl_last AS
        SELECT
          table_name,
          ANY_VALUE(source_name)   AS source_name,
          MAX(loaded_at)           AS loaded_at,
          ANY_VALUE(dq_pass)       AS dq_pass,
          ANY_VALUE(dq_violations) AS dq_violations,
          ANY_VALUE(rows_loaded)   AS rows_loaded
        FROM etl_metrics
        GROUP BY table_name
    """)
    con.close()


def load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    return bool(
        con.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='main' AND table_name=?",
            [name],
        ).fetchone()
    )


def apply_dq(
    df: pd.DataFrame,
    table: str,
    dq: Dict[str, Any],
) -> Dict[str, Any]:
    rules = (dq.get("rules") or {}).get(table)
    result = {"pass": True, "violations": 0, "on_fail": "warn"}
    if not rules:
        return result

    schema = rules.get("schema") or {}
    checks = rules.get("checks") or []
    result["on_fail"] = rules.get("on_fail", "warn")

    dfc = df.copy()
    for col, typ in schema.items():
        if col not in dfc.columns:
            continue
        if typ == "int":
            dfc[col] = pd.to_numeric(dfc[col], errors="coerce").astype("Int64")
        elif typ == "float":
            dfc[col] = pd.to_numeric(dfc[col], errors="coerce")
        elif typ == "datetime":
            dfc[col] = pd.to_datetime(dfc[col], errors="coerce", utc=True)
        elif typ == "str":
            dfc[col] = dfc[col].astype("string")

    violations = 0
    for rule in checks:
        if "not_null" in rule:
            cols = rule["not_null"]
            nulls = dfc[cols].isna().any(axis=1).sum()
            violations += int(nulls > 0)
        elif "unique" in rule:
            cols = rule["unique"]
            dups = dfc.duplicated(subset=cols).sum()
            violations += int(dups > 0)
        elif "range" in rule:
            r = rule["range"]
            col, vmin, vmax = r["column"], r.get("min"), r.get("max")
            if col in dfc.columns:
                s = pd.to_numeric(dfc[col], errors="coerce")
                bad = 0
                if vmin is not None:
                    bad += (s < vmin).sum()
                if vmax is not None:
                    bad += (s > vmax).sum()
                violations += int(bad > 0)

    result["violations"] = int(violations)
    result["pass"] = violations == 0
    return result


def _build_cast_select(src_table: str, cast_map: Dict[str, str] | None) -> str:
    if not cast_map:
        return f"SELECT * FROM {src_table}"
    parts = [f"TRY_CAST({src_table}.{col} AS {typ}) AS {col}" for col, typ in cast_map.items()]
    return f"SELECT * REPLACE({', '.join(parts)}) FROM {src_table}"


def incremental_upsert(
    con: duckdb.DuckDBPyConnection,
    stage_table: str,
    dest_table: str,
    key_cols: List[str],
    cast_map: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    if not key_cols:
        raise ValueError(f"Modo incremental requiere 'key' en YAML para {dest_table}")

    casted_view = f"{dest_table}__castview"
    con.execute(f"DROP VIEW IF EXISTS {casted_view}")
    con.execute(f"CREATE VIEW {casted_view} AS {_build_cast_select(stage_table, cast_map)}")

    if not _table_exists(con, dest_table):
        con.execute(f"CREATE TABLE {dest_table} AS SELECT * FROM {casted_view} LIMIT 0")

    on_join = " AND ".join([f"s.{k} = t.{k}" for k in key_cols])
    not_null_pred = " AND ".join([f"s.{k} IS NOT NULL" for k in key_cols])
    first_key = key_cols[0]

    cols = con.execute(f"PRAGMA table_info('{dest_table}')").fetchdf()["name"].tolist()
    select_cols = ", ".join([f"s.{c}" for c in cols])

    to_insert = f"{dest_table}__to_insert"
    con.execute(f"DROP TABLE IF EXISTS {to_insert}")
    con.execute(
        f"""
        CREATE TEMP TABLE {to_insert} AS
        SELECT {select_cols}
        FROM {casted_view} s
        LEFT JOIN {dest_table} t
          ON {on_join}
        WHERE t.{first_key} IS NULL
          AND ({not_null_pred})
        """
    )

    before = con.execute(f"SELECT COUNT(*) FROM {dest_table}").fetchone()[0]
    skipped_null_key = con.execute(
        f"SELECT COUNT(*) FROM {casted_view} s WHERE NOT ({not_null_pred})"
    ).fetchone()[0]
    total_casted = con.execute(f"SELECT COUNT(*) FROM {casted_view}").fetchone()[0]

    con.execute(f"INSERT INTO {dest_table} SELECT * FROM {to_insert}")
    after = con.execute(f"SELECT COUNT(*) FROM {dest_table}").fetchone()[0]
    inserted = after - before
    skipped_dup = max(total_casted - skipped_null_key - inserted, 0)

    con.execute(f"DROP VIEW IF EXISTS {casted_view}")

    return {
        "inserted": inserted,
        "skipped_null_key": skipped_null_key,
        "skipped_dup": skipped_dup,
        "to_insert_table": to_insert,
    }


def export_parquet(
    con: duckdb.DuckDBPyConnection,
    table: str,
    cfg: Dict[str, Any],
) -> str | None:
    dir_ = cfg.get("dir")
    if not dir_:
        return None

    overwrite = bool(cfg.get("overwrite", False))
    part = cfg.get("partition_by") or []
    part_list = ", ".join(part)
    overwrite_clause = ", OVERWRITE_OR_IGNORE TRUE" if overwrite else ""
    os.makedirs(dir_, exist_ok=True)

    if cfg.get("export_sql"):
        sql = cfg["export_sql"]
        con.execute(
            f"""
            COPY ({sql})
            TO '{dir_}/'
            (FORMAT PARQUET{', PARTITION_BY ('+part_list+')' if part_list else ''}{overwrite_clause})
            """
        )
    else:
        con.execute(
            f"""
            COPY {table}
            TO '{dir_}/'
            (FORMAT PARQUET{', PARTITION_BY ('+part_list+')' if part_list else ''}{overwrite_clause})
            """
        )
    return dir_


def run_group(
    group: str,
    config: Dict[str, Any],
    dq: Dict[str, Any],
) -> str:
    defaults = config.get("defaults") or {}
    db_path = defaults.get("db_path", "data/warehouse.duckdb")
    ensure_ledger(db_path)

    group_list = (config.get("groups") or {}).get(group) or []
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    started = datetime.now(timezone.utc)

    # ajustes de runner / reportes
    settings = {}
    try:
        settings = load_settings() or {}
    except Exception:
        settings = {}
    r_cfg = settings.get("runner") or {}
    p_cfg = settings.get("paths") or {}
    fail_fast = bool(r_cfg.get("fail_fast", False))
    dq_mode = (r_cfg.get("dq_report") or "html").lower()
    reports_dir = p_cfg.get("reports_dir", "data/reports")
    os.makedirs(reports_dir, exist_ok=True)

    run_status = "ok"
    rows_total = 0
    metrics_rows: List[Dict[str, Any]] = []
    error_msg = None

    for src in group_list:
        name = src["name"]
        typ = src["type"]
        table = src.get("table", name)
        params = src.get("params") or {}
        ctx = {
            "db_path": db_path,
            "table": table,
            "mode": src.get("mode", defaults.get("mode", "replace")),
        }
        try:
            Adapter = get_adapter(typ)
            adp = Adapter(params=params, context=ctx)
            table_name, rows_loaded, dur = adp.run()

            con = duckdb.connect(db_path)
            df = con.execute(f"SELECT * FROM {table_name}").fetchdf()
            dqres = apply_dq(df, table_name, dq)
            con.close()

            dq_pass = dqres["pass"]
            dq_violations = dqres["violations"]

            print(
                f"[RUN] {name} → {table_name}: {rows_loaded} filas "
                f"({dur:.2f}s) DQ pass={dq_pass} vio={dq_violations}"
            )

            if not dq_pass:
                if dq_mode in ("html", "both"):
                    dq_html_path = os.path.join(reports_dir, f"dq_{name}_{run_id}.html")
                    try:
                        with open(dq_html_path, "w", encoding="utf-8") as _f:
                            _f.write(
                                "<html><head><meta charset='utf-8'><title>DQ Report</title></head><body>"
                                f"<h1>Data Quality – {name}</h1>"
                                f"<p><b>Run:</b> {run_id}</p>"
                                f"<p><b>Violations:</b> {int(dq_violations)}</p>"
                                f"<p><b>Pass:</b> {dq_pass}</p>"
                                "</body></html>"
                            )
                        print(f"[DQ-REPORT] {dq_html_path}")
                    except Exception as _e:
                        print(f"[DQ-REPORT] WARN al escribir HTML: {_e}")

                print(f"[DQ-FAIL] {table_name} violations={int(dq_violations)}")
                if fail_fast:
                    print("[ABORT] fail_fast=true — stopping group")
                    run_status = "fail"
                    break

            rows_total += int(rows_loaded)
            metrics_rows.append(
                {
                    "run_id": run_id,
                    "source_name": name,
                    "table_name": table_name,
                    "rows_loaded": int(rows_loaded),
                    "duration_s": float(dur),
                    "dq_pass": dq_pass,
                    "dq_violations": int(dq_violations),
                    "loaded_at": datetime.now(timezone.utc),
                }
            )

        except Exception as e:
            run_status = "fail"
            error_msg = str(e)
            print(f"[RUN][ERROR] {name}: {e}")
            break

    finished = datetime.now(timezone.utc)
    duration = (finished - started).total_seconds()

    # --- Persistencia: dentro de la MISMA conexión y en el orden correcto ---
    con = duckdb.connect(db_path)

    if metrics_rows:
        con.register("df_metrics", pd.DataFrame(metrics_rows))
        con.execute(
            """
            INSERT INTO etl_metrics
              (run_id, source_name, table_name, rows_loaded, dq_pass, dq_violations, duration_s, loaded_at)
            SELECT run_id, source_name, table_name, rows_loaded, dq_pass, dq_violations, duration_s, loaded_at
            FROM df_metrics
            """
        )

    con.execute(
        """
        INSERT INTO etl_runs
          (run_id, started_at, finished_at, group_name, status, rows_total, duration_s)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [run_id, started, finished, group, run_status, rows_total, duration],
    )

    con.close()

    # Health JSON (informativo)
    health_path = os.path.join(reports_dir, f"health_{run_id}.json")
    with open(health_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "run_id": run_id,
                "group": group,
                "status": run_status,
                "error": error_msg,
                "sources": len(group_list),
                "rows_total": rows_total,
                "duration_s": duration,
                "at": finished.isoformat(),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    return run_status


def main() -> None:
    ap = argparse.ArgumentParser(description="ETL Runner (config + DQ + ledger)")
    ap.add_argument("--config", default=CONFIG_DEFAULT, help="Ruta a sources.yml")
    ap.add_argument("--dq", default=DQ_DEFAULT, help="Ruta a dq.yml")
    ap.add_argument("--group", default="daily", help="Grupo a ejecutar (clave en 'groups').")
    args = ap.parse_args()

    cfg = load_yaml(args.config)
    dq = load_yaml(args.dq)
    status = run_group(args.group, cfg, dq)
    sys.exit(0 if status == "ok" else 1)


if __name__ == "__main__":
    main()
