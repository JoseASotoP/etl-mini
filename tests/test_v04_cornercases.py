# -*- coding: utf-8 -*-
"""
POC extendida v0.4.0 – Corner cases
1. Carga incremental con columnas extra (debería funcionar).
2. Filas de varios años para probar particionado.
"""

import duckdb
import os
import shutil
import pandas as pd


def run_cornercases(db_path: str = "data/warehouse.duckdb") -> None:
    con = duckdb.connect(db_path)

    print("=== Paso 1: Crear staging con columnas extra y varios años ===")
    con.execute("DROP TABLE IF EXISTS staging_pm25")
    con.execute("""
        CREATE TABLE staging_pm25 AS
        SELECT 
            datetime_utc,
            value,
            parameter,
            unit,
            latitude,
            longitude,
            'extra_col' AS extra_info  -- columna extra que no existe en destino
        FROM aq_madrid_pm25
        ORDER BY datetime_utc DESC LIMIT 3
    """)

    # Insertar manualmente dos filas nuevas (años distintos, para partición)
    con.execute("""
        INSERT INTO staging_pm25
        (datetime_utc, value, parameter, unit, latitude, longitude, extra_info)
        VALUES
        ('2024-01-01 00:00:00+02:00', 15.0, 'pm25', 'µg/m³', 40.4, -3.7, 'nuevo2024'),
        ('2023-06-15 12:00:00+02:00', 30.0, 'pm25', 'µg/m³', 40.5, -3.8, 'nuevo2023')
    """)

    print(con.execute("SELECT COUNT(*) FROM staging_pm25").fetchone())

    print("\n=== Paso 2: Carga incremental (ignorar duplicados) ===")
    before = con.execute("SELECT COUNT(*) FROM aq_madrid_pm25").fetchone()[0]
    con.execute("""
        INSERT INTO aq_madrid_pm25 (datetime_utc, value, parameter, unit, latitude, longitude)
        SELECT s.datetime_utc, s.value, s.parameter, s.unit, s.latitude, s.longitude
        FROM staging_pm25 s
        LEFT JOIN aq_madrid_pm25 t
        ON s.datetime_utc = t.datetime_utc
        WHERE t.datetime_utc IS NULL
    """)
    after = con.execute("SELECT COUNT(*) FROM aq_madrid_pm25").fetchone()[0]
    print(f"Filas antes: {before}, después: {after}, nuevas: {after - before}")

    print("\n=== Paso 3: Exportar a Parquet particionado por año ===")
    out_dir = "data/parquet/aq_madrid_pm25_corner"
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    con.execute(f"""
        COPY (
            SELECT *, strftime(datetime_utc, '%Y') AS year
            FROM aq_madrid_pm25
        )
        TO '{out_dir}'
        (FORMAT PARQUET, PARTITION_BY (year), OVERWRITE_OR_IGNORE)
    """)
    print(f"Exportado a {out_dir}/")

    print("\n=== Paso 4: Leer particiones de vuelta ===")
    df = con.execute(f"""
        SELECT year(datetime_utc) AS year, COUNT(*) AS filas
        FROM parquet_scan('{out_dir}/*/*.parquet')
        GROUP BY 1 ORDER BY 1
    """).fetchdf()
    print(df)

    con.close()


if __name__ == "__main__":
    run_cornercases()
