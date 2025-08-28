# -*- coding: utf-8 -*-
"""
Asistente LLM para Nítida — v0.5.0 (con Mini-Planner)

- Pestaña "Asistente" conversa en lenguaje natural.
- Modo 1: Consulta única → genera SQL SEGURO (solo SELECT) sobre tablas/vistas permitidas.
- Modo 2: Análisis (mini-planner) → produce 2–3 consultas (KPIs, serie temporal, Top SKU),
  ejecuta en DuckDB con LIMIT/timeout, dibuja múltiples gráficos y genera narrativa.
- Fallback sin API key con plantillas típicas (top-N, series diarias, etc.).
- Logs en: data/logs/assistant.log

Requisitos:
    pip install langchain langchain-openai openai tiktoken altair
"""

from __future__ import annotations

import os
import re
import json
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timedelta, timezone, date

import duckdb
import pandas as pd
import altair as alt
import streamlit as st

import re, datetime as dt
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple

DIM_SYNONYMS = {
    "sku": ["sku", "producto", "artículo", "item"],
    "customer_id": ["cliente", "account", "buyer"],
    "region_id": ["región", "region", "país", "pais", "country"],
    "channel_id": ["canal", "channel", "marketplace"]
}


# --- LangChain (opcional) ---
try:
    from langchain_openai import ChatOpenAI
    from langchain.prompts import ChatPromptTemplate
except Exception:  # sin deps o sin red
    ChatOpenAI = None
    ChatPromptTemplate = None

