# -*- coding: utf-8 -*-
"""
POC v0.4.0 – Stress Test de Producción (~50k filas)

Este test valida:
1. Que la carga incremental funciona con mucho volumen.
2. Que duplicados, NULLs y valores inválidos se descartan.
3. Que la exportación a Parquet particionado (año+mes) mantiene consistencia.
"""

import duckdb
import os
import shutil
import pandas as pd
import numpy as np
import time


def run_stress(db_path: str = "data/warehouse.duckdb") -> None:
    con = duckdb.connect(db_path)

    print("=== Paso 1: Generar dataset sintético (~50k filas) ===")
    n = 50_000
    dates = pd.date_range("2023-01-01", periods=n, freq="h")
    df = pd.DataFrame({
        "datetime_utc": dates,
        "value": np.random.randn(n).round(1) * 10 + 50,
        "parameter": np.repeat("pm25", n),
        "unit": np.repeat("µg/m³", n),
        "latitude": np.random.choice([40.4, 41.4, 42.4], size=n),
        "longitude": np.random.choice([-3.7, -3.6, -3.5], size=n),
    })

    # Inyectar duplicados (5%)
    dup = df.sample(frac=0.05, random_state=42)
    df = pd.concat([df, dup], ignore_index=True)

    # Inyectar NULLs y valores inválidos
    df.loc[df.sample(frac=0.01, random_state=1).index, "datetime_utc"] = None
    df.loc[df.sample(frac=0.005, random_state=2).index, "datetime_utc"] = "INVALID"
    df.loc[df.sample(frac=0.005, random_state=3).index, "value"] = "NaN"

    print(df.head())

    # Cargar staging en DuckDB
    con.execute("CREATE OR REPLACE TABLE staging_stress AS SELECT * FROM df")

    print(f"Filas en staging: {len(df)}")

    # ===============================
    print("\n=== Paso 2: Carga incremental robusta ===")
    before = con.execute("SELECT COUNT(*) FROM aq_madrid_pm25").fetchone()[0]

    t0 = time.time()
    con.execute("""
        INSERT INTO aq_madrid_pm25
        SELECT
            TRY_CAST(datetime_utc AS TIMESTAMP) AS datetime_utc,
            TRY_CAST(value AS DOUBLE) AS value,
            parameter,
            unit,
            latitude,
            longitude
        FROM staging_stress s
        WHERE datetime_utc IS NOT NULL
          AND TRY_CAST(datetime_utc AS TIMESTAMP) IS NOT NULL
          AND TRY_CAST(value AS DOUBLE) IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM aq_madrid_pm25 t
              WHERE t.datetime_utc = TRY_CAST(s.datetime_utc AS TIMESTAMP)
          )
    """)
    t1 = time.time()

    after = con.execute("SELECT COUNT(*) FROM aq_madrid_pm25").fetchone()[0]
    print(f"Filas antes: {before}, después: {after}, nuevas: {after - before}")
    print(f"Tiempo inserción: {t1 - t0:.2f}s")

    # ===============================
    print("\n=== Paso 3: Exportar a Parquet particionado por año+mes ===")
    out_dir = "data/parquet/aq_madrid_pm25_stress"
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    con.execute(f"""
        COPY (
            SELECT *, strftime(TRY_CAST(datetime_utc AS TIMESTAMP), '%Y') AS year,
                      strftime(TRY_CAST(datetime_utc AS TIMESTAMP), '%m') AS month
            FROM aq_madrid_pm25
        )
        TO '{out_dir}/'
        (FORMAT PARQUET, PARTITION_BY (year, month), OVERWRITE_OR_IGNORE 1)
    """)
    print(f"Exportado a {out_dir}/")

    # ===============================
    print("\n=== Paso 4: Validar consistencia ===")
    df_check = con.execute(f"""
        SELECT year, month, COUNT(*) AS filas
        FROM parquet_scan('{out_dir}/**/*.parquet')
        GROUP BY 1,2
        ORDER BY 1,2
    """).fetchdf()

    total_parquet = df_check["filas"].sum()
    print(df_check)
    print(f"Total en Parquet = {total_parquet}, Total en tabla = {after}")

    assert total_parquet == after, "❌ Los conteos no coinciden"

if __name__ == "__main__":
    run_stress()
