# app/reset_db.py
"""
Reset seguro de la base DuckDB.

- Vacía etl_runs y etl_metrics (ledger de runs y métricas).
- Elimina tablas de prueba y staging generadas en desarrollos previos.
- Mantiene la estructura necesaria para seguir operando el ETL.
"""

import duckdb

DB_PATH = "data/warehouse.duckdb"

TABLES_TO_DROP = [
    # Tablas de demo y fuentes externas antiguas
    "aq_madrid_pm25",
    "usgs_quakes_7d_m40",
    "wb_esp_sp_pop_totl",
    # Tablas de staging y pruebas
    "stg_20250824_174038_dim_customers",
    "stg_20250824_174104_datagiro_canonico_demo_v2",
    "stg_20250824_174104_dim_customers",
    "stg_20250824_174104_movimientos_logistica",
    "stg_20250824_174104_sample_data",
    "stg_prueba",
    "stg_ventas",
]

def main():
    con = duckdb.connect(DB_PATH)

    # 1. Vaciar ledger (mantener estructura)
    try:
        con.execute("DELETE FROM etl_runs")
        print("✔ etl_runs vaciada")
    except Exception as e:
        print(f"(i) etl_runs no existe o ya está vacía: {e}")

    try:
        con.execute("DELETE FROM etl_metrics")
        print("✔ etl_metrics vaciada")
    except Exception as e:
        print(f"(i) etl_metrics no existe o ya está vacía: {e}")

    # 2. Eliminar tablas de prueba/staging
    for tbl in TABLES_TO_DROP:
        try:
            con.execute(f"DROP TABLE IF EXISTS {tbl}")
            print(f"✔ Eliminada {tbl}")
        except Exception as e:
            print(f"(i) No se pudo eliminar {tbl}: {e}")

    con.close()
    print("\n=== Reseteo completo. Base lista para un nuevo arranque. ===")

if __name__ == "__main__":
    main()