LOG_DIR = Path("data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "assistant.log"

# ======== Seguridad / utilidades SQL ========

DEFAULT_ALLOWED = [
    # Vistas del dashboard base:
    "vw_sales_items",       # (order_id, sku_id, quantity, revenue_eur, order_date, ...)
    "vw_sales_daily",       # (d, revenue_eur, units, orders)
    "vw_top_sku",           # (sku_id, revenue_eur, units)
    # Vistas/datos de los datasets grandes (si existen):
    "vw_fact_sales_big2m",
    "vw_big_sales_daily",
    "stg_fact_sales_big2m",
    "stg_fact_sales_wide",
]

DDL_FORBIDDEN = re.compile(
    r"\b(DROP|ALTER|TRUNCATE|CREATE|REPLACE|INSERT|UPDATE|DELETE|ATTACH|DETACH|COPY|PRAGMA)\b",
    re.I,
)
MULTISTMT = re.compile(r";\s*\S", re.S)

def _log(event: dict):
    try:
        event["ts"] = datetime.now(timezone.utc).isoformat()
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass

def _introspect_schema(con: duckdb.DuckDBPyConnection, allowed: list[str]) -> str:
    if not allowed:
        return ""
    q = f"""
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema='main' AND table_name IN ({",".join("'" + t + "'" for t in allowed)})
    ORDER BY table_name, ordinal_position
    """
    try:
        df = con.execute(q).fetchdf()
        if df.empty:
            return ""
        lines = []
        for t in allowed:
            cols = df[df["table_name"] == t]
            if cols.empty:
                continue
            spec = ", ".join(f"{c} {d}" for c, d in zip(cols["column_name"], cols["data_type"]))
            lines.append(f"{t}({spec})")
        return "\n".join(lines)
    except Exception:
        return ""

def sanitize_sql(sql: str, allowed: list[str], default_limit: int = 1000) -> str:
    """
    Reglas:
    - una sola sentencia
    - solo SELECT
    - sin DDL/DML peligrosos
    - si menciona tablas explícitas tras FROM/JOIN, deben estar en allowlist
    - LIMIT obligatorio
    """
    if not sql:
        raise ValueError("SQL vacío.")

    s = sql.strip().rstrip(";")
    if MULTISTMT.search(sql):
        raise ValueError("No se permite ejecutar múltiples sentencias.")
    if not re.match(r"^\s*SELECT\b", s, re.I):
        raise ValueError("Solo se permite SELECT.")
    if DDL_FORBIDDEN.search(s):
        raise ValueError("Comando no permitido en el SQL.")

    # Validar tablas si aparecen literal en FROM/JOIN
    for kw in ("FROM", "JOIN"):
        for m in re.finditer(rf"\b{kw}\s+([a-zA-Z_][a-zA-Z0-9_]*)", s, re.I):
            t = m.group(1)
            if t not in allowed:
                raise ValueError(f"Tabla no permitida: {t}")

    if not re.search(r"\bLIMIT\b", s, re.I):
        s = f"{s}\nLIMIT {default_limit}"
    return s

def run_select(con: duckdb.DuckDBPyConnection, sql: str, timeout_ms: int = 6000) -> pd.DataFrame:

    return con.execute(sql).fetchdf()

# ======== Plantillas simplificadas (sin LLM) ========

def template_sql(prompt: str) -> str | None:
    """
    Heurísticas muy simples si no hay LLM:
    """
    p = prompt.lower()
    if "top" in p and ("sku" in p or "producto" in p):
        m = re.search(r"top\s+(\d+)", p)
        n = int(m.group(1)) if m else 10
        return f"SELECT * FROM vw_top_sku ORDER BY revenue_eur DESC LIMIT {n}"
    if ("últimos" in p or "ultimos" in p or "last" in p) and ("días" in p or "dias" in p or "days" in p):
        m = re.search(r"(últimos|ultimos|last)\s+(\d+)", p)
        n = int(m.group(2)) if m else 30
        return f"""
        SELECT * FROM vw_sales_daily
        WHERE d >= CURRENT_DATE - INTERVAL '{n} days'
        ORDER BY d
        """
    if "diario" in p or "por día" in p or "por dia" in p:
        return "SELECT * FROM vw_sales_daily ORDER BY d LIMIT 3650"
    if "items" in p or "líneas" in p or "lineas" in p:
        return "SELECT * FROM vw_sales_items LIMIT 1000"
    return None

# ======== LLM → SQL (consulta única) ========

SYSTEM_PROMPT = """Eres un asistente de analítica.
Devuelves SIEMPRE una única consulta SQL válida para DuckDB, enfocada en negocio.
REGLAS:
- Solo SELECT.
- Solo las tablas/vistas permitidas que te doy.
- Aplica LIMIT si es necesario.
- Prefiere nombres de columnas tal cual el esquema.
Esquema permitido:
{schema}
"""

def llm_to_sql(prompt: str, schema_text: str, model_name: str = "gpt-4o-mini") -> str:
    if ChatOpenAI is None or os.getenv("OPENAI_API_KEY") in (None, ""):
        sql = template_sql(prompt)
        if sql:
            return sql
        raise RuntimeError("Sin LLM y sin plantilla aplicable. Sé más específico (ej.: 'Top 10 SKUs por ingresos').")

    try:
        llm = ChatOpenAI(model=model_name, temperature=0.1)
        tmpl = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("user", "{question}"),
        ])
        chain = tmpl | llm
        out = chain.invoke({"schema": schema_text, "question": prompt})
        text = out.content if hasattr(out, "content") else str(out)
        m = re.search(r"```sql\s*(.*?)```", text, re.S|re.I)
        sql = m.group(1).strip() if m else text.strip()
        return sql
    except Exception as e:
        # Si falla la llamada (key inválida, red, etc.), intenta plantilla
        sql = template_sql(prompt)
        if sql:
            return sql
        raise RuntimeError(f"No se pudo usar el LLM: {e}")

# ======== Charts básicos ========

def auto_chart(df: pd.DataFrame, title: str = ""):
    """
    Reglas:
    - Si hay 'd' (fecha) + numéricas → línea temporal.
    - Si hay 'sku_id' + numérica → barras top.
    - Si no, None (Streamlit muestra tabla).
    """
    if df is None or df.empty:
        return None

    if "d" in df.columns:
        try:
            data = df.copy()
            data["d"] = pd.to_datetime(data["d"])
            cands = [c for c in data.columns if c != "d" and pd.api.types.is_numeric_dtype(data[c])]
            if cands:
                y = cands[0]
                return alt.Chart(data).mark_line().encode(
                    x="d:T",
                    y=f"{y}:Q",
                    tooltip=list(data.columns),
                ).properties(height=280, title=title or y)
        except Exception:
            pass

    if "sku_id" in df.columns:
        cands = [c for c in df.columns if c != "sku_id" and pd.api.types.is_numeric_dtype(df[c])]
        if cands:
            y = cands[0]
            data = df.sort_values(y, ascending=False).head(20)
            return alt.Chart(data).mark_bar().encode(
                x=f"{y}:Q",
                y=alt.Y("sku_id:N", sort="-x"),
                tooltip=list(data.columns),
            ).properties(height=360, title=title or y)

    return None

