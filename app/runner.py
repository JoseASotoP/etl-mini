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
import time  # noqa: F401 (posible uso futuro)
from datetime import datetime, timezone
from typing import Any, Dict, List

import duckdb
import pandas as pd
import yaml

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

    Preconditions
    --------------
    Debe poder abrirse una conexión de escritura a `db_path`.

    Example
    --------
    >>> ensure_ledger("data/warehouse.duckdb")  # doctest: +SKIP
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

    Preconditions
    --------------
    El archivo debe existir y ser texto UTF-8 válido.

    Example
    --------
    >>> cfg = load_yaml("config/sources.yml")  # doctest: +SKIP
    """
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    return bool(con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='main' AND table_name=?", [name]
    ).fetchone())


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

    Preconditions
    --------------
    Las claves deben existir si se usan en reglas y ser casteables.

    Example
    --------
    >>> res = apply_dq(pd.DataFrame(), "t", {"rules": {}})  # doctest: +SKIP
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
            dfc[col] = pd.to_numeric(
                dfc[col], errors="coerce"
            ).astype("Int64")
        elif typ == "float":
            dfc[col] = pd.to_numeric(dfc[col], errors="coerce")
        elif typ == "datetime":
            dfc[col] = pd.to_datetime(
                dfc[col], errors="coerce", utc=True
            )
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
            col, vmin, vmax = (
                r["column"],
                r.get("min"),
                r.get("max"),
            )
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
    """
    if not cast_map:
        return f"SELECT * FROM {src_table}"
    parts = []
    for col, typ in cast_map.items():
        parts.append(f"TRY_CAST({src_table}.{col} AS {typ}) AS {col}")
    # incluimos también columnas no listadas en cast_map tal cual (si existen)
    return (
        f"SELECT * REPLACE({', '.join(parts)}) "
        f"FROM {src_table}"
    )

