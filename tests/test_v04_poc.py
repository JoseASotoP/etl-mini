# -*- coding: utf-8 -*-
"""
POC v0.4.0 – Incremental + Particionado en DuckDB

Este test valida:
1. Que podemos hacer carga incremental (evitar duplicados).
2. Que podemos exportar a Parquet con partición por año y leerlo de vuelta.
"""

import duckdb
import os
import shutil
import pandas as pd


def run_poc(db_path: str = "data/warehouse.duckdb") -> None:
    con = duckdb.connect(db_path)

    print("=== Paso 1: Crear staging con lote simulado ===")
    con.execute("""
        CREATE OR REPLACE TABLE staging_pm25 AS
        SELECT * FROM aq_madrid_pm25
        ORDER BY datetime_utc DESC LIMIT 5
    """)
    con.execute("""
        INSERT INTO staging_pm25 (datetime_utc, value)
        VALUES ('2025-08-20 00:00:00+02:00', 25.0)
    """)
    print(con.execute("SELECT COUNT(*) FROM staging_pm25").fetchone())

    print("\n=== Paso 2: Carga incremental (sin duplicados) ===")
    before = con.execute("SELECT COUNT(*) FROM aq_madrid_pm25").fetchone()[0]
    con.execute("""
        INSERT INTO aq_madrid_pm25
        SELECT s.*
        FROM staging_pm25 s
        LEFT JOIN aq_madrid_pm25 t
        ON s.datetime_utc = t.datetime_utc
        WHERE t.datetime_utc IS NULL
    """)
    after = con.execute("SELECT COUNT(*) FROM aq_madrid_pm25").fetchone()[0]
    print(f"Filas antes: {before}, después: {after}, nuevas: {after - before}")

    print("\n=== Paso 3: Exportar a Parquet particionado por año ===")
    out_dir = "data/parquet/aq_madrid_pm25"
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)  # 🔥 limpia antes de exportar
    os.makedirs(out_dir, exist_ok=True)

    con.execute(f"""
        COPY (
            SELECT *, strftime(datetime_utc::timestamp, '%Y') AS year
            FROM aq_madrid_pm25
        )
        TO '{out_dir}/'
        (FORMAT PARQUET, PARTITION_BY (year))
    """)
    print(f"Exportado a {out_dir}/")

    print("\n=== Paso 4: Leer particiones de vuelta ===")
    df = con.execute(f"""
        SELECT year, COUNT(*) AS filas
        FROM parquet_scan('{out_dir}/**/*.parquet')
        GROUP BY 1 ORDER BY 1
    """).fetchdf()
    print(df)

    con.close()


if __name__ == "__main__":
    run_poc()