# ======== Mini-Planner ========

@dataclass
class Filters:
    start: str | None = None   # ISO date (YYYY-MM-DD)
    end: str | None = None     # ISO date (YYYY-MM-DD), exclusive
    last_days: int | None = None
    year: int | None = None

def parse_filters(prompt: str) -> Filters:
    """Extrae 'últimos N días' o 'año 202X' de forma simple."""
    p = prompt.lower()

    # últimos N días
    m = re.search(r"(últimos|ultimos|last)\s+(\d+)\s+(días|dias|days)", p)
    if m:
        n = int(m.group(2))
        return Filters(last_days=n)

    # año 20xx
    m2 = re.search(r"\b(20\d{2})\b", p)
    if m2:
        y = int(m2.group(1))
        return Filters(year=y)

    return Filters()

def _date_clause(col: str, flt: Filters) -> str:
    if flt.last_days:
        return f"{col} >= CURRENT_DATE - INTERVAL '{int(flt.last_days)} days'"
    if flt.year:
        y = int(flt.year)
        return f"{col} >= DATE '{y}-01-01' AND {col} < DATE '{y+1}-01-01'"
    return "TRUE"

def tables_available(con: duckdb.DuckDBPyConnection) -> set[str]:
    rows = con.execute("""
        SELECT table_name FROM information_schema.tables WHERE table_schema='main'
        UNION ALL
        SELECT table_name FROM information_schema.views  WHERE table_schema='main'
    """).fetchall()
    return {r[0] for r in rows}

@dataclass
class PlanQuery:
    title: str
    sql: str
    kind: str  # "kpi" | "series" | "top"

def build_plan(con: duckdb.DuckDBPyConnection, prompt: str, allowed: list[str]) -> list[PlanQuery]:
    """
    Construye 2–3 consultas según lo disponible.
    Preferencias:
      - KPIs desde vw_sales_items (orders) o vw_sales_daily (sin orders)
      - Serie temporal desde vw_sales_daily o vw_big_sales_daily
      - Top SKU desde vw_sales_items o vw_fact_sales_big2m
    """
    avail = tables_available(con)
    flt = parse_filters(prompt)

    # Helpers de fecha por columna
    items_date_col = "order_date"
    daily_date_col = "d"
    big_date_col   = "promised_date"

    plan: list[PlanQuery] = []

    # 1) KPIs (revenue, units, orders si hay)
    if "vw_sales_items" in avail:
        where = _date_clause(items_date_col, flt)
        plan.append(PlanQuery(
            title="KPIs (ventas)",
            kind="kpi",
            sql=f"""
            SELECT
              SUM(revenue_eur)                      AS revenue_eur,
              SUM(quantity)                         AS units,
              COUNT(DISTINCT order_id)              AS orders
            FROM vw_sales_items
            WHERE {where}
            """
        ))
    elif "vw_sales_daily" in avail:
        where = _date_clause(daily_date_col, flt)
        plan.append(PlanQuery(
            title="KPIs (ventas diarias agregadas)",
            kind="kpi",
            sql=f"""
            SELECT
              SUM(revenue_eur) AS revenue_eur,
              SUM(units)       AS units,
              NULL::BIGINT     AS orders
            FROM vw_sales_daily
            WHERE {where}
            """
        ))
    elif "vw_fact_sales_big2m" in avail:
        where = _date_clause(big_date_col, flt)
        plan.append(PlanQuery(
            title="KPIs (ventas big2m)",
            kind="kpi",
            sql=f"""
            SELECT
              SUM(line_total_eur)                   AS revenue_eur,
              SUM(quantity_units)                   AS units,
              NULL::BIGINT                          AS orders
            FROM vw_fact_sales_big2m
            WHERE {where}
            """
        ))

    # 2) Serie temporal
    if "vw_sales_daily" in avail:
        where = _date_clause(daily_date_col, flt)
        plan.append(PlanQuery(
            title="Serie diaria — revenue",
            kind="series",
            sql=f"""
            SELECT d, revenue_eur, units, orders
            FROM vw_sales_daily
            WHERE {where}
            ORDER BY d
            """
        ))
    elif "vw_big_sales_daily" in avail:
        where = _date_clause(daily_date_col, flt)
        plan.append(PlanQuery(
            title="Serie diaria — revenue (big)",
            kind="series",
            sql=f"""
            SELECT d, revenue_eur, units
            FROM vw_big_sales_daily
            WHERE {where}
            ORDER BY d
            """
        ))

    # 3) Top SKU
    if "vw_sales_items" in avail:
        where = _date_clause(items_date_col, flt)
        plan.append(PlanQuery(
            title="Top 10 SKU por ingresos",
            kind="top",
            sql=f"""
            SELECT sku_id,
                   SUM(revenue_eur) AS revenue_eur,
                   SUM(quantity)    AS units
            FROM vw_sales_items
            WHERE {where}
            GROUP BY sku_id
            ORDER BY revenue_eur DESC
            LIMIT 10
            """
        ))
    elif "vw_fact_sales_big2m" in avail:
        where = _date_clause(big_date_col, flt)
        plan.append(PlanQuery(
            title="Top 10 SKU por ingresos (big2m)",
            kind="top",
            sql=f"""
            SELECT sku_id,
                   SUM(line_total_eur) AS revenue_eur,
                   SUM(quantity_units) AS units
            FROM vw_fact_sales_big2m
            WHERE {where}
            GROUP BY sku_id
            ORDER BY revenue_eur DESC
            LIMIT 10
            """
        ))

    # Filtra solo las que referencian tablas permitidas
    filtered: list[PlanQuery] = []
    for q in plan:
        try:
            _ = sanitize_sql(q.sql, allowed, default_limit=2000000)  # no imponemos LIMIT en agregados
            filtered.append(q)
        except Exception:
            continue

    # Si por lo que sea no hay nada, devolvemos algo genérico para no dejar vacío
    if not filtered and "vw_sales_daily" in avail:
        filtered = [PlanQuery(
            title="Serie diaria (fallback)",
            kind="series",
            sql="SELECT d, revenue_eur, units FROM vw_sales_daily ORDER BY d LIMIT 3650"
        )]

    return filtered[:3]  # como máximo 3

