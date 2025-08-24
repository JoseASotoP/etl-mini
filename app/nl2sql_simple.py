# -*- coding: utf-8 -*-
from __future__ import annotations
import re
from typing import Tuple, List, Optional

# Reglas muy simples para el MVP. Siempre mostramos el SQL antes de ejecutar.
# Tablas conocidas en tu proyecto:
KNOWN = {
    "pm25": "aq_madrid_pm25",
    "poblacion": "wb_esp_sp_pop_totl",
    "population": "wb_esp_sp_pop_totl",
    "quakes": "usgs_quakes_7d_m40",
    "terremotos": "usgs_quakes_7d_m40",
    "sismos": "usgs_quakes_7d_m40",
}

def _guess_table(q: str, tables: List[str]) -> Optional[str]:
    ql = q.lower()
    for kw, t in KNOWN.items():
        if kw in ql and t in tables:
            return t
    # fallback: primera tabla disponible
    return tables[0] if tables else None

def _month_filter(table: str) -> Optional[str]:
    if table == "aq_madrid_pm25":
        return "WHERE date_trunc('month', datetime_utc) = date_trunc('month', now())"
    if table == "usgs_quakes_7d_m40":
        return "WHERE time >= now() - INTERVAL 30 DAY"
    if table == "wb_esp_sp_pop_totl":
        return None
    return None

def nl_to_sql(q: str, tables: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Devuelve (sql, mensaje_info).
    Si no entiende la intención, devuelve un SELECT LIMIT 100 y explica que es un preview.
    """
    ql = (q or "").lower().strip()
    if not ql:
        return None, "Escribe una pregunta. Ej: '¿Cuántas lecturas PM2.5 hay este mes?'"

    table = _guess_table(ql, tables)
    if not table:
        return None, "No pude inferir la tabla. Ve a la pestaña Tablas para explorar."

    # count / cuántas
    if any(w in ql for w in ["cuantas", "cuántas", "cuantos", "cuántos", "count", "número de"]):
        filt = _month_filter(table)
        where = f" {filt}" if filt else ""
        return (f"SELECT COUNT(*) AS filas FROM {table}{where};", None)

    # top N
    m = re.search(r"top\s+(\d+)", ql)
    if m:
        n = int(m.group(1))
        order_col = "value" if table != "usgs_quakes_7d_m40" else "magnitude"
        return (f"SELECT * FROM {table} ORDER BY {order_col} DESC LIMIT {n};", None)

    # este mes / últimos X días
    if "este mes" in ql or "últimos" in ql or "ultimos" in ql:
        filt = _month_filter(table) or ""
        return (f"SELECT * FROM {table} {filt} ORDER BY 1 DESC LIMIT 100;", None)

    # por defecto: preview
    return (f"SELECT * FROM {table} LIMIT 100;", "No entendí del todo la intención; te muestro un preview (100 filas).")
