# -*- coding: utf-8 -*-
"""
POC v0.4.0 – Corner case: NULLs e inválidos en clave

Este test valida:
1. Que filas con `NULL` o `INVALID` en la clave se ignoran automáticamente.
2. Que las demás filas válidas sí se insertan de forma incremental.
"""

import duckdb
import pandas as pd


def run_nulls(db_path: str = "data/warehouse.duckdb") -> None:
    con = duckdb.connect(db_path)

    print("=== Paso 1: Crear staging con NULLs y valores atípicos en clave ===")
    data = pd.DataFrame([
        [None, 10.0, "pm25", "µg/m³", 40.4, -3.7],                     # NULL
        ["2025-08-20 02:00:00+02:00", 21.0, "pm25", "µg/m³", 40.4, -3.7], # válido
        ["INVALID", 30.0, "pm25", "µg/m³", 40.4, -3.7],                # inválido
    ], columns=["datetime_utc", "value", "parameter", "unit", "latitude", "longitude"])

    con.execute("DROP TABLE IF EXISTS staging_nulls")
    con.register("data", data)
    con.execute("CREATE TABLE staging_nulls AS SELECT * FROM data")
    print(con.execute("SELECT * FROM staging_nulls").fetchdf())

    print("\n=== Paso 2: Carga incremental (deduplicación por datetime_utc) ===")
    before = con.execute("SELECT COUNT(*) FROM aq_madrid_pm25").fetchone()[0]
    try:
        con.execute("""
            INSERT INTO aq_madrid_pm25
            SELECT
                TRY_CAST(s.datetime_utc AS TIMESTAMPTZ) AS datetime_utc,
                s.value, s.parameter, s.unit, s.latitude, s.longitude
            FROM staging_nulls s
            LEFT JOIN aq_madrid_pm25 t
            ON TRY_CAST(s.datetime_utc AS TIMESTAMPTZ) = t.datetime_utc
            WHERE t.datetime_utc IS NULL
              AND s.datetime_utc IS NOT NULL
              AND TRY_CAST(s.datetime_utc AS TIMESTAMPTZ) IS NOT NULL
        """)
    except Exception as e:
        print(f"Error en inserción: {e}")
    after = con.execute("SELECT COUNT(*) FROM aq_madrid_pm25").fetchone()[0]
    print(f"Filas antes: {before}, después: {after}, nuevas: {after - before}")

    print("\n=== Paso 3: Verificar si entraron los NULLs/INVALID ===")
    df = con.execute("""
        SELECT datetime_utc, COUNT(*) AS n
        FROM aq_madrid_pm25
        WHERE datetime_utc >= '2025-08-19'
        GROUP BY 1 ORDER BY 1
    """).fetchdf()
    print(df)

    con.close()


if __name__ == "__main__":
    run_nulls()