def narrate_from_results(prompt: str, dfs: dict[str, pd.DataFrame]) -> str:
    """
    Genera narrativa. Si hay LLM, resume con contexto;
    si no, compone un texto basado en estadísticas simples.
    """
    # Heurística local
    def num(x):
        try:
            return float(x)
        except Exception:
            return None

    revenue, units, orders = None, None, None
    if "kpi" in dfs and not dfs["kpi"].empty:
        row = dfs["kpi"].iloc[0]
        revenue = num(row.get("revenue_eur"))
        units   = num(row.get("units"))
        orders  = num(row.get("orders"))

    trend = ""
    if "series" in dfs and not dfs["series"].empty:
        s = dfs["series"]
        try:
            s["d"] = pd.to_datetime(s["d"])
            s = s.sort_values("d")
            if "revenue_eur" in s.columns:
                last = s["revenue_eur"].tail(7).sum()
                prev = s["revenue_eur"].tail(14).head(7).sum()
                if prev and prev != 0:
                    pct = (last - prev) / prev * 100.0
                    trend = f"La última semana la facturación sumó {last:,.0f}€, {pct:+.1f}% vs la semana previa."
        except Exception:
            pass

    base_text = "Análisis general: "
    parts = []
    if revenue is not None:
        parts.append(f"Ingresos totales ≈ {revenue:,.0f}€")
    if units is not None:
        parts.append(f"unidades ≈ {units:,.0f}")
    if orders is not None:
        parts.append(f"pedidos ≈ {orders:,.0f}")
    if trend:
        parts.append(trend)

    summary_local = base_text + ("; ".join(parts) if parts else "consulta ejecutada.")
    use_llm = (ChatOpenAI is not None and os.getenv("OPENAI_API_KEY"))

    if not use_llm:
        return summary_local

    # LLM: genera una narrativa de 4-6 frases
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
        schema_hint = ", ".join(k for k in dfs.keys() if not dfs[k].empty)
        few_rows = {}
        for k, df in dfs.items():
            few_rows[k] = df.head(10).to_dict(orient="records")

        prompt_tmpl = ChatPromptTemplate.from_messages([
            ("system",
             "Eres un analista de datos. Resume de forma clara y accionable los resultados. "
             "Ton profesional, 4–6 frases, menciona cifras relevantes y, si procede, variaciones recientes."),
            ("user",
             "Petición del usuario: {user_prompt}\n"
             "Resultados disponibles: {tables}\n"
             "Muestras JSON (hasta 10 filas por tabla):\n{samples}\n"
             "Escribe un resumen breve y útil.")
        ])
        out = (prompt_tmpl | llm).invoke({
            "user_prompt": prompt,
            "tables": schema_hint,
            "samples": json.dumps(few_rows, ensure_ascii=False)[:6000],  # límite prudente
        })
        text = out.content if hasattr(out, "content") else str(out)
        return text.strip()
    except Exception:
        return summary_local

