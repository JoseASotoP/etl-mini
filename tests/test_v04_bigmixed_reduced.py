# -*- coding: utf-8 -*-
"""
POC v0.4.0 – Big Mixed Reduced
--------------------------------
Test de integración reducido pero realista que cubre:
1. Población con duplicados, enteros y strings inválidos.
2. Series temporales de contaminación (PM2.5) con nulos y duplicados.
3. Exportación a Parquet particionado (año+mes).
4. Validación de consistencia: tabla vs. Parquet.

Es la versión reducida del stress test "Big Mixed".
"""

import duckdb
import pandas as pd
import os, shutil, time


def run_bigmixed_reduced(db_path: str = "data/warehouse.duckdb") -> None:
    con = duckdb.connect(db_path)

    # === BLOQUE 1: POBLACIÓN (year + value) ===
    print("\n=== POBLACIÓN: staging con enteros, duplicados y strings ===")
    pop_data = pd.DataFrame({
        "year": [2019, 2023, 2025, 2025, "XXXX"],
        "value": [47000000, 48347910, 49000000, 49000000, "INVALID"],
        "indicator_id": ["SP.POP.TOTL"] * 5,
    })
    print(pop_data)

    con.register("pop_view", pop_data)
    before = con.execute("SELECT COUNT(*) FROM wb_esp_sp_pop_totl").fetchone()[0]

    con.execute("""
        INSERT INTO wb_esp_sp_pop_totl
        SELECT TRY_CAST(s.year AS INT), TRY_CAST(s.value AS BIGINT), s.indicator_id
        FROM pop_view s
        LEFT JOIN wb_esp_sp_pop_totl t ON TRY_CAST(s.year AS INT) = t.year
        WHERE t.year IS NULL
          AND TRY_CAST(s.year AS INT) IS NOT NULL
    """)
    after = con.execute("SELECT COUNT(*) FROM wb_esp_sp_pop_totl").fetchone()[0]
    print(f"Filas antes: {before}, después: {after}, nuevas: {after - before}")

    print(con.execute("SELECT * FROM wb_esp_sp_pop_totl ORDER BY year DESC LIMIT 5").fetchdf())

    # === BLOQUE 2: CONTAMINACIÓN (datetime_utc + value) ===
    print("\n=== PM25: staging con nulos, duplicados y strings ===")
    pm_data = pd.DataFrame({
        "datetime_utc": [
            "2025-08-20 03:00:00+02:00",
            "2025-08-20 03:00:00+02:00",  # duplicado exacto
            None,                         # NULL
            "INVALID",                    # string inválido
        ],
        "value": [15.0, 15.0, 20.0, "BAD"],
        "parameter": ["pm25"] * 4,
        "unit": ["µg/m³"] * 4,
        "latitude": [40.4, 40.4, 40.5, 40.5],
        "longitude": [-3.7, -3.7, -3.8, -3.8],
    })
    print(pm_data)

    # Registrar el DataFrame como vista en DuckDB
    con.register("pm25_view", pm_data)

    before = con.execute("SELECT COUNT(*) FROM aq_madrid_pm25").fetchone()[0]

    con.execute("""
        INSERT INTO aq_madrid_pm25
        SELECT
            TRY_CAST(s.datetime_utc AS TIMESTAMP),
            TRY_CAST(s.value AS DOUBLE),
            s.parameter,
            s.unit,
            TRY_CAST(s.latitude AS DOUBLE),
            TRY_CAST(s.longitude AS DOUBLE)
        FROM pm25_view s
        LEFT JOIN aq_madrid_pm25 t
        ON TRY_CAST(s.datetime_utc AS TIMESTAMP) = t.datetime_utc
        WHERE t.datetime_utc IS NULL
          AND TRY_CAST(s.datetime_utc AS TIMESTAMP) IS NOT NULL
    """)

    after = con.execute("SELECT COUNT(*) FROM aq_madrid_pm25").fetchone()[0]
    print(f"Filas antes: {before}, después: {after}, nuevas: {after - before}")

    print(con.execute("SELECT * FROM aq_madrid_pm25 ORDER BY datetime_utc DESC LIMIT 5").fetchdf())

    # === BLOQUE 3: EXPORTACIÓN A PARQUET (multi-columna) ===
    print("\n=== EXPORTAR a Parquet particionado por año+mes ===")
    out_dir = "data/parquet/bigmixed_reduced"
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)

    start = time.time()
    con.execute(f"""
        COPY (
            SELECT *, 
                   strftime(datetime_utc, '%Y') AS year,
                   strftime(datetime_utc, '%m') AS month
            FROM aq_madrid_pm25
        ) TO '{out_dir}' (FORMAT PARQUET, PARTITION_BY (year, month))
    """)
    print(f"Exportado a {out_dir}/ en {time.time() - start:.2f}s")

    # === BLOQUE 4: VALIDACIÓN CONSISTENCIA ===
    print("\n=== VALIDAR consistencia Parquet vs. tabla ===")
    df_check = con.execute(f"""
        SELECT year, month, COUNT(*) AS filas
        FROM parquet_scan('{out_dir}/**/*.parquet')
        GROUP BY 1,2
        ORDER BY 1,2
    """).fetchdf()

    total_parquet = df_check["filas"].sum()
    total_table = con.execute("SELECT COUNT(*) FROM aq_madrid_pm25").fetchone()[0]

    print(df_check.head())
    print(f"Total en Parquet = {total_parquet}, Total en tabla = {total_table}")

    assert total_parquet == total_table, "❌ Los conteos no coinciden"

    con.close()


if __name__ == "__main__":
    run_bigmixed_reduced()
