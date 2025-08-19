# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Muestra últimas ejecuciones y métricas de ETL desde DuckDB.

Lee tablas `etl_runs` y `etl_metrics` y presenta un resumen por consola.
Admite seleccionar la base de datos y el número de filas a mostrar.

Parameters
----------
None

Returns
-------
None
    Módulo con punto de entrada CLI.

Preconditions
--------------
Las tablas `etl_runs` y/o `etl_metrics` pueden no existir aún; en ese
caso se informa por pantalla sin lanzar excepción.

Example
--------
$ python -m app.show_runs --db data/warehouse.duckdb --n 15
"""

import argparse
import duckdb


def main() -> None:
    """
    Punto de entrada: imprime runs recientes y métricas del ETL.

    Construye las consultas en función de `--n` y muestra las últimas
    ejecuciones (`etl_runs`) y un bloque de métricas recientes
    (`etl_metrics`).

    Parameters
    ----------
    None

    Returns
    -------
    None
        Escribe la salida por stdout.

    Preconditions
    --------------
    La ruta `--db` debe ser accesible por DuckDB. Si las tablas no
    existen, se informa y la ejecución continúa.

    Example
    --------
    $ python -m app.show_runs --n 5
    """
    ap = argparse.ArgumentParser(
        description="Mostrar últimas ejecuciones ETL"
    )
    ap.add_argument("--db", default="data/warehouse.duckdb")
    ap.add_argument("--n", type=int, default=10)
    args = ap.parse_args()

    con = duckdb.connect(args.db)
    try:
        query_runs = (
            "SELECT run_id, started_at, finished_at, group_name, status, "
            "rows_total, duration_s "
            "FROM etl_runs "
            "ORDER BY started_at DESC "
            f"LIMIT {args.n}"
        )
        runs = con.execute(query_runs).fetchdf()
        print("\n=== Últimas ejecuciones (etl_runs) ===")
        print(runs)
    except Exception:
        print("Sin tabla etl_runs todavía.")

    try:
        query_met = (
            "SELECT run_id, source_name, table_name, rows_loaded, dq_pass, "
            "dq_violations, duration_s "
            "FROM etl_metrics "
            "ORDER BY run_id DESC "
            f"LIMIT {args.n * 3}"
        )
        met = con.execute(query_met).fetchdf()
        print("\n=== Métricas recientes (etl_metrics) ===")
        print(met)
    except Exception:
        print("Sin tabla etl_metrics todavía.")

    con.close()


if __name__ == "__main__":
    main()