# ======== UI Principal ========

def render_assistant(con: duckdb.DuckDBPyConnection, allowed_tables: list[str] | None = None):
    st.subheader("Asistente (LLM)")

    # Allowlist dinámica (intersección de DEFAULT_ALLOWED con lo existente)
    avail = tables_available(con)
    allowed = [t for t in (allowed_tables or DEFAULT_ALLOWED) if t in avail]
    schema_text = _introspect_schema(con, allowed)

    with st.expander("Ayuda / qué puedo pedir", expanded=False):
        st.markdown(
            "- *“Top 10 SKUs por ingresos.”*\n"
            "- *“Ventas por día en los últimos 30 días.”*\n"
            "- *“Análisis general de 2024.”*\n"
            "- *“Comparativa última semana vs anterior.”*"
        )
        st.caption("Si no configuras OPENAI_API_KEY, se usarán plantillas y el planner local.")

    # Selector de modo
    mode = st.radio(
        "Modo",
        ["Consulta única (SQL)", "Análisis (planner clásico)", "Análisis avanzado"],
        index=1,
        horizontal=True,
    )

    c1, c2 = st.columns([3,1])
    with c1:
        user_prompt = st.text_area("Escribe tu petición:", height=100,
                                   placeholder="Ej.: Análisis general 2024; Top 10 SKU últimos 30 días; …")
    with c2:
        model = st.selectbox("Modelo", ["gpt-4o-mini (OpenAI)", "Plantillas locales"], index=0 if os.getenv("OPENAI_API_KEY") else 1)

    if st.button("► Ejecutar", type="primary"):
        started = datetime.now()
        executed_ok = False

        if mode == "Consulta única (SQL)":
            try:
                use_llm = (model.startswith("gpt-") and os.getenv("OPENAI_API_KEY"))
                sql_raw = llm_to_sql(user_prompt, schema_text, model_name="gpt-4o-mini") if use_llm else (template_sql(user_prompt) or "")
                sql = sanitize_sql(sql_raw, allowed, default_limit=1000)
                df = run_select(con, sql, timeout_ms=6000)
                if "d" in df.columns:
                    with pd.option_context("mode.chained_assignment", None):
                        try: df["d"] = pd.to_datetime(df["d"])
                        except Exception: pass
                st.code(sql, language="sql")
                st.dataframe(df, use_container_width=True, hide_index=True, height=320)
                ch = auto_chart(df)
                if ch is not None:
                    st.altair_chart(ch, use_container_width=True)
                executed_ok = True
                _log({"ok": True, "mode":"single", "prompt": user_prompt, "sql": sql,
                      "rows": int(len(df)), "ms": int((datetime.now()-started).total_seconds()*1000),
                      "llm": bool(use_llm)})
            except Exception as e:
                st.error(f"No se pudo ejecutar tu petición: {e}")
                _log({"ok": False, "mode":"single", "prompt": user_prompt, "error": str(e)})

        elif mode == "Análisis (planner clásico)":
            try:
                plan = build_plan(con, user_prompt, allowed)
                if not plan:
                    raise RuntimeError("No se pudo construir un plan de análisis con las tablas disponibles.")

                tabs = st.tabs([p.title for p in plan])
                results: dict[str, pd.DataFrame] = {}
                for (p, tab) in zip(plan, tabs):
                    with tab:
                        try:
                            sql = sanitize_sql(p.sql, allowed, default_limit=2000000)  # agregados: sin límite duro
                            df = run_select(con, sql, timeout_ms=8000)
                            # normaliza fecha si procede
                            if "d" in df.columns:
                                with pd.option_context("mode.chained_assignment", None):
                                    try: df["d"] = pd.to_datetime(df["d"])
                                    except Exception: pass
                            st.code(sql, language="sql")
                            st.dataframe(df, use_container_width=True, hide_index=True, height=280)
                            ch = auto_chart(df, title=p.title)
                            if ch is not None:
                                st.altair_chart(ch, use_container_width=True)
                            results[p.kind] = df
                        except Exception as e:
                            st.warning(f"No se pudo ejecutar '{p.title}': {e}")

                # Narrativa (en bloque aparte)
                st.markdown("### Narrativa")
                story = narrate_from_results(user_prompt, results)
                st.write(story)

                executed_ok = True
                _log({"ok": True, "mode":"planner", "prompt": user_prompt,
                      "parts": [p.kind for p in plan],
                      "ms": int((datetime.now()-started).total_seconds()*1000)})
            except Exception as e:
                st.error(f"No se pudo completar el análisis: {e}")
                _log({"ok": False, "mode":"planner", "prompt": user_prompt, "error": str(e)})
                
        elif mode == "Análisis avanzado":
            try:
                run_plan(con, user_prompt, st, model_label=model)
            except Exception as e:
                st.error(f"No se pudo ejecutar el análisis avanzado: {e}")



