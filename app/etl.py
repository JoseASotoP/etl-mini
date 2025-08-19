# -*- coding: utf-8 -*-
from __future__ import annotations

"""
ETL-mini: extracción de fuentes (csv/xlsx/json/api) y carga a DuckDB.

Este módulo implementa utilidades de logging, estado incremental, mapeo
de tipos a DuckDB y modos de carga (replace/append/upsert), además de la
ejecución directa, por lotes o programada.

Parameters
----------
None

Returns
-------
None
    Módulo con punto de entrada CLI.

Preconditions
--------------
Estructura de carpetas en `data/` accesible. Configuración en
`config/settings.toml` válida. Fuentes definidas por `source_from_dict`.

Example
--------
$ python -m app.etl --only my_source
$ python -m app.etl --schedule
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
import argparse
import json
import time
import logging
import sys

import duckdb
import pandas as pd

try:
    import tomllib  # py3.11+
except Exception:
    import tomli as tomllib  # fallback

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except Exception:
    BackgroundScheduler = None  # scheduler opcional

from .sources import source_from_dict, BaseSource


# ------------------------------ Utilidades ---------------------------------

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
INPUT = DATA / "input"
REPORTS = DATA / "reports"
PLOTS = DATA / "plots"
STATE = DATA / "state"

REPORTS.mkdir(parents=True, exist_ok=True)
PLOTS.mkdir(parents=True, exist_ok=True)
STATE.mkdir(parents=True, exist_ok=True)


def get_logger() -> logging.Logger:
    """
    Crea/recupera logger para la ejecución de ETL.

    Configura logger con salida a archivo por run y a stdout.

    Parameters
    ----------
    None

    Returns
    -------
    logging.Logger
        Instancia de logger con formato estándar.

    Preconditions
    --------------
    La carpeta `data/reports` debe existir o poder crearse.

    Example
    --------
    >>> log = get_logger()  # doctest: +SKIP
    """
    logger = logging.getLogger("etl")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    ts = time.strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(REPORTS / f"run_{ts}.log", encoding="utf-8")
    ch = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


log = get_logger()


def load_settings() -> Dict[str, Any]:
    """
    Carga configuración desde `config/settings.toml`.

    Parameters
    ----------
    None

    Returns
    -------
    Dict[str, Any]
        Diccionario con la configuración.

    Preconditions
    --------------
    Debe existir `config/settings.toml` con formato TOML válido.

    Example
    --------
    >>> cfg = load_settings()  # doctest: +SKIP
    """
    cfg_path = ROOT / "config" / "settings.toml"
    with cfg_path.open("rb") as f:
        return tomllib.load(f)


def save_health(health: Dict[str, Any]) -> None:
    """
    Guarda un resumen de salud/estado en JSON.

    Parameters
    ----------
    health : Dict[str, Any]
        Mapa con métricas de ejecución por fuente.

    Returns
    -------
    None

    Preconditions
    --------------
    La carpeta `data/reports` debe ser escribible.

    Example
    --------
    >>> save_health({"src": {"ok": True}})  # doctest: +SKIP
    """
    out = REPORTS / "health.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(health, f, ensure_ascii=False, indent=2)


def read_state(name: str) -> Dict[str, Any]:
    """
    Lee estado incremental de una fuente desde `data/state`.

    Parameters
    ----------
    name : str
        Nombre de la fuente para componer el archivo `<name>.json`.

    Returns
    -------
    Dict[str, Any]
        Estado previo, o dict vacío si no existe.

    Preconditions
    --------------
    Los archivos de estado se guardan como JSON UTF-8.

    Example
    --------
    >>> read_state("my_source")  # doctest: +SKIP
    {}
    """
    p = STATE / f"{name}.json"
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_state(name: str, d: Dict[str, Any]) -> None:
    """
    Escribe el estado incremental para una fuente.

    Parameters
    ----------
    name : str
        Nombre base del archivo de estado.
    d : Dict[str, Any]
        Contenido de estado (p. ej., since_value).

    Returns
    -------
    None

    Preconditions
    --------------
    La carpeta `data/state` debe existir o poder crearse.

    Example
    --------
    >>> write_state("my_source", {"since_value": "2024-01-01"})  # doctest: +SKIP
    """
    p = STATE / f"{name}.json"
    with p.open("w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


# ------------------------------ Carga a DuckDB ------------------------------


def ensure_table_exists(
    con: duckdb.DuckDBPyConnection,
    table: str,
    df: pd.DataFrame,
) -> None:
    """
    Crea tabla si no existe con esquema derivado del DataFrame.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Conexión abierta a DuckDB.
    table : str
        Nombre de la tabla destino.
    df : pandas.DataFrame
        Datos origen para inferir tipos.

    Returns
    -------
    None

    Preconditions
    --------------
    La conexión debe estar abierta y con permisos de creación.

    Example
    --------
    >>> # ensure_table_exists(con, "mi_tabla", df)  # doctest: +SKIP
    """
    cols = ", ".join(
        f"{c} {duckdb_type_for(df[c])}" for c in df.columns
    )
    con.execute(f"CREATE TABLE IF NOT EXISTS {table} ({cols})")


def duckdb_type_for(series: pd.Series) -> str:
    """
    Mapea dtype de pandas a tipo SQL de DuckDB.

    Parameters
    ----------
    series : pandas.Series
        Serie a mapear.

    Returns
    -------
    str
        Tipo SQL de DuckDB (BIGINT, DOUBLE, BOOLEAN, TIMESTAMP, TEXT).

    Preconditions
    --------------
    Se asume que `series` tiene dtype válido de pandas.

    Example
    --------
    >>> duckdb_type_for(pd.Series([1, 2]))  # doctest: +ELLIPSIS
    'BIGINT'
    """
    if pd.api.types.is_integer_dtype(series):
        return "BIGINT"
    if pd.api.types.is_float_dtype(series):
        return "DOUBLE"
    if pd.api.types.is_bool_dtype(series):
        return "BOOLEAN"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "TIMESTAMP"
    return "TEXT"


def load_replace(
    con,
    df: pd.DataFrame,
    table: str,
) -> int:
    """
    Reemplaza completamente el contenido de una tabla con `df`.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Conexión a DuckDB.
    df : pandas.DataFrame
        Datos a cargar.
    table : str
        Tabla destino.

    Returns
    -------
    int
        Número de filas cargadas.

    Preconditions
    --------------
    Permisos de creación/escritura en la tabla destino.

    Example
    --------
    >>> # load_replace(con, df, "mi_tabla")  # doctest: +SKIP
    """
    con.register("df_tmp", df)
    con.execute(
        f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM df_tmp"
    )
    return len(df)


def load_append(
    con,
    df: pd.DataFrame,
    table: str,
) -> int:
    """
    Inserta las filas de `df` al final de la tabla destino.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Conexión a DuckDB.
    df : pandas.DataFrame
        Datos a agregar.
    table : str
        Tabla destino.

    Returns
    -------
    int
        Filas insertadas.

    Preconditions
    --------------
    La tabla debe existir o se crea con `ensure_table_exists`.

    Example
    --------
    >>> # load_append(con, df, "mi_tabla")  # doctest: +SKIP
    """
    ensure_table_exists(con, table, df)
    con.register("df_tmp", df)
    con.execute("INSERT INTO {t} SELECT * FROM df_tmp".format(t=table))
    return len(df)


def load_upsert(
    con,
    df: pd.DataFrame,
    table: str,
    key_columns: List[str],
) -> int:
    """
    UPSERT por columnas clave: UPDATE si coincide, INSERT si no.

    Si no hay claves válidas, hace fallback a `load_replace`.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Conexión a DuckDB.
    df : pandas.DataFrame
        Datos origen.
    table : str
        Tabla destino.
    key_columns : List[str]
        Columnas clave para coincidencia.

    Returns
    -------
    int
        Filas procesadas (len(df)).

    Preconditions
    --------------
    Las columnas clave deben existir en `df`. Requiere permisos de
    MERGE/UPDATE/INSERT.

    Example
    --------
    >>> # load_upsert(con, df, "mi_tabla", ["id"])  # doctest: +SKIP
    """
    if not key_columns:
        return load_replace(con, df, table)

    ensure_table_exists(con, table, df)
    con.register("df_tmp", df)

    cols = list(df.columns)
    on_clause = " AND ".join(
        [f"t.{k}=s.{k}" for k in key_columns if k in cols]
    )
    if not on_clause:
        return load_replace(con, df, table)

    set_clause = ", ".join(
        [f"{c}=s.{c}" for c in cols if c not in key_columns]
    )
    insert_cols = ", ".join(cols)
    insert_vals = ", ".join([f"s.{c}" for c in cols])

    sql = f"""
    MERGE INTO {table} AS t
    USING df_tmp AS s
    ON {on_clause}
    WHEN MATCHED THEN UPDATE SET {set_clause}
    WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals})
    """
    con.execute(sql)
    return len(df)


def load_df(
    con,
    df: pd.DataFrame,
    table: str,
    mode: str,
    key_columns: Optional[List[str]],
) -> int:
    """
    Carga `df` según el modo: replace | append | upsert.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Conexión a DuckDB.
    df : pandas.DataFrame
        Datos de entrada.
    table : str
        Tabla destino.
    mode : str
        Modo de carga ("replace", "append" o "upsert").
    key_columns : Optional[List[str]]
        Claves para upsert (puede ser None).

    Returns
    -------
    int
        Filas afectadas.

    Preconditions
    --------------
    `df` puede estar vacío; en tal caso no se carga nada.

    Example
    --------
    >>> # load_df(con, df, "t", "append", None)  # doctest: +SKIP
    """
    if df is None or df.empty:
        return 0
    if mode == "append":
        return load_append(con, df, table)
    if mode == "upsert":
        return load_upsert(con, df, table, key_columns or [])
    return load_replace(con, df, table)


# --------------------------------- ETL run ----------------------------------


def run_source(
    con,
    source_cfg: Dict[str, Any],
    health: Dict[str, Any],
) -> None:
    """
    Ejecuta extracción/carga para una fuente concreta y actualiza salud.

    Inyecta `since_value` desde estado previo si aplica, extrae datos,
    carga según el modo configurado y persiste nuevo estado.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Conexión a DuckDB.
    source_cfg : Dict[str, Any]
        Configuración de la fuente (name, target_table, load_mode, etc.).
    health : Dict[str, Any]
        Mapa de resultados a rellenar.

    Returns
    -------
    None

    Preconditions
    --------------
    La fuente debe ser construible por `source_from_dict`.

    Example
    --------
    >>> # run_source(con, cfg, {})  # doctest: +SKIP
    """
    src = source_from_dict(source_cfg)
    name = src.source_name()
    t0 = time.time()
    try:
        if src.since_field:
            prev = read_state(name)
            if prev.get("since_value") and not src.since_value:
                source_cfg["since_value"] = prev["since_value"]
                # recrea con since_value inyectado
                src = source_from_dict(source_cfg)

        df, new_since = src.extract(STATE)
        rows = load_df(
            con,
            df,
            src.target_table,
            src.load_mode,
            src.key_columns,
        )

        if new_since:
            write_state(name, {"since_value": new_since})

        health[name] = {
            "ok": True,
            "rows": int(rows),
            "table": src.target_table,
            "mode": src.load_mode,
            "since_field": src.since_field,
            "since_value": new_since or source_cfg.get("since_value"),
            "t_sec": round(time.time() - t0, 3),
        }
        log.info(
            f"✓ {name} → {src.target_table} [{src.load_mode}] "
            f"({rows} filas)"
        )
    except Exception as e:
        health[name] = {
            "ok": False,
            "error": str(e),
            "t_sec": round(time.time() - t0, 3),
        }
        log.exception("✗ %s falló", name)


def run_all(
    sources_cfg: List[Dict[str, Any]],
    warehouse_path: str,
) -> Dict[str, Any]:
    """
    Ejecuta en serie todas las fuentes y guarda `health.json`.

    Parameters
    ----------
    sources_cfg : List[Dict[str, Any]]
        Lista de configuraciones de fuente.
    warehouse_path : str
        Ruta al archivo DuckDB.

    Returns
    -------
    Dict[str, Any]
        Mapa de salud por fuente.

    Preconditions
    --------------
    Todas las fuentes deben ser válidas para `source_from_dict`.

    Example
    --------
    >>> # run_all(cfg["sources"], "data/warehouse.duckdb")  # doctest: +SKIP
    """
    health: Dict[str, Any] = {}
    con = duckdb.connect(warehouse_path)
    try:
        for s in sources_cfg:
            run_source(con, s, health)
    finally:
        con.close()
    save_health(health)
    return health


# --------------------------------- Scheduler --------------------------------


def schedule_all(
    sources_cfg: List[Dict[str, Any]],
    warehouse_path: str,
    default_every: int,
) -> None:
    """
    Programa todas las fuentes con intervalos en minutos.

    Crea un job por fuente que abre/cierra conexión por ejecución y
    actualiza `health.json` de forma incremental.

    Parameters
    ----------
    sources_cfg : List[Dict[str, Any]]
        Configuraciones de fuentes a programar.
    warehouse_path : str
        Ruta a la base DuckDB.
    default_every : int
        Minutos por defecto entre ejecuciones.

    Returns
    -------
    None

    Preconditions
    --------------
    Requiere `apscheduler` instalado. El proceso se mantiene en bucle
    hasta `KeyboardInterrupt`.

    Example
    --------
    >>> # schedule_all(sources, "data/warehouse.duckdb", 60)  # doctest: +SKIP
    """
    if BackgroundScheduler is None:
        raise RuntimeError(
            "APScheduler no instalado. Instala: pip install apscheduler"
        )
    sched = BackgroundScheduler()
    sched.start()
    log.info("Scheduler iniciado.")

    def make_job(scfg: Dict[str, Any]):
        """Cierra sobre configuración y ejecuta una única fuente."""
        def _job():
            con = duckdb.connect(warehouse_path)
            try:
                health: Dict[str, Any] = {}
                run_source(con, scfg, health)
                hx = REPORTS / "health.json"
                if hx.exists():
                    try:
                        cur = json.loads(
                            hx.read_text(encoding="utf-8")
                        )
                    except Exception:
                        cur = {}
                else:
                    cur = {}
                cur.update(health)
                save_health(cur)
            finally:
                con.close()
        return _job

    for s in sources_cfg:
        every = int(s.get("every_minutes") or default_every or 60)
        name = s.get("name") or s.get("target_table")
        sched.add_job(
            make_job(s),
            "interval",
            minutes=every,
            id=str(name),
            replace_existing=True,
        )
        log.info("Programada fuente '%s' cada %s min.", name, every)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Deteniendo scheduler…")
        sched.shutdown(wait=False)


# ----------------------------------- CLI ------------------------------------


def main():
    """
    Punto de entrada CLI para ejecuciones únicas o programadas.

    Lee configuración, permite filtrar por `--only` o activar `--schedule`
    y al final informa del estado de fuentes OK y con error.

    Parameters
    ----------
    None

    Returns
    -------
    None
        Imprime logs y termina con código de proceso por `sys.exit`
        cuando aplica.

    Preconditions
    --------------
    Debe existir `config/settings.toml` con secciones `warehouse`,
    `sources` y opcionalmente `schedule`.

    Example
    --------
    $ python -m app.etl
    """
    cfg = load_settings()
    warehouse_path = cfg.get(
        "warehouse", {}
    ).get("path", "data/warehouse.duckdb")
    sources_cfg: List[Dict[str, Any]] = cfg.get("sources", [])
    default_every = int(cfg.get("schedule", {}).get("every_minutes", 60))

    parser = argparse.ArgumentParser(
        description="ETL-mini con fuentes (csv/xlsx/json/api)"
    )
    parser.add_argument(
        "--only",
        type=str,
        help="Ejecutar solo una fuente por nombre",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Ejecutar en modo programado",
    )
    args = parser.parse_args()

    if args.only:
        filt = [
            s
            for s in sources_cfg
            if (s.get("name") or s.get("target_table")) == args.only
        ]
        if not filt:
            log.error("No existe fuente con nombre '%s'", args.only)
            sys.exit(2)
        run_all(filt, warehouse_path)
        return

    if args.schedule:
        log.info("Modo programado (Ctrl+C para parar)")
        schedule_all(sources_cfg, warehouse_path, default_every)
        return

    health = run_all(sources_cfg, warehouse_path)
    log.info("ETL finalizado.")

    ok = [k for k, v in health.items() if v.get("ok")]
    bad = [k for k, v in health.items() if not v.get("ok")]
    if ok:
        log.info("Fuentes OK: " + ", ".join(ok))
    if bad:
        log.warning("Fuentes con error: " + ", ".join(bad))


if __name__ == "__main__":
    main()
