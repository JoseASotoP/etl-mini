# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Runner de ETL por grupos con configuración YAML, DQ y ledger en DuckDB.

Carga fuentes via adaptadores, aplica reglas de calidad (dq.yml) y registra
métricas en tablas `etl_runs` y `etl_metrics`. Genera además un health JSON.

Parameters
----------
None

Returns
-------
None
    Módulo con punto de entrada CLI.

Preconditions
--------------
- Ficheros `config/sources.yml` y `config/dq.yml` legibles.
- DuckDB accesible en la ruta configurada.
- Adaptadores registrados en `app.adapters`.

Example
--------
$ python -m app.runner --group daily
$ python -m app.runner --config config/sources.yml --dq config/dq.yml
"""

import argparse
import json
import os
import sys
import time  # noqa: F401 (posible uso futuro)
from datetime import datetime, timezone
from typing import Any, Dict, List

import duckdb
import pandas as pd
import yaml

# --- Lote 2: imports mínimos para fail-fast ---
from app.utils import load_settings
from .adapters.base import get_adapter
# asegura el registro de adaptadores (efecto lateral import)
from .adapters import csv_local, http_json  # noqa: F401

CONFIG_DEFAULT = "config/sources.yml"
DQ_DEFAULT = "config/dq.yml"


def ensure_ledger(db_path: str) -> None:
    """
    Crea tablas de control `etl_runs` y `etl_metrics` si no existen.

    Parameters
    ----------
    db_path : str
        Ruta al archivo DuckDB.

    Returns
    -------
    None
    """
    con = duckdb.connect(db_path)
    con.execute(
        """
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
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS etl_metrics (
          run_id TEXT,
          source_name TEXT,
          table_name TEXT,
          rows_loaded INTEGER,
          duration_s DOUBLE,
          dq_pass BOOLEAN,
          dq_violations INTEGER,
          loaded_at TIMESTAMP  -- sello temporal de carga POR FUENTE
        )
        """
    )
    con.close()


def load_yaml(path: str) -> Dict[str, Any]:
    """
    Carga un YAML a dict usando `yaml.safe_load`.

    Parameters
    ----------
    path : str
        Ruta del archivo YAML.

    Returns
    -------
    Dict[str, Any]
        Contenido del YAML o dict vacío si está vacío.
    """
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    """
    Verifica si existe una tabla en la base de datos.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Conexión activa a DuckDB.
    name : str
        Nombre de la tabla.

    Returns
    -------
    bool
    """
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
    """
    Valida un DataFrame según `dq.yml`. Devuelve pass/violations.

    Soporta `schema` (casts: int/float/datetime/str) y `checks` de
    `not_null`, `unique` y `range`.

    Parameters
    ----------
    df : pandas.DataFrame
        Datos a validar.
    table : str
        Nombre lógico de la tabla para buscar reglas.
    dq : Dict[str, Any]
        Reglas cargadas desde `dq.yml`.

    Returns
    -------
    Dict[str, Any]
        {'pass': bool, 'violations': int, 'on_fail': 'warn'|'block'}
    """
    rules = (dq.get("rules") or {}).get(table)
    result = {"pass": True, "violations": 0, "on_fail": "warn"}
    if not rules:
        return result

    schema = rules.get("schema") or {}
    checks = rules.get("checks") or []
    result["on_fail"] = rules.get("on_fail", "warn")

    # casts
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
    """
    Devuelve un SELECT con TRY_CAST según cast_map o '*' si no se define.

    Parameters
    ----------
    src_table : str
        Nombre de la tabla staging.
    cast_map : Dict[str, str] | None
        Mapeo de columnas a tipos.

    Returns
    -------
    str
    """
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
    """
    Inserta solo filas nuevas de stage→dest usando dedupe por key_cols.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Conexión activa.
    stage_table : str
        Nombre de la tabla staging.
    dest_table : str
        Nombre de la tabla destino.
    key_cols : List[str]
        Columnas clave para incremental.
    cast_map : Dict[str, str] | None
        Mapeo de casts.

    Returns
    -------
    Dict[str, Any]
    """
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
    """
    Exporta a parquet según cfg: {dir, overwrite, partition_by, export_sql?}.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Conexión activa.
    table : str
        Nombre de la tabla.
    cfg : Dict[str, Any]
        Configuración.

    Returns
    -------
    str | None
    """
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
    """
    Ejecuta un grupo de fuentes: extrae, valida y registra métricas.

    Parameters
    ----------
    group : str
        Nombre del grupo a ejecutar.
    config : Dict[str, Any]
        Configuración completa de `sources.yml`.
    dq : Dict[str, Any]
        Reglas de `dq.yml`.

    Returns
    -------
    str
        Estado final del run ("ok" | "fail").
    """
    defaults = config.get("defaults") or {}
    db_path = defaults.get("db_path", "data/warehouse.duckdb")
    ensure_ledger(db_path)

    group_list = (config.get("groups") or {}).get(group) or []
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    started = datetime.now(timezone.utc)

    # --- Lote 2: setup fail-fast ---
    _settings = {}
    try:
        _settings = load_settings() or {}
    except Exception:
        _settings = {}
    _runner_cfg = _settings.get("runner") or {}
    _paths_cfg = _settings.get("paths") or {}
    _fail_fast = bool(_runner_cfg.get("fail_fast", False))
    _dq_mode = (_runner_cfg.get("dq_report") or "html").lower()
    _reports_dir = _paths_cfg.get("reports_dir", "data/reports")
    os.makedirs(_reports_dir, exist_ok=True)

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

            # --- Lote 2: reacción a DQ ---
            if not dq_pass:
                if _dq_mode in ("html", "both"):
                    dq_html_path = os.path.join(_reports_dir, f"dq_{name}_{run_id}.html")
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
                if _fail_fast:
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

    con = duckdb.connect(db_path)
    if metrics_rows:
        con.register("df_metrics", pd.DataFrame(metrics_rows))
        con.execute(
            """
            INSERT INTO etl_metrics
            SELECT run_id, source_name, table_name, rows_loaded,
                   duration_s, dq_pass, dq_violations, loaded_at
            FROM df_metrics
            """
        )
    con.execute(
        """
        INSERT INTO etl_runs
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            run_id,
            started,
            finished,
            group,
            run_status,
            error_msg,
            len(group_list),
            rows_total,
            duration,
        ],
    )
    con.close()

    health_path = os.path.join(_reports_dir, f"health_{run_id}.json")
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
    """
    Punto de entrada CLI para ejecutar un grupo con DQ y ledger.

    Returns
    -------
    None
    """
    ap = argparse.ArgumentParser(description="ETL Runner (config + DQ + ledger)")
    ap.add_argument("--config", default=CONFIG_DEFAULT, help="Ruta a sources.yml")
    ap.add_argument("--dq", default=DQ_DEFAULT, help="Ruta a dq.yml")
    ap.add_argument("--group", default="daily", help="Grupo a ejecutar (clave en 'groups').")
    args = ap.parse_args()

    cfg = load_yaml(args.config)
    dq = load_yaml(args.dq)
    status = run_group(args.group, cfg, dq)

    # --- Lote 2: exit code ---
    sys.exit(0 if status == "ok" else 1)


if __name__ == "__main__":
    main()