@dataclass
class Scope:
    start: dt.date
    end: dt.date            # end exclusivo
    dim: Optional[str]      # 'sku', 'customer_id', etc.
    intent: List[str]       # ['kpis','series','compare','drivers','anomalies','dow']
    top_n: int = 10

# --------- parsing sencillo de rango temporal en español ---------
def parse_time_window(text: str, today: Optional[dt.date] = None) -> Tuple[dt.date, dt.date]:
    t = (today or dt.date.today())
    s = text.lower()

    # últimos X días/meses
    m = re.search(r"últim[oa]s?\s+(\d+)\s*(d[ií]as?)", s)
    if m:
        n = int(m.group(1)); start = t - dt.timedelta(days=n); return start, t + dt.timedelta(days=1)

    m = re.search(r"últim[oa]s?\s+(\d+)\s*mes", s)
    if m:
        n = int(m.group(1)); start = (t.replace(day=1) - dt.timedelta(days=1))
        for _ in range(n-1): start = (start.replace(day=1) - dt.timedelta(days=1))
        start = start.replace(day=1)
        return start, t + dt.timedelta(days=1)

    # “este año”, “2024”, “año 2024”
    if "este año" in s or "este anio" in s:
        start = dt.date(t.year,1,1); end = dt.date(t.year+1,1,1); return start, end
    m = re.search(r"(?:año|ano)?\s*(20\d{2})", s)
    if m:
        y = int(m.group(1)); return dt.date(y,1,1), dt.date(y+1,1,1)

    # “Q3 2025”
    qm = re.search(r"q([1-4])\s*(20\d{2})", s)
    if qm:
        q = int(qm.group(1)); y = int(qm.group(2))
        start = dt.date(y, 3*(q-1)+1, 1)
        qend_month = 3*q+1
        end = dt.date(y+1,1,1) if qend_month==13 else dt.date(y, qend_month, 1)
        return start, end

    # “desde 2024-04-01 a 2024-08-31”
    m = re.search(r"desde\s*(\d{4}-\d{2}-\d{2})\s*(?:a|hasta)\s*(\d{4}-\d{2}-\d{2})", s)
    if m:
        start = dt.date.fromisoformat(m.group(1)); end = dt.date.fromisoformat(m.group(2)) + dt.timedelta(days=1)
        return start, end

    # por defecto: últimos 30 días
    return t - dt.timedelta(days=30), t + dt.timedelta(days=1)

def detect_dimension(text: str) -> Optional[str]:
    s = text.lower()
    for dim, keys in DIM_SYNONYMS.items():
        if any(k in s for k in keys): return dim
    return None

