# -*- coding: utf-8 -*-
"""
POC v0.4.0 – Duplicados (exactos y parciales)

Este test valida:
1. Que los duplicados exactos NO se insertan de nuevo.
2. Qué ocurre con duplicados parciales (misma clave temporal, distinto valor).
"""

import duckdb
import os


def run_duplicates(db_path: str = "data/warehouse.duckdb") -> None:
    con = duckdb.connect(db_path)

    print("=== Paso 1: Crear staging con duplicados exactos y parciales ===")
    con.execute("""
        CREATE OR REPLACE TABLE staging_dup AS
        SELECT * FROM aq_madrid_pm25
        ORDER BY datetime_utc DESC LIMIT 3
    """)
    # Duplicado exacto (misma fila ya existente)
    con.execute("""
        INSERT INTO staging_dup (datetime_utc, value, parameter, unit, latitude, longitude)
        VALUES ('2025-08-19 00:00:00+02:00', 20.4, 'pm25', 'µg/m3', 40.4, -3.7)
    """)
    # Duplicado parcial (misma fecha/hora, distinto valor)
    con.execute("""
        INSERT INTO staging_dup (datetime_utc, value, parameter, unit, latitude, longitude)
        VALUES ('2025-08-19 00:00:00+02:00', 99.9, 'pm25', 'µg/m3', 40.4, -3.7)
    """)

    print(con.execute("SELECT * FROM staging_dup").fetchdf())

    print("\n=== Paso 2: Carga incremental (deduplicación por datetime_utc) ===")
    before = con.execute("SELECT COUNT(*) FROM aq_madrid_pm25").fetchone()[0]

    con.execute("""
        INSERT INTO aq_madrid_pm25
        SELECT s.*
        FROM staging_dup s
        LEFT JOIN aq_madrid_pm25 t
        ON s.datetime_utc = t.datetime_utc
        WHERE t.datetime_utc IS NULL
    """)

    after = con.execute("SELECT COUNT(*) FROM aq_madrid_pm25").fetchone()[0]
    print(f"Filas antes: {before}, después: {after}, nuevas: {after - before}")

    print("\n=== Paso 3: Verificar qué pasó con los duplicados ===")
    df_check = con.execute("""
        SELECT datetime_utc, COUNT(*) AS n, MIN(value) AS min_val, MAX(value) AS max_val
        FROM aq_madrid_pm25
        WHERE datetime_utc = '2025-08-19 00:00:00+02:00'
        GROUP BY datetime_utc
    """).fetchdf()
    print(df_check)

    con.close()


if __name__ == "__main__":
    run_duplicates()
