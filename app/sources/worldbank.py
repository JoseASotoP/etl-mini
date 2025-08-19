# -*- coding: utf-8 -*-
from __future__ import annotations

"""
World Bank API: descarga de indicadores por país y carga en DuckDB + CSV.

Descarga todas las páginas de un indicador del World Bank para un país,
normaliza columnas y guarda resultados en tabla y CSV.

Parameters
----------
None

Returns
-------
None
    Módulo con punto de entrada CLI.

Preconditions
--------------
Conexión a internet. Estructura `data/` accesible para DB y reportes.

Example
--------
$ python -m app.sources.worldbank ESP SP.POP.TOTL
"""

import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List

import duckdb
import pandas as pd

WAREHOUSE = Path("data/warehouse.duckdb")
REPORTS = Path("data/reports")
REPORTS.mkdir(parents=True, exist_ok=True)
DATA = Path("data")
DATA.mkdir(parents=True, exist_ok=True)


def _wb_url(
    country: str,
    indicator: str,
    page: int = 1,
    per_page: int = 1000,
) -> str:
    """
    Construye una URL de consulta para la API del World Bank.

    Parameters
    ----------
    country : str
        Código ISO3 del país (p. ej., 'ESP').
    indicator : str
        Código del indicador (p. ej., 'SP.POP.TOTL').
    page : int, default=1
        Página a solicitar.
    per_page : int, default=1000
        Filas por página.

    Returns
    -------
    str
        URL lista para consultar.

    Example
    --------
    >>> _wb_url('ESP', 'SP.POP.TOTL')  # doctest: +ELLIPSIS
    'https://api.worldbank.org/...'
    """
    params = {
        "format": "json",
        "page": str(page),
        "per_page": str(per_page),
    }
    base = (
        "https://api.worldbank.org/v2/country/"
        f"{country}/indicator/{indicator}"
    )
    return f"{base}?{urllib.parse.urlencode(params)}"


def fetch_indicator(
    country: str,
    indicator: str,
    per_page: int = 1000,
    sleep_s: float = 0.2,
) -> pd.DataFrame:
    """
    Descarga todas las páginas del indicador para un país.

    Devuelve DataFrame con columnas: year, value, indicator_id, indicator,
    country_id, country.

    Parameters
    ----------
    country : str
        Código ISO3 del país.
    indicator : str
        Código del indicador.
    per_page : int, default=1000
        Filas por página (máximo habitual).
    sleep_s : float, default=0.2
        Pausa entre páginas para evitar rate-limit.

    Returns
    -------
    pandas.DataFrame
        Datos normalizados y tipados.

    Preconditions
    --------------
    La API devuelve un array [meta, rows]. Puede haber varias páginas.

    Example
    --------
    >>> # fetch_indicator('ESP', 'SP.POP.TOTL')  # doctest: +SKIP
    """
    url1 = _wb_url(country, indicator, page=1, per_page=per_page)
    with urllib.request.urlopen(url1) as r:
        payload = json.load(r)

    if not isinstance(payload, list) or len(payload) < 2:
        raise RuntimeError(
            f"Respuesta inesperada del World Bank: {payload!r}"
        )

    meta = payload[0] or {}
    rows = payload[1] or []

    total = int(meta.get("total", len(rows)))
    pages = int(meta.get("pages", 1))
    if pages <= 1 and len(rows) < total and total > 0:
        pages = math.ceil(total / per_page)

    all_rows: List[Dict] = []
    all_rows.extend(rows)

    for page in range(2, pages + 1):
        time.sleep(sleep_s)
        url = _wb_url(country, indicator, page=page, per_page=per_page)
        with urllib.request.urlopen(url) as r:
            p = json.load(r)
        rows_p = p[1] or []
        all_rows.extend(rows_p)

    if not all_rows:
        return pd.DataFrame(
            columns=[
                "year",
                "value",
                "indicator_id",
                "indicator",
                "country_id",
                "country",
            ]
        )

    def _get(d, path, default=None):
        """Acceso seguro a dict con ruta 'a.b.c'."""
        cur = d
        for k in path.split("."):
            if not isinstance(cur, dict) or k not in cur:
                return default
            cur = cur[k]
        return cur

    data = []
    for rec in all_rows:
        data.append(
            {
                "year": _get(rec, "date"),
                "value": _get(rec, "value"),
                "indicator_id": _get(rec, "indicator.id"),
                "indicator": _get(rec, "indicator.value"),
                "country_id": _get(rec, "country.id"),
                "country": _get(rec, "country.value"),
            }
        )

    df = pd.DataFrame(data)
    # Tipos
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


def _table_name(country: str, indicator: str) -> str:
    """
    Genera nombre de tabla estable para DuckDB.

    Parameters
    ----------
    country : str
        Código ISO3.
    indicator : str
        Código del indicador.

    Returns
    -------
    str
        Nombre con formato `wb_<pais>_<indicador>`.

    Example
    --------
    >>> _table_name('ESP', 'SP.POP.TOTL')
    'wb_esp_sp_pop_totl'
    """
    return f"wb_{country.lower()}_{indicator.lower().replace('.', '_')}"


def load_to_duckdb(df: pd.DataFrame, table: str) -> int:
    """
    Carga el DataFrame en DuckDB (CREATE OR REPLACE) y devuelve filas.

    Parameters
    ----------
    df : pandas.DataFrame
        Datos a cargar.
    table : str
        Tabla destino.

    Returns
    -------
    int
        Filas en la tabla tras la carga.

    Preconditions
    --------------
    `WAREHOUSE` debe existir o poder crearse.

    Example
    --------
    >>> # load_to_duckdb(df, 'wb_esp_sp_pop_totl')  # doctest: +SKIP
    """
    WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE))
    try:
        con.register("df_tmp", df)
        con.execute(
            f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM df_tmp"
        )
        n = con.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]
        return int(n)
    finally:
        con.close()


def main() -> None:
    """
    CLI: descarga indicador, carga a DuckDB y exporta CSV.

    Uso
    ---
    python -m app.sources.worldbank <PAIS_ISO3> <INDICADOR>
    ej.: python -m app.sources.worldbank ESP SP.POP.TOTL

    Parameters
    ----------
    None

    Returns
    -------
    None
        Imprime progreso y rutas de salida.

    Preconditions
    --------------
    Conexión a internet y permisos de escritura en `data/`.
    """
    if len(sys.argv) < 3:
        print(
            "Uso: python -m app.sources.worldbank <PAIS_ISO3> <INDICADOR>"
        )
        print(
            "Ejemplo: python -m app.sources.worldbank ESP SP.POP.TOTL"
        )
        sys.exit(2)

    country = sys.argv[1].strip()
    indicator = sys.argv[2].strip()

    print(f"[WB] Descargando {indicator} para {country} ...")
    df = fetch_indicator(country, indicator)
    print(f"[WB] Filas descargadas: {len(df)}")

    table = _table_name(country, indicator)
    n = load_to_duckdb(df, table)

    ts = time.strftime("%Y%m%d_%H%M%S")
    csv_path = REPORTS / f"worldbank_{table}_{ts}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8")

    print(f"[WB] Cargado en DuckDB → tabla: {table} (filas: {n})")
    print(f"[WB] Copia CSV → {csv_path}")


if __name__ == "__main__":
    main()