def detect_intents(text: str) -> List[str]:
    s = text.lower()
    intents = []
    # base
    intents += ["kpis","series","top"]
    # extensiones según palabras
    if any(w in s for w in ["compar", "vs", "frente", "respecto"]): intents.append("compare")
    if any(w in s for w in ["driver", "caída", "caidas", "subida", "ganadores", "perdedores", "motores"]): intents.append("drivers")
    if any(w in s for w in ["anomal", "pico", "spike"]): intents.append("anomalies")
    if any(w in s for w in ["semana", "dow", "día de la semana", "dia de la semana"]): intents.append("dow")
    return list(dict.fromkeys(intents))

def make_scope(prompt: str) -> Scope:
    start, end = parse_time_window(prompt)
    dim = detect_dimension(prompt) or "sku"  # por defecto sku
    intents = detect_intents(prompt)
    m = re.search(r"top\s*(\d+)", prompt.lower())
    top_n = int(m.group(1)) if m else 10
    return Scope(start, end, dim, intents, top_n)

# ------------------ SQL helpers ------------------

def where_between(col: str) -> str:
    return f"{col} >= ? AND {col} < ?"

def kpis_sql(extra_where: str = "") -> str:
    return f"""
WITH cur AS (
  SELECT SUM(revenue_eur) AS rev, SUM(quantity) AS units, COUNT(DISTINCT order_id) AS orders
  FROM vw_sales_items
  WHERE {where_between('order_date')} {extra_where}
),
prev AS (
  SELECT SUM(revenue_eur) AS rev, SUM(quantity) AS units, COUNT(DISTINCT order_id) AS orders
  FROM vw_sales_items
  WHERE {where_between('order_date')} {extra_where}
)
SELECT cur.rev, cur.units, cur.orders,
       prev.rev AS prev_rev, prev.units AS prev_units, prev.orders AS prev_orders,
       (cur.rev - prev.rev) AS delta_rev,
       100.0*(cur.rev - prev.rev)/NULLIF(prev.rev,0) AS pct_rev
FROM cur, prev;
"""

def series_sql(extra_where: str = "", grain: str = "day") -> str:
    # usamos la vista ya diaria para simplificar y la filtramos
    return f"""
SELECT d, revenue_eur, units, orders
FROM vw_sales_daily
WHERE {where_between('d')} {extra_where}
ORDER BY d
LIMIT 2000000;
"""

def top_dim_sql(dim: str, extra_where: str = "", limit: int = 10) -> str:
    return f"""
SELECT {dim} AS dim,
       SUM(revenue_eur) AS revenue_eur,
       SUM(quantity)    AS units
FROM vw_sales_items
WHERE {where_between('order_date')} {extra_where}
GROUP BY 1
ORDER BY revenue_eur DESC
LIMIT {limit};
"""

def drivers_sql(dim: str, extra_where: str = "", limit: int = 10) -> str:
    # compara periodo vs anterior (misma duración)
    return f"""
WITH cur AS (
  SELECT {dim} AS dim, SUM(revenue_eur) AS rev
  FROM vw_sales_items
  WHERE {where_between('order_date')} {extra_where}
  GROUP BY 1
),
prev AS (
  SELECT {dim} AS dim, SUM(revenue_eur) AS rev
  FROM vw_sales_items
  WHERE {where_between('order_date')} {extra_where}
  GROUP BY 1
),
both AS (
  SELECT dim, SUM(CASE WHEN tag='cur' THEN rev ELSE 0 END) AS rev_cur,
             SUM(CASE WHEN tag='prev' THEN rev ELSE 0 END) AS rev_prev
  FROM (
    SELECT 'cur' AS tag, * FROM cur
    UNION ALL
    SELECT 'prev' AS tag, * FROM prev
  )
  GROUP BY 1
)
SELECT dim, rev_cur, rev_prev, (rev_cur - rev_prev) AS diff
FROM both
ORDER BY diff DESC
LIMIT {limit};
"""

def anomalies_sql(extra_where: str = "") -> str:
    return f"""
WITH ts AS (
  SELECT d, revenue_eur
  FROM vw_sales_daily
  WHERE {where_between('d')} {extra_where}
  ORDER BY d
),
s AS (
  SELECT d, revenue_eur,
         AVG(revenue_eur) OVER (ORDER BY d ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING) AS ma30,
         STDDEV_SAMP(revenue_eur) OVER (ORDER BY d ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING) AS sd30
  FROM ts
)
SELECT d, revenue_eur, ma30, sd30,
       (revenue_eur - ma30)/NULLIF(sd30,0) AS z
FROM s
WHERE sd30 IS NOT NULL AND ABS((revenue_eur - ma30)/NULLIF(sd30,0)) >= 3
ORDER BY ABS(z) DESC
LIMIT 20;
"""

