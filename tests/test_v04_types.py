# -*- coding: utf-8 -*-
"""
POC v0.4.0 – Mezcla de tipos (int como string)
"""

import duckdb
import pandas as pd


def run_types(db_path: str = "data/warehouse.duckdb") -> None:
    con = duckdb.connect(db_path)

    print("=== Paso 1: Crear staging con tipos mezclados ===")
    data = pd.DataFrame({
        "year": ["2020", "2026", "XXXX"],   # uno válido duplicado, uno nuevo válido, uno inválido
        "value": ["47359424", "50000000", "INVALID"],
        "indicator_id": ["SP.POP.TOTL"] * 3
    })
    print(data)

    con.register("staging_types", data)

    print("\n=== Paso 2: Carga incremental con TRY_CAST ===")
    before = con.execute("SELECT COUNT(*) FROM wb_esp_sp_pop_totl").fetchone()[0]

    con.execute("""
        INSERT INTO wb_esp_sp_pop_totl
        SELECT 
            TRY_CAST(s.year AS INT) AS year,
            TRY_CAST(s.value AS BIGINT) AS value,
            s.indicator_id
        FROM staging_types s
        LEFT JOIN wb_esp_sp_pop_totl t
        ON TRY_CAST(s.year AS INT) = t.year
        WHERE t.year IS NULL
          AND TRY_CAST(s.year AS INT) IS NOT NULL
          AND TRY_CAST(s.value AS BIGINT) IS NOT NULL
    """)

    after = con.execute("SELECT COUNT(*) FROM wb_esp_sp_pop_totl").fetchone()[0]
    print(f"Filas antes: {before}, después: {after}, nuevas: {after - before}")

    print("\n=== Paso 3: Verificar si entraron los válidos ===")
    df = con.execute("""
        SELECT year, value
        FROM wb_esp_sp_pop_totl
        WHERE year >= 2025
        ORDER BY year
    """).fetchdf()
    print(df)

    con.close()


if __name__ == "__main__":
    run_types()
