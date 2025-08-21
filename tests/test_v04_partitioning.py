# -*- coding: utf-8 -*-
"""
POC v0.4.0 – Particionado multi-columna (año + mes)

Este test valida:
1. Que DuckDB puede exportar Parquet con particionado en más de una columna.
2. Que podemos leer de vuelta las particiones y agregarlas correctamente.
"""

import duckdb
import os
import shutil


def run_partitioning(db_path: str = "data/warehouse.duckdb") -> None:
    con = duckdb.connect(db_path)

    print("=== Paso 1: Preparar directorio de salida limpio ===")
    out_dir = "data/parquet/aq_madrid_pm25_multi"
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    print("\n=== Paso 2: Exportar con particionado por año + mes ===")
    con.execute(f"""
        COPY (
            SELECT *,
                   strftime(datetime_utc, '%Y') AS year,
                   strftime(datetime_utc, '%m') AS month
            FROM aq_madrid_pm25
        )
        TO '{out_dir}/'
        (FORMAT PARQUET, PARTITION_BY (year, month), OVERWRITE_OR_IGNORE 1)
    """)
    print(f"Exportado a {out_dir}/")

    print("\n=== Paso 3: Leer particiones de vuelta ===")
    df = con.execute(f"""
        SELECT year, month, COUNT(*) AS filas
        FROM parquet_scan('{out_dir}/**/*.parquet')
        GROUP BY 1, 2
        ORDER BY 1, 2
    """).fetchdf()
    print(df)

    con.close()


if __name__ == "__main__":
    run_partitioning()