def dow_sql(extra_where: str = "") -> str:
    return f"""
SELECT STRFTIME(d, '%w')::INTEGER AS dow,
       AVG(revenue_eur) AS avg_rev, AVG(units) AS avg_units, AVG(orders) AS avg_orders
FROM vw_sales_daily
WHERE {where_between('d')} {extra_where}
GROUP BY 1
ORDER BY 1;
"""

# ----------------- ejecución y render -----------------

def run_plan(con, prompt: str, st, model_label: str = "gpt-4o-mini (OpenAI)"):
    scope = make_scope(prompt)
    start, end = scope.start, scope.end
    prev_len = end - start
    prev_start = start - prev_len
    prev_end   = start

    # filtros extra (placeholder para cuando filtremos por canal/cliente específicos)
    extra = ""  # e.g. " AND channel_id = ?"

    st.caption(f"Ventana: {start} → {end-dt.timedelta(days=1)}  |  Dimensión: **{scope.dim}**  |  Modelo: {model_label}")

    # --- KPIs ---
    if "kpis" in scope.intent:
        sql = kpis_sql(extra)
        df = con.execute(sql, [start, end, prev_start, prev_end]).df()
        st.subheader("KPIs (periodo vs previo)")
        st.dataframe(df, hide_index=True, use_container_width=True)

    # --- Serie ---
    if "series" in scope.intent:
        sql = series_sql(extra)
        ts = con.execute(sql, [start, end]).df()
        st.subheader("Serie diaria — revenue")
        st.line_chart(ts.set_index("d")["revenue_eur"])

    # --- Top N dimensión ---
    if "top" in scope.intent:
        sql = top_dim_sql(scope.dim, extra, scope.top_n)
        topdf = con.execute(sql, [start, end]).df()
        st.subheader(f"Top {scope.top_n} por ingresos — {scope.dim}")
        st.bar_chart(topdf.set_index("dim")["revenue_eur"])

    # --- Drivers (ganadores) ---
    if "drivers" in scope.intent:
        st.subheader(f"Drivers (∆ ingresos vs periodo anterior) — {scope.dim}")
        gains = con.execute(drivers_sql(scope.dim, extra, scope.top_n), [start, end, prev_start, prev_end]).df()
        st.dataframe(gains, hide_index=True, use_container_width=True)

    # --- Anomalías ---
    if "anomalies" in scope.intent:
        an = con.execute(anomalies_sql(extra), [start, end]).df()
        st.subheader("Anomalías (|z| ≥ 3)")
        st.dataframe(an, hide_index=True, use_container_width=True)

    # --- Día de semana ---
    if "dow" in scope.intent:
        dow = con.execute(dow_sql(extra), [start, end]).df()
        st.subheader("Estacionalidad por día de semana (0=Dom, 6=Sáb)")
        st.bar_chart(dow.set_index("dow")["avg_rev"])

    # --- Narrativa simple ---
    st.markdown("### Narrativa")
    narr = []
    if "kpis" in scope.intent and 'df' in locals():
        rev = float(df.loc[0, 'rev']); prv = float(df.loc[0,'prev_rev'] or 0.0)
        pct = float(df.loc[0,'pct_rev'] or 0.0)
        narr.append(f"Ingresos del periodo: **{rev:,.0f} €**, variación vs anterior: **{pct:+.1f}%**.")
    if "top" in scope.intent and not topdf.empty:
        first = topdf.iloc[0]
        narr.append(f"Top {scope.dim}: **{first['dim']}** (~{first['revenue_eur']:,.0f} €).")
    if "anomalies" in scope.intent and not an.empty:
        d0 = an.iloc[0]['d']; z0 = an.iloc[0]['z']
        narr.append(f"Mayor anomalía: **{d0}** (z≈{z0:.1f}).")
    st.write(" ".join(narr) if narr else "Sin hallazgos destacados.")
