# -*- coding: utf-8 -*-
"""
POC v0.4.0 – Test BigMixed Full

Prueba de fuego:
1. Datos sintéticos masivos (~100k filas).
2. Población (enteros/strings/duplicados/invalid).
3. Contaminación (timestamps/nulls/strings/duplicados).
4. Incremental robusto + Exportación Parquet particionada.
"""

import duckdb
import pandas as pd
import numpy as np
import os
import shutil
import time


def run_bigmixed_full(db_path: str = "data/warehouse.duckdb") -> None:
    con = duckdb.connect(db_path)

    # === BLOQUE 1: POBLACIÓN ===
    print("\n=== POBLACIÓN: staging con enteros, strings, duplicados ===")

    pop_data = pd.DataFrame({
        "year": ["2019", "2023", "2025", "2025", "XXXX", "2026"],
        "value": ["47000000", 48347910, "INVALID", 49000000, 50000000, "51000000"],
        "indicator_id": ["SP.POP.TOTL"] * 6,
        "extra_col": ["noise"] * 6  # columna extra que no existe en destino
    })

    print(pop_data)

    con.register("pop_view", pop_data)
    before = con.execute("SELECT COUNT(*) FROM wb_esp_sp_pop_totl").fetchone()[0]

    con.execute("""
        INSERT INTO wb_esp_sp_pop_totl
        SELECT
            TRY_CAST(s.year AS INTEGER),
            TRY_CAST(s.value AS BIGINT),
            s.indicator_id
        FROM pop_view s
        LEFT JOIN wb_esp_sp_pop_totl t
        ON TRY_CAST(s.year AS INTEGER) = t.year
        WHERE t.year IS NULL
          AND TRY_CAST(s.year AS INTEGER) IS NOT NULL
    """)

    after = con.execute("SELECT COUNT(*) FROM wb_esp_sp_pop_totl").fetchone()[0]
    print(f"Filas antes: {before}, después: {after}, nuevas: {after - before}")

    print(con.execute("""
        SELECT * FROM wb_esp_sp_pop_totl ORDER BY year DESC LIMIT 5
    """).fetchdf())

    # === BLOQUE 2: CONTAMINACIÓN ===
    print("\n=== PM25: staging masivo con nulos, duplicados y ruido ===")

    n = 100000
    dates = pd.date_range("2023-01-01", periods=n, freq="h")

    pm_data = pd.DataFrame({
        "datetime_utc": dates.astype(str),
        "value": np.random.randint(5, 200, size=n).astype(str),
        "parameter": ["pm25"] * n,
        "unit": ["µg/m³"] * n,
        "latitude": np.random.uniform(40.3, 40.5, size=n),
        "longitude": np.random.uniform(-3.8, -3.6, size=n),
        "extra_noise": np.random.choice(["A", "B", "C"], size=n)
    })

    # introducir errores
    pm_data.loc[::5000, "datetime_utc"] = None
    pm_data.loc[::7000, "datetime_utc"] = "INVALID"
    pm_data.loc[::8000, "value"] = "NaN"

    print(pm_data.head())

    con.register("pm_view", pm_data)
    before = con.execute("SELECT COUNT(*) FROM aq_madrid_pm25").fetchone()[0]

    t0 = time.time()
    con.execute("""
        INSERT INTO aq_madrid_pm25
        SELECT
            TRY_CAST(s.datetime_utc AS TIMESTAMP),
            TRY_CAST(s.value AS DOUBLE),
            s.parameter,
            s.unit,
            TRY_CAST(s.latitude AS DOUBLE),
            TRY_CAST(s.longitude AS DOUBLE)
        FROM pm_view s
        LEFT JOIN aq_madrid_pm25 t
        ON TRY_CAST(s.datetime_utc AS TIMESTAMP) = t.datetime_utc
        WHERE t.datetime_utc IS NULL
          AND TRY_CAST(s.datetime_utc AS TIMESTAMP) IS NOT NULL
    """)
    t1 = time.time()

    after = con.execute("SELECT COUNT(*) FROM aq_madrid_pm25").fetchone()[0]
    print(f"Filas antes: {before}, después: {after}, nuevas: {after - before}, tiempo: {t1-t0:.2f}s")

    print(con.execute("""
        SELECT * FROM aq_madrid_pm25 ORDER BY datetime_utc DESC LIMIT 5
    """).fetchdf())

    # === BLOQUE 3: EXPORTACIÓN PARQUET ===
    print("\n=== EXPORTAR Parquet particionado ===")

    out_dir = "data/parquet/bigmixed_full"
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)

    os.makedirs(out_dir, exist_ok=True)

    # población por año
    con.execute(f"""
        COPY wb_esp_sp_pop_totl TO '{out_dir}/pop/'
        (FORMAT PARQUET, PARTITION_BY (year), OVERWRITE_OR_IGNORE TRUE)
    """)

    # pm25 por año+mes
    con.execute(f"""
        COPY (
            SELECT *, strftime(TRY_CAST(datetime_utc AS TIMESTAMP), '%Y') AS year,
                      strftime(TRY_CAST(datetime_utc AS TIMESTAMP), '%m') AS month
            FROM aq_madrid_pm25
        ) TO '{out_dir}/pm25/'
        (FORMAT PARQUET, PARTITION_BY (year, month), OVERWRITE_OR_IGNORE TRUE)
    """)

    print(f"Exportado a {out_dir}/")

    # === BLOQUE 4: VALIDACIÓN ===
    print("\n=== VALIDACIÓN ===")

    df_pop = con.execute(f"""
        SELECT year, COUNT(*) AS filas
        FROM parquet_scan('{out_dir}/pop/**/*.parquet')
        GROUP BY 1 ORDER BY 1
    """).fetchdf()

    df_pm = con.execute(f"""
        SELECT year, month, COUNT(*) AS filas
        FROM parquet_scan('{out_dir}/pm25/**/*.parquet')
        GROUP BY 1,2 ORDER BY 1,2
    """).fetchdf()

    total_pop = df_pop["filas"].sum()
    total_pm = df_pm["filas"].sum()

    print("POBLACIÓN (parquet):")
    print(df_pop)
    print("PM25 (parquet):")
    print(df_pm.head(10))

    real_pop = con.execute("SELECT COUNT(*) FROM wb_esp_sp_pop_totl").fetchone()[0]
    real_pm = con.execute("SELECT COUNT(*) FROM aq_madrid_pm25").fetchone()[0]

    print(f"Total población parquet={total_pop}, tabla={real_pop}")
    print(f"Total PM25 parquet={total_pm}, tabla={real_pm}")

    assert total_pop == real_pop, "❌ Diferencia en población parquet vs tabla"
    assert total_pm == real_pm, "❌ Diferencia en PM25 parquet vs tabla"

    print("✅ Test BigMixed Full completado correctamente")

    con.close()


if __name__ == "__main__":
    run_bigmixed_full()
