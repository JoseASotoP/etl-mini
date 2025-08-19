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
            adp = Adapter(params=params, context=ctx)
            table_name, rows_loaded, dur = adp.run()

            # DQ: validar contra tabla cargada
            con = duckdb.connect(db_path)
            query = f"SELECT * FROM {table_name}"
            df = con.execute(query).fetchdf()
            con.close()
            dqres = apply_dq(df, table_name, dq)
            finished_src = datetime.now(timezone.utc)

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
