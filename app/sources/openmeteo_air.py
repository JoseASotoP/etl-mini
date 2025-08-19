# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Open-Meteo (Air Quality): extracción simple y carga a DuckDB + CSV.

Consulta la API pública de Open-Meteo (sin API key) para variables de
calidad del aire por coordenadas, devuelve un DataFrame y lo exporta.

Parameters
----------
None

Returns
-------
None
    Módulo con punto de entrada CLI.

Preconditions
--------------
Conexión a internet. Carpetas `data/` y `data/reports/` accesibles.

Example
--------
$ python -m app.sources.openmeteo_air 40.4168 -3.7038 pm25 7 madrid
"""

import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd


def _ts() -> str:
    """
    Devuelve timestamp 'YYYYmmdd_HHMMSS' para nombres de archivo.

    Parameters
    ----------
    None

    Returns
    -------
    str
        Marca temporal legible.

    Example
    --------
    >>> isinstance(_ts(), str)
    True
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def fetch(
    lat: str,
    lon: str,
    parameter: str,
    past_days: int = 7,
) -> pd.DataFrame:
    """
    Descarga series horarias de calidad del aire desde Open-Meteo.

    Parameters
    ----------
    lat : str
        Latitud en grados (cadena o convertible a float).
    lon : str
        Longitud en grados (cadena o convertible a float).
    parameter : str
        pm25 | pm10 | no2 | o3 | so2 | co (mapeo interno aplicado).
    past_days : int, default=7
        Días hacia atrás (≈0–92).

    Returns
    -------
    pandas.DataFrame
        Columnas: datetime_utc, value, parameter, latitude, longitude,
        unit.

    Preconditions
    --------------
    La API devuelve µg/m³ para PM y ppb/μg/m³ según variable; se usa
    'µg/m³' como unidad genérica para PM.

    Example
    --------
    >>> df = fetch("40.4168", "-3.7038", "pm25", 1)  # doctest: +SKIP
    """
    param_map = {
        "pm25": "pm2_5",
        "pm2_5": "pm2_5",
        "pm10": "pm10",
        "no2": "nitrogen_dioxide",
        "o3": "ozone",
        "so2": "sulphur_dioxide",
        "co": "carbon_monoxide",
    }
    hourly_key = param_map.get(parameter.lower(), parameter.lower())

    base = "https://air-quality-api.open-meteo.com/v1/air-quality"
    qs = {
        "latitude": lat,
        "longitude": lon,
        "hourly": hourly_key,
        "timezone": "UTC",
        "past_days": str(past_days),
        "forecast_days": "0",
    }
    url = f"{base}?{urllib.parse.urlencode(qs)}"
    print(f"[Open-Meteo] GET {url}")

    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    values = hourly.get(hourly_key, [])

    if not times or not values:
        return pd.DataFrame()

    df = pd.DataFrame(
        {
            "datetime_utc": pd.to_datetime(
                times, utc=True, errors="coerce"
            ),
            "value": values,
        }
    )
    df["parameter"] = parameter.lower()
    df["latitude"] = float(lat)
    df["longitude"] = float(lon)
    df["unit"] = "µg/m³"
    return df


def load_to_duckdb(df: pd.DataFrame, table: str) -> int:
    """
    Carga el DataFrame en DuckDB (CREATE OR REPLACE).

    Parameters
    ----------
    df : pandas.DataFrame
        Datos a cargar (si vacío → 0).
    table : str
        Nombre de la tabla destino.

    Returns
    -------
    int
        Filas totales en la tabla tras la carga.

    Preconditions
    --------------
    Se crea `data/warehouse.duckdb` si no existe.

    Example
    --------
    >>> # load_to_duckdb(df, 'aq_madrid_pm25')  # doctest: +SKIP
    """
    if df is None or df.empty:
        return 0
    Path("data").mkdir(parents=True, exist_ok=True)
    con = duckdb.connect("data/warehouse.duckdb")
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
    CLI: descarga, carga y exporta CSV de Open-Meteo Air Quality.

    Parameters
    ----------
    None

    Returns
    -------
    None
        Imprime progreso y rutas de salida.

    Preconditions
    --------------
    Uso:
      python -m app.sources.openmeteo_air <LAT> <LON> <PARAM> [PAST_DAYS]
      [LABEL]

    Example
    --------
    $ python -m app.sources.openmeteo_air 40.4168 -3.7038 pm25 7 madrid
    """
    if len(sys.argv) < 4:
        print(
            "Uso: python -m app.sources.openmeteo_air <LAT> <LON> <PARAM> "
            "[PAST_DAYS] [LABEL]"
        )
        print(
            "Ej:  python -m app.sources.openmeteo_air 40.4168 -3.7038 pm25 "
            "7 madrid"
        )
        sys.exit(1)

    lat = sys.argv[1]
    lon = sys.argv[2]
    parameter = sys.argv[3]
    past_days = int(sys.argv[4]) if len(sys.argv) >= 5 else 7
    label = (
        sys.argv[5]
        if len(sys.argv) >= 6
        else f"{lat}_{lon}".replace(".", "p").replace("-", "m")
    )

    df = fetch(lat, lon, parameter, past_days=past_days)
    print(f"[Open-Meteo] Filas: {len(df)}")
    if df.empty:
        print("[Open-Meteo] Sin datos.")
        sys.exit(0)

    # Tabla estable: aq_<label>_<param>
    safe_label = "".join(
        ch if ch.isalnum() or ch in "_-" else "_" for ch in label
    ).lower()
    table = f"aq_{safe_label}_{parameter.lower()}"

    n = load_to_duckdb(df, table)
    print(f"[Open-Meteo] Cargado → tabla: {table} (filas: {n})")

    Path("data/reports").mkdir(parents=True, exist_ok=True)
    out_csv = Path("data/reports") / f"openmeteo_{table}_{_ts()}.csv"
    df.to_csv(out_csv, index=False)
    print(f"[Open-Meteo] Copia CSV → {out_csv}")


if __name__ == "__main__":
    main()
