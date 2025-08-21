# -*- coding: utf-8 -*-
"""
POC v0.4.0 – Incremental en tabla de población (wb_esp_sp_pop_totl)

Valida:
1. Insertar registros de años ya existentes (2019–2024) + un año nuevo (2025).
2. Que solo se inserte el nuevo (2025).
3. Que funcione aunque el valor llegue como string.
"""

import duckdb
import pandas as pd


def run_population(db_path: str = "data/warehouse.duckdb") -> None:
    con = duckdb.connect(db_path)

    print("=== Paso 1: Crear staging con población (años viejos + nuevo 2025) ===")
    data = pd.DataFrame([
        {"year": 2019, "value": 47000000, "indicator_id": "SP.POP.TOTL"},   # ya existe
        {"year": 2023, "value": "48347910", "indicator_id": "SP.POP.TOTL"}, # string numérico
        {"year": 2025, "value": "49000000", "indicator_id": "SP.POP.TOTL"}, # nuevo como string
    ])

    # Registrar DataFrame como tabla temporal en DuckDB
    con.register("data_df", data)
    con.execute("CREATE OR REPLACE TABLE staging_pop AS SELECT * FROM data_df")

    print(con.execute("SELECT * FROM staging_pop").fetchdf())

    print("\n=== Paso 2: Carga incremental (deduplicación por year) ===")
    before = con.execute("SELECT COUNT(*) FROM wb_esp_sp_pop_totl").fetchone()[0]
    con.execute("""
        INSERT INTO wb_esp_sp_pop_totl
        SELECT s.*
        FROM staging_pop s
        LEFT JOIN wb_esp_sp_pop_totl t
        ON s.year = t.year
        WHERE t.year IS NULL
    """)
    after = con.execute("SELECT COUNT(*) FROM wb_esp_sp_pop_totl").fetchone()[0]
    print(f"Filas antes: {before}, después: {after}, nuevas: {after - before}")

    print("\n=== Paso 3: Verificar qué entró ===")
    df = con.execute("""
        SELECT year, value
        FROM wb_esp_sp_pop_totl
        WHERE year >= 2019
        ORDER BY year
    """).fetchdf()
    print(df)

    con.close()


if __name__ == "__main__":
    run_population()
