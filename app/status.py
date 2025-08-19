# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Muestra estado de ejecuciones y métricas de ETL desde DuckDB.

Lee las tablas `etl_runs` y `etl_metrics` y presenta un resumen por
consola o en JSON. Permite seleccionar la base de datos, limitar el
número de filas a mostrar y, opcionalmente, mostrar solo las últimas
cargas por tabla a través de la vista `v_etl_last`.

Parameters
----------
None

Returns
-------
None
    Módulo con punto de entrada CLI.

Preconditions
--------------
- La ruta indicada en `--db` debe ser accesible por DuckDB.
- Si las tablas o la vista no existen, se informa sin lanzar excepción.

Example
-------
$ python -m app.status --db data/warehouse.duckdb --n 15
$ python -m app.status --last
$ python -m app.status --json
$ python -m app.status --last --json
"""

import argparse
import duckdb
import json
import pandas as pd

def df_to_json_records(df: pd.DataFrame) -> str:
    """
    Convierte un DataFrame a JSON (`orient='records'`) serializando columnas
    de fecha/hora a cadenas ISO 8601 para evitar errores de serialización.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame de entrada. Si es ``None`` o está vacío, se devuelve ``"[]"``.

    Returns
    -------
    str
        Cadena JSON con indentación de 2 espacios y ``ensure_ascii=False``.

    Notes
    -----
    - Las columnas con tipo ``datetime64[ns]`` o ``datetime64[ns, tz]`` se
      convierten a texto ISO mediante ``astype(str)``, preservando la zona
      horaria cuando exista.
    - El resto de columnas se serializan con ``to_dict(orient="records")``.
      Si necesitas un control más estricto de tipos NumPy → tipos Python
      nativos, puedes añadir una normalización adicional antes del volcado
      a JSON.

    Examples
    --------
    >>> import pandas as pd
    >>> df = pd.DataFrame({
    ...     "when": pd.to_datetime(["2025-08-19 16:27:27+02:00"]),
    ...     "value": [42]
    ... })
    >>> json_str = df_to_json_records(df)
    >>> '"when": "2025-08-19 16:27:27+02:00"' in json_str
    True
    """
    if df is None or df.empty:
        return "[]"
    df2 = df.copy()
    for col in df2.columns:
        # 'M' indica dtype datetime en pandas (datetime64[*])
        if getattr(df2[col].dtype, "kind", None) == "M":
            df2[col] = df2[col].astype(str)  # ISO 8601
    # (opcional) normaliza tipos numpy a tipos Python si lo necesitas
    return json.dumps(
        df2.to_dict(orient="records"),
        ensure_ascii=False,
        indent=2,
    )


def main() -> None:
    """
    Punto de entrada CLI: muestra estado del ETL (runs, métricas, últimas cargas).

    Ejecuta consultas sobre las tablas `etl_runs` y `etl_metrics` en DuckDB.
    Opcionalmente incluye la vista `v_etl_last` (última carga por tabla).
    El resultado puede imprimirse como tablas (pandas.DataFrame) o en JSON.

    Parameters
    ----------
    None

    Returns
    -------
    None
        Escribe la salida por stdout (tablas o JSON).

    Preconditions
    --------------
    - La ruta indicada en `--db` debe ser accesible por DuckDB.
    - Si las tablas o vistas no existen, se informa sin lanzar excepción.

    Example
    -------
    $ python -m app.status --n 5
    $ python -m app.status --last
    $ python -m app.status --json
    $ python -m app.status --last --json
    """

    ap = argparse.ArgumentParser(
        description="Mostrar últimas ejecuciones ETL"
    )
    ap.add_argument("--db", default="data/warehouse.duckdb")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--last", action="store_true", help="Mostrar solo últimas cargas (v_etl_last)")
    ap.add_argument("--json", action="store_true", help="Salida en JSON en lugar de tablas")
    args = ap.parse_args()

    con = duckdb.connect(args.db)

    # Últimas ejecuciones (etl_runs)
    try:
        query_runs = f"""
            SELECT run_id, started_at, finished_at, group_name, status,
                   rows_total, duration_s
            FROM etl_runs
            ORDER BY started_at DESC
            LIMIT {args.n}
        """
        runs = con.execute(query_runs).fetchdf()
        print("\n=== Últimas ejecuciones (etl_runs) ===")
        if runs.empty:
            print("(sin filas todavía)")
        elif args.json:
            print(df_to_json_records(runs))
        else:
            print(runs)
    except duckdb.CatalogException:
        print("Sin tabla etl_runs todavía.")

    # Métricas recientes (etl_metrics)
    try:
        query_met = f"""
            SELECT run_id, source_name, table_name, rows_loaded, dq_pass,
                   dq_violations, duration_s
            FROM etl_metrics
            ORDER BY run_id DESC
            LIMIT {args.n * 3}
        """
        met = con.execute(query_met).fetchdf()
        print("\n=== Métricas recientes (etl_metrics) ===")
        if met.empty:
            print("(sin filas todavía)")
        elif args.json:
            print(df_to_json_records(met))
        else:
            print(met)
    except duckdb.CatalogException:
        print("Sin tabla etl_metrics todavía.")

    # Últimas cargas por tabla (v_etl_last)
    if args.last:
        try:
            # Asegura que la vista exista
            con.execute("""
                CREATE VIEW IF NOT EXISTS v_etl_last AS
                SELECT *
                FROM etl_metrics
                QUALIFY ROW_NUMBER() OVER (PARTITION BY table_name ORDER BY loaded_at DESC)=1
            """)
            query_last = """
                SELECT table_name, source_name, rows_loaded, dq_pass,
                       dq_violations, loaded_at
                FROM v_etl_last
                ORDER BY table_name
            """
            last = con.execute(query_last).fetchdf()
            print("\n=== Últimas cargas por tabla (v_etl_last) ===")
            if last.empty:
                print("(sin filas todavía)")
            elif args.json:
                print(df_to_json_records(last))
            else:
                print(last)

        except Exception as e:
            print(f"Error al consultar v_etl_last: {e}")

    con.close()


if __name__ == "__main__":
    main()