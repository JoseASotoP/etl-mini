# -*- coding: utf-8 -*-
from __future__ import annotations

"""
USGS Earthquakes: descarga GeoJSON, normaliza y carga a DuckDB + CSV.

Obtiene eventos sísmicos de la API FDSN (USGS) en una ventana de días y
con magnitud mínima, y genera tablas/archivos para análisis rápido.

Parameters
----------
None

Returns
-------
None
    Módulo con punto de entrada CLI.

Preconditions
--------------
Conexión a internet. Carpeta `data/` accesible para crear DB/CSV.

Example
--------
$ python -m app.sources.usgs
$ python -m app.sources.usgs 14 5.0
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pandas as pd


DB_PATH = "data/warehouse.duckdb"
REPORTS_DIR = Path("data/reports")


def _utc_now() -> datetime:
    """
    Devuelve la hora actual en UTC.

    Parameters
    ----------
    None

    Returns
    -------
    datetime.datetime
        Instante actual en UTC.

    Example
    --------
    >>> isinstance(_utc_now(), datetime)  # doctest: +ELLIPSIS
    True
    """
    return datetime.now(timezone.utc)


def _fmt_ts(dt: datetime) -> str:
    """
    Formatea un datetime como 'YYYYmmdd_HHMMSS'.

    Parameters
    ----------
    dt : datetime.datetime
        Fecha/hora de entrada.

    Returns
    -------
    str
        Marca temporal legible.

    Example
    --------
    >>> _fmt_ts(datetime(2024, 1, 1, 0, 0, 0))
    '20240101_000000'
    """
    return dt.strftime("%Y%m%d_%H%M%S")


def fetch_usgs(days: int = 7, minmag: float = 4.0) -> pd.DataFrame:
    """
    Descarga eventos sísmicos recientes desde USGS (GeoJSON).

    Ventana [hoy - days, hoy], con magnitud >= minmag. Devuelve un
    DataFrame ordenado (más reciente primero) si hay fechas.

    Parameters
    ----------
    days : int, default=7
        Días hacia atrás a consultar.
    minmag : float, default=4.0
        Magnitud mínima (Richter).

    Returns
    -------
    pandas.DataFrame
        Columnas: datetime_utc, magnitude, depth_km, latitude, longitude,
        place, event_id, type, status.

    Preconditions
    --------------
    Endpoint: https://earthquake.usgs.gov/fdsnws/event/1/query

    Example
    --------
    >>> df = fetch_usgs(1, 5.0)  # doctest: +SKIP
    """
    end = _utc_now().date()
    start = end - timedelta(days=days)
    base = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    params = {
        "format": "geojson",
        "starttime": start.strftime("%Y-%m-%d"),
        "endtime": end.strftime("%Y-%m-%d"),
        "minmagnitude": str(minmag),
        "orderby": "time",
    }
    url = f"{base}?{urllib.parse.urlencode(params)}"
    print(f"[USGS] GET {url}")

    req = urllib.request.Request(url, headers={"User-Agent": "etl-mini/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.loads(r.read().decode("utf-8"))

    feats = payload.get("features", [])
    rows = []
    for f in feats:
        props = f.get("properties", {}) or {}
        geom = f.get("geometry", {}) or {}
        coords = (geom.get("coordinates") or [None, None, None]) + \
            [None, None, None]
        lon, lat, depth_km = coords[0], coords[1], coords[2]

        # USGS 'time' en ms desde epoch
        t_ms = props.get("time")
        dt_utc = None
        if t_ms is not None:
            dt_utc = datetime.fromtimestamp(
                t_ms / 1000.0, tz=timezone.utc
            ).isoformat()

        rows.append(
            {
                "datetime_utc": dt_utc,
                "magnitude": props.get("mag"),
                "depth_km": depth_km,
                "latitude": lat,
                "longitude": lon,
                "place": props.get("place"),
                "event_id": f.get("id"),
                "type": props.get("type"),
                "status": props.get("status"),
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty and "datetime_utc" in df.columns:
        df = df.sort_values(
            "datetime_utc",
            ascending=False,
            na_position="last",
        ).reset_index(drop=True)
    print(f"[USGS] Filas: {len(df)}")
    return df


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
    `DB_PATH` debe ser accesible.

    Example
    --------
    >>> # load_to_duckdb(df, 'usgs_quakes_7d_m40')  # doctest: +SKIP
    """
    con = duckdb.connect(DB_PATH)
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
        try:
            con.close()
        except Exception:
            pass


def to_csv(df: pd.DataFrame, stem: str) -> Path:
    """
    Escribe `df` a CSV en `data/reports/{stem}_<ts>.csv`.

    Parameters
    ----------
    df : pandas.DataFrame
        Datos a exportar.
    stem : str
        Prefijo base del archivo.

    Returns
    -------
    pathlib.Path
        Ruta del archivo CSV generado.

    Preconditions
    --------------
    `REPORTS_DIR` debe existir o poder crearse.

    Example
    --------
    >>> # to_csv(df, 'usgs_quakes_7d_m40')  # doctest: +SKIP
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / f"{stem}_{_fmt_ts(_utc_now())}.csv"
    df.to_csv(out, index=False)
    return out


def normalize_table_name(days: int, minmag: float) -> str:
    """
    Devuelve un nombre de tabla estable según días y magnitud.

    Parameters
    ----------
    days : int
        Ventana de días.
    minmag : float
        Magnitud mínima.

    Returns
    -------
    str
        Nombre con formato `usgs_quakes_{days}d_m{mag}`.

    Example
    --------
    >>> normalize_table_name(7, 4.0)
    'usgs_quakes_7d_m40'
    """
    mag = str(minmag).replace(".", "")
    return f"usgs_quakes_{days}d_m{mag}"


def main() -> None:
    """
    CLI: descarga, carga y exporta CSV de sismos recientes (USGS).

    Uso
    ---
    python -m app.sources.usgs                # últimos 7 días, M>=4.0
    python -m app.sources.usgs 14 5.0         # últimos 14 días, M>=5.0

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
    days = int(sys.argv[1]) if len(sys.argv) >= 2 else 7
    minmag = float(sys.argv[2]) if len(sys.argv) >= 3 else 4.0

    df = fetch_usgs(days=days, minmag=minmag)
    table = normalize_table_name(days, minmag)
    n = load_to_duckdb(df, table) if not df.empty else 0
    print(f"[USGS] Cargado → tabla: {table} (filas: {n})")
    if n > 0:
        csv_path = to_csv(df, f"usgs_{table}")
        print(f"[USGS] Copia CSV → {csv_path}")


if __name__ == "__main__":
    main()
