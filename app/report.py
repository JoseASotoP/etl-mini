# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Reporte HTML simple de una ejecución ETL.

Genera un HTML agregando el contenido de `last_run.txt` y los perfiles
`profile_*.md` encontrados en la carpeta de reportes configurada.
"""

from datetime import datetime, timezone
import os
import duckdb
import pandas as pd
from pathlib import Path
from typing import List

from .utils import load_settings

def _exists(con: duckdb.DuckDBPyConnection, name: str, view_ok: bool = True) -> bool:
    """
    Comprueba si existe una tabla (y opcionalmente una vista) en el esquema `main` de DuckDB.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Conexión activa a la base de datos DuckDB.
    name : str
        Nombre de la tabla o vista a verificar.
    view_ok : bool, default True
        Si es True, considera también las vistas como válidas. Si es False, solo tablas.

    Returns
    -------
    bool
        True si existe el objeto solicitado; False en caso contrario.

    Preconditions
    --------------
    Debe existir una conexión `con` abierta y válida a la base de datos.

    Example
    --------
    >>> # doctest: +SKIP
    >>> con = duckdb.connect("data/warehouse.duckdb")
    >>> _exists(con, "etl_runs")
    True
    """
    if view_ok:
        q = """
        SELECT 1 FROM information_schema.tables WHERE table_schema='main' AND table_name=?
        UNION ALL
        SELECT 1 FROM information_schema.views  WHERE table_schema='main' AND table_name=?
        LIMIT 1
        """
        return bool(con.execute(q, [name, name]).fetchone())
    else:
        return bool(con.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema='main' AND table_name=? LIMIT 1",
            [name]
        ).fetchone())


def assemble_report() -> str:
    """
    Construye un informe HTML con las tablas de runs, métricas y últimas cargas desde DuckDB.

    Genera un fichero `run_YYYYmmdd_HHMMSS.html` en el directorio de reportes configurado,
    con tres secciones: "Últimos runs", "Métricas recientes" y "Últimas cargas por tabla".
    Si alguna tabla/vista no existe, la sección correspondiente muestra "(sin datos)".

    Parameters
    ----------
    None

    Returns
    -------
    str
        Ruta absoluta (string) al archivo HTML generado.

    Preconditions
    --------------
    Debe existir configuración con `paths.db_path` y `paths.reports_dir`. Si falla la carga,
    se usa el *fallback*:
      - DB: `data/warehouse.duckdb`
      - Reportes: `data/reports` (se crea si no existe)

    Example
    --------
    >>> # doctest: +SKIP
    >>> out = assemble_report()
    >>> os.path.exists(out)
    True
    """
    # Usa tu load_settings si está importado; si no, fallback mínimo
    try:
        settings = load_settings()  # si no está importado arriba: from app.utils import load_settings
    except Exception:
        settings = {"paths": {"db_path": "data/warehouse.duckdb", "reports_dir": "data/reports"}}

    db_path = settings["paths"]["db_path"]
    reports_dir = settings["paths"]["reports_dir"]
    os.makedirs(reports_dir, exist_ok=True)

    con = duckdb.connect(db_path)

    runs = pd.DataFrame()
    mets = pd.DataFrame()
    last = pd.DataFrame()

    if _exists(con, "etl_runs"):
        runs = con.execute("""
            SELECT run_id, started_at, finished_at, group_name, status, rows_total, duration_s
            FROM etl_runs
            ORDER BY started_at DESC
            LIMIT 20
        """).fetchdf()

    if _exists(con, "etl_metrics"):
        mets = con.execute("""
            SELECT run_id, source_name, table_name, rows_loaded, dq_pass, dq_violations, duration_s, loaded_at
            FROM etl_metrics
            ORDER BY loaded_at DESC NULLS LAST, run_id DESC
            LIMIT 100
        """).fetchdf()

    if _exists(con, "v_etl_last", view_ok=True):
        last = con.execute("""
            SELECT table_name, source_name, rows_loaded, dq_pass, dq_violations, loaded_at
            FROM v_etl_last
            ORDER BY loaded_at DESC
        """).fetchdf()

    con.close()

    def _df(df: pd.DataFrame) -> str:
        """
        Convierte un DataFrame a HTML de tabla o devuelve un marcador de "sin datos".

        Parameters
        ----------
        df : pandas.DataFrame
            DataFrame a renderizar.

        Returns
        -------
        str
            Cadena HTML con la tabla o un párrafo indicando ausencia de datos.
        """
        if df is None or df.empty:
            return "<p><i>(sin datos)</i></p>"
        return df.to_html(index=False, escape=False)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
    head = (
        "<meta charset='utf-8'>"
        "<style>"
        "body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:24px;}"
        "table{border-collapse:collapse;width:100%;}"
        "th,td{border:1px solid #ddd;padding:6px 8px;font-size:13px;}"
        "th{background:#f6f6f6;text-align:left;}"
        "h1{margin-top:0} h2{margin-top:28px}"
        "</style>"
    )
    html = [
        "<html><head><title>ETL Mini — Informe</title>", head, "</head><body>",
        "<h1>ETL – Reporte de ejecución</h1>",
        "<h2>Resumen</h2>",
        "<ul>",
        f"<li>DB: <code>{db_path}</code></li>",
        f"<li>Generado: <code>{now}</code></li>",
        "</ul>",
        "<h2>Últimos runs</h2>", _df(runs),
        "<h2>Métricas recientes</h2>", _df(mets),
        "<h2>Últimas cargas por tabla</h2>", _df(last),
        "</body></html>",
    ]
    out_path = os.path.join(reports_dir, f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("".join(html))
    print(f"Reporte generado: {out_path}")
    return out_path



if __name__ == "__main__":
    p = assemble_report()
    print("Reporte generado:", p)