def incremental_upsert(
    con: duckdb.DuckDBPyConnection,
    stage_table: str,
    dest_table: str,
    key_cols: List[str],
    cast_map: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    """
    Inserta solo filas nuevas de stage→dest usando dedupe por key_cols con TRY_CAST.
    Si dest no existe, crea el esquema con el SELECT casteado (sin datos).

    Además, deja creada una tabla temporal {dest_table}__to_insert
    con el lote a insertar (casteado y deduplicado) para que el caller
    pueda aplicar DQ sobre ese lote. El caller puede dropearla después.

    Devuelve:
      {
        'inserted': X,
        'skipped_null_key': Y,
        'skipped_dup': Z,
        'to_insert_table': '<dest>__to_insert'
      }
    """
    if not key_cols:
        raise ValueError(f"Modo incremental requiere 'key' en YAML para {dest_table}")

    # 1) Vista casteada desde staging
    casted_view = f"{dest_table}__castview"
    con.execute(f"DROP VIEW IF EXISTS {casted_view}")
    con.execute(f"CREATE VIEW {casted_view} AS {_build_cast_select(stage_table, cast_map)}")

    # 2) Asegurar tabla destino (mismo esquema que la vista casteada, sin datos)
    if not _table_exists(con, dest_table):
        con.execute(f"CREATE TABLE {dest_table} AS SELECT * FROM {casted_view} LIMIT 0")

    # 3) Predicados de join y no-nulos (¡alias 's'!)
    on_join = " AND ".join([f"s.{k} = t.{k}" for k in key_cols])
    not_null_pred = " AND ".join([f"s.{k} IS NOT NULL" for k in key_cols])
    first_key = key_cols[0]

    # 4) Columnas en el orden exacto del destino
    cols = con.execute(f"PRAGMA table_info('{dest_table}')").fetchdf()["name"].tolist()
    select_cols = ", ".join([f"s.{c}" for c in cols])

    # 5) Tabla temporal con el lote a insertar (casteado + dedupe + clave no nula)
    to_insert = f"{dest_table}__to_insert"
    con.execute(f"DROP TABLE IF EXISTS {to_insert}")
    con.execute(f"""
        CREATE TEMP TABLE {to_insert} AS
        SELECT {select_cols}
        FROM {casted_view} s
        LEFT JOIN {dest_table} t
          ON {on_join}
        WHERE t.{first_key} IS NULL
          AND ({not_null_pred})
    """)

    # 6) Estadísticos previos y descartes por clave nula
    before = con.execute(f"SELECT COUNT(*) FROM {dest_table}").fetchone()[0]
    skipped_null_key = con.execute(f"SELECT COUNT(*) FROM {casted_view} s WHERE NOT ({not_null_pred})").fetchone()[0]
    total_casted = con.execute(f"SELECT COUNT(*) FROM {casted_view}").fetchone()[0]

    # 7) Insertar
    con.execute(f"INSERT INTO {dest_table} SELECT * FROM {to_insert}")
    after = con.execute(f"SELECT COUNT(*) FROM {dest_table}").fetchone()[0]
    inserted = after - before
    skipped_dup = max(total_casted - skipped_null_key - inserted, 0)

    # 8) Limpieza de la castview (dejamos __to_insert para DQ del caller)
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
    Exporta a parquet según cfg: {dir, overwrite, partition_by, export_sql?}
    Si export_sql existe, hace COPY (SELECT ...).
    Maneja correctamente el caso sin particiones (sin PARTITION_BY ()).
    """
    dir_ = cfg.get("dir")
    if not dir_:
        return None

    overwrite = bool(cfg.get("overwrite", False))
    part = cfg.get("partition_by") or []
    part_list = ", ".join(part)
    overwrite_clause = ", OVERWRITE_OR_IGNORE TRUE" if overwrite else ""

    # Asegurar que el directorio existe
    os.makedirs(dir_, exist_ok=True)

    if cfg.get("export_sql"):
        sql = cfg["export_sql"]
        if part_list:
            con.execute(f"""
                COPY ({sql})
                TO '{dir_}/'
                (FORMAT PARQUET, PARTITION_BY ({part_list}){overwrite_clause})
            """)
        else:
            con.execute(f"""
                COPY ({sql})
                TO '{dir_}/'
                (FORMAT PARQUET{overwrite_clause})
            """)
    else:
        if part_list:
            con.execute(f"""
                COPY {table}
                TO '{dir_}/'
                (FORMAT PARQUET, PARTITION_BY ({part_list}){overwrite_clause})
            """)
        else:
            con.execute(f"""
                COPY {table}
                TO '{dir_}/'
                (FORMAT PARQUET{overwrite_clause})
            """)
    return dir_

def run_group(
    group: str,
    config: Dict[str, Any],
    dq: Dict[str, Any],
) -> None:
    """
    Ejecuta un grupo de fuentes: extrae, carga, valida y registra métricas.

    Parameters
    ----------
    group : str
        Nombre del grupo a ejecutar (clave en `groups`).
    config : Dict[str, Any]
        Configuración completa de `sources.yml`.
    dq : Dict[str, Any]
        Reglas de `dq.yml`.

    Returns
    -------
    None

    Preconditions
    --------------
    Los adaptadores deben existir y aceptar `params` y `context`.

    Example
    --------
    >>> # run_group("daily", cfg, dq)  # doctest: +SKIP
    """
    defaults = config.get("defaults") or {}
    db_path = defaults.get("db_path", "data/warehouse.duckdb")
    ensure_ledger(db_path)

    group_list = (config.get("groups") or {}).get(group) or []
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    started = datetime.now(timezone.utc)

    rows_total = 0
    metrics_rows: List[Dict[str, Any]] = []
    status = "ok"
    error_msg = None

    for src in group_list:
        name = src["name"]
        typ = src["type"]
        started_src = datetime.now(timezone.utc)
        table = src.get("table", name)
        params = src.get("params") or {}
        ctx = {
            "db_path": db_path,
            "table": table,
            "mode": src.get("mode", defaults.get("mode", "replace")),
        }
        try:
            Adapter = get_adapter(typ)

            mode = src.get("mode", defaults.get("mode", "replace"))
            incr_cfg = src.get("incremental") or {}
            stage_table = None

            if mode == "incremental":
                # 1) cargar a STAGING con el adaptador
                stage_table = f"{table}__stg"
                ctx_inc = {**ctx, "table": stage_table}
                adp = Adapter(params=params, context=ctx_inc)
                stage_name, staged_rows, dur = adp.run()

                # 2) upsert incremental (dedupe + TRY_CAST)
                key_cols = (src.get("incremental") or {}).get("key") or []
                cast_map = (src.get("incremental") or {}).get("cast_map") or {}
                con = duckdb.connect(db_path)
                counters = incremental_upsert(con, stage_name, table, key_cols, cast_map)

                # 3) DQ sobre el LOTE (no sobre la tabla completa)
                #    Si no hay lote, consideramos DQ OK (no hay nada que auditar).
                to_insert_tbl = counters.get("to_insert_table")
                if counters["inserted"] > 0 and to_insert_tbl:
                    df = con.execute(f"SELECT * FROM {to_insert_tbl}").fetchdf()
                    dqres = apply_dq(df, table, dq)
                else:
                    dqres = {"pass": True, "violations": 0, "on_fail": "warn"}

                # 4) export parquet si procede (ya con la tabla actualizada)
                export_cfg = src.get("export_parquet")
                if export_cfg:
                    export_parquet(con, table, export_cfg)

                # 5) limpiar staging y to_insert
                con.execute(f"DROP TABLE IF EXISTS {stage_name}")
                if to_insert_tbl:
                    con.execute(f"DROP TABLE IF EXISTS {to_insert_tbl}")
                con.close()

                table_name = table
                rows_loaded = int(counters["inserted"])
            else:
                # comportamiento actual (replace/append) sin staging
                adp = Adapter(params=params, context=ctx)
                table_name, rows_loaded, dur = adp.run()

                # DQ sobre la tabla cargada (modo no-incremental)
                con = duckdb.connect(db_path)
                df = con.execute(f"SELECT * FROM {table_name}").fetchdf()
                dqres = apply_dq(df, table_name, dq)
                # export parquet si procede
                export_cfg = src.get("export_parquet")
                if export_cfg:
                    export_parquet(con, table_name, export_cfg)
                con.close()


            # on_fail=block → marcar status fail (no interrumpe otras)
            if not dqres["pass"] and (dqres.get("on_fail") == "block"):
                status = "fail"
                error_msg = (
                    "DQ block en {t} (violations={v})"
                    .format(
                        t=table_name,
                        v=dqres["violations"],
                    )
                )

            rows_total += rows_loaded
            finished_src = datetime.now(timezone.utc)
            metrics_rows.append(
                {
                    "run_id": run_id,
                    "source_name": name,
                    "table_name": table_name,
                    "rows_loaded": int(rows_loaded),
                    "duration_s": float(dur),
                    "dq_pass": bool(dqres["pass"]),
                    "dq_violations": int(dqres["violations"]),
                    "loaded_at": finished_src,  # << clave
                }
            )
            print(
                (
                    f"[RUN] {name} → {table_name}: {rows_loaded} filas "
                    f"({dur:.2f}s) DQ pass={dqres['pass']} "
                    f"vio={dqres['violations']}"
                )
            )
        except Exception as e:
            status = "fail"
            error_msg = str(e)
            print(f"[RUN][ERROR] {name}: {e}")

    finished = datetime.now(timezone.utc)
    duration = (finished - started).total_seconds()

    # Guardar ledger
    con = duckdb.connect(db_path)

    if metrics_rows:
        con.register("df_metrics", pd.DataFrame(metrics_rows))
        con.execute(
            """
            INSERT INTO etl_metrics
            SELECT
              run_id,
              source_name,
              table_name,
              rows_loaded,
              duration_s,
              dq_pass,
              dq_violations,
              loaded_at
            FROM df_metrics
            """
        )
    else:
        print("No se insertan métricas (ninguna fuente registró filas/resultado en este run).")

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
            status,
            error_msg,
            len(group_list),
            rows_total,
            duration,
        ],
    )
    con.close()


    # Health JSON
    os.makedirs("data/reports", exist_ok=True)
    with open(
        f"data/reports/health_{run_id}.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            {
                "run_id": run_id,
                "group": group,
                "status": status,
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


def main() -> None:
    """
    Punto de entrada CLI para ejecutar un grupo con DQ y ledger.

    Lee rutas de configuración y ejecuta `run_group`.

    Parameters
    ----------
    None

    Returns
    -------
    None
        Imprime progreso por stdout y escribe métricas/health.

    Preconditions
    --------------
    Rutas `--config` y `--dq` deben ser accesibles.

    Example
    --------
    $ python -m app.runner --group daily
    """
    ap = argparse.ArgumentParser(
        description="ETL Runner (config + DQ + ledger)"
    )
    ap.add_argument(
        "--config",
        default=CONFIG_DEFAULT,
        help="Ruta a sources.yml",
    )
    ap.add_argument(
        "--dq",
        default=DQ_DEFAULT,
        help="Ruta a dq.yml",
    )
    ap.add_argument(
        "--group",
        default="daily",
        help="Grupo a ejecutar (clave en 'groups').",
    )
    args = ap.parse_args()

    cfg = load_yaml(args.config)
    dq = load_yaml(args.dq)
    run_group(args.group, cfg, dq)


if __name__ == "__main__":
    main()
