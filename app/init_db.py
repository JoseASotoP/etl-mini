# app/init_db.py
"""
Inicializa la base DuckDB alineada con el runner (usa ensure_ledger).
Uso:
    python -m app.init_db
"""
from pathlib import Path
import duckdb

# Ajusta si tu settings.toml dice otra ruta
DB_PATH = Path("data/warehouse.duckdb")

def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"(i) Eliminada base anterior: {DB_PATH}")

    # Crea el fichero vacío
    con = duckdb.connect(str(DB_PATH))
    con.close()

    # Llama a la fuente de la verdad (runner.ensure_ledger)
    try:
        from app.runner import ensure_ledger
    except Exception as e:
        raise SystemExit(f"No se pudo importar ensure_ledger desde app.runner: {e}")

    ensure_ledger(str(DB_PATH))
    print(f"✔ Base de datos inicializada y alineada con runner.ensure_ledger\nRuta: {DB_PATH}")

if __name__ == "__main__":
    main()
