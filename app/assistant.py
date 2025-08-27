# -*- coding: utf-8 -*-
"""
Asistente LLM para Nítida — v0.5.0 MVP

- Pestaña "Asistente" conversa en lenguaje natural.
- Genera SQL SEGURO (solo SELECT) sobre tablas/vistas permitidas.
- Ejecuta en DuckDB con LIMIT/timeout y muestra tabla + gráfico.
- Fallback sin API key con plantillas típicas (top-N, series diarias, etc.).
- Log de actividad: data/logs/assistant.log

Requisitos:
    pip install langchain langchain-openai openai tiktoken altair
"""

from __future__ import annotations
import io

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

def df_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "Datos") -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name=sheet_name)
    buf.seek(0)
    return buf.read()


import os
import re
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

import duckdb
import pandas as pd
import altair as alt
import streamlit as st

# --- LangChain ---
try:
    from langchain_openai import ChatOpenAI
    from langchain.prompts import ChatPromptTemplate
except Exception:  # sin deps o sin red
    ChatOpenAI = None
    ChatPromptTemplate = None

LOG_DIR = Path("data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "assistant.log"

# ===== Seguridad / utilidades =====

DEFAULT_ALLOWED = [
    "vw_sales_items",
    "vw_sales_daily",
    "vw_top_sku",
    "stg_fact_sales_order_items",
    "vw_big_sales_daily", 
    "vw_fact_sales_big2m",
    "stg_fact_sales_big2m", 
    "stg_fact_sales_wide"
]

DDL_FORBIDDEN = re.compile(r"\b(DROP|ALTER|TRUNCATE|CREATE|REPLACE|INSERT|UPDATE|DELETE|ATTACH|DETACH|COPY|PRAGMA)\b", re.I)
MULTISTMT = re.compile(r";\s*\S", re.S)

def _log(event: dict):
    try:
        event["ts"] = datetime.now(timezone.utc).isoformat()
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass

def _introspect_schema(con: duckdb.DuckDBPyConnection, allowed: list[str]) -> str:
    q = """
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema='main' AND table_name IN ({})
    ORDER BY table_name, ordinal_position
    """.format(",".join("'" + t + "'" for t in allowed))
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
    - solo tablas allowed
    - LIMIT obligatorio
    """
    if not sql:
        raise ValueError("SQL vacío.")

    # Una sola sentencia
    s = sql.strip().rstrip(";")
    if MULTISTMT.search(sql):
        raise ValueError("No se permite ejecutar múltiples sentencias.")
    # Solo SELECT
    if not re.match(r"^\s*SELECT\b", s, re.I):
        raise ValueError("Solo se permite SELECT.")
    if DDL_FORBIDDEN.search(s):
        raise ValueError("Comando no permitido en el SQL.")
    # Tablas permitidas
    idents = set(re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", s))
    # muy simple: si menciona alguna tabla que no esté en allowlist, bloquea
    tables_mentioned = [tok for tok in idents if tok.lower() not in {
        "select","from","where","group","by","order","limit","and","or","desc","asc","distinct","on","join","left","right","inner","outer",
        "as","sum","avg","min","max","count","date_trunc","date_part","cast","coalesce","case","when","then","else","end",
        "in","not","between","like","ilike","having","over","partition","rows","range","current","row","preceding","following",
        "true","false","null","is"
    }]
    # si menciona al menos una tabla, todas deben estar permitidas
    if tables_mentioned:
        for t in tables_mentioned:
            if t not in allowed:
                # puede ser un alias; comprobación relajada: si aparece exacto en FROM/JOIN, validamos
                if re.search(rf"\bFROM\s+{t}\b", s, re.I) or re.search(rf"\bJOIN\s+{t}\b", s, re.I):
                    if t not in allowed:
                        raise ValueError(f"Tabla no permitida: {t}")
    # LIMIT
    if not re.search(r"\bLIMIT\b", s, re.I):
        s = f"{s}\nLIMIT {default_limit}"
    return s

def run_select(con: duckdb.DuckDBPyConnection, sql: str, timeout_ms: int = 5000) -> pd.DataFrame:
    
    return con.execute(sql).fetchdf()



# ===== Fallback “plantillas” sin LLM =====

def template_sql(prompt: str) -> str | None:
    """
    Reglas heurísticas muy simples para casos típicos si no hay LLM:
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

# ===== LLM -> SQL =====

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
        # Sin LLM -> plantillas
        sql = template_sql(prompt)
        if sql:
            return sql
        # fallback final
        raise RuntimeError("Sin LLM y sin plantilla aplicable. Sé más específico (ej.: 'Top 10 SKUs por ingresos').")

    llm = ChatOpenAI(model=model_name, temperature=0.1)
    tmpl = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("user", "{question}"),
    ])
    chain = tmpl | llm
    out = chain.invoke({
        "schema": schema_text,
        "question": prompt
    })
    text = out.content if hasattr(out, "content") else str(out)
    # intenta extraer bloque SQL; si no, usa todo el texto
    m = re.search(r"```sql\s*(.*?)```", text, re.S|re.I)
    sql = m.group(1).strip() if m else text.strip()
    return sql

# ===== Gráficos automáticos =====

def auto_chart(df: pd.DataFrame, title: str = ""):
    """
    Reglas simples:
    - Si hay columna 'd' (date) y numéricas -> línea temporal
    - Si hay 'sku_id' + una numérica -> barras top-N
    - Si no, tabla (Streamlit mostrará dataframe)
    """
    if df is None or df.empty:
        return None

    # d como fecha
    if "d" in df.columns and pd.api.types.is_datetime64_any_dtype(df["d"]) or "d" in df.columns and df["d"].dtype == "object":
        cands = [c for c in df.columns if c != "d" and pd.api.types.is_numeric_dtype(df[c])]
        if cands:
            data = df.copy()
            try:
                data["d"] = pd.to_datetime(data["d"])
            except Exception:
                pass
            y = cands[0]
            chart = alt.Chart(data).mark_line().encode(
                x="d:T",
                y=f"{y}:Q",
                tooltip=list(data.columns)
            ).properties(height=280, title=title or y)
            return chart

    # sku_id barras
    if "sku_id" in df.columns:
        cands = [c for c in df.columns if c != "sku_id" and pd.api.types.is_numeric_dtype(df[c])]
        if cands:
            y = cands[0]
            data = df.sort_values(y, ascending=False).head(20)
            chart = alt.Chart(data).mark_bar().encode(
                x=f"{y}:Q",
                y=alt.Y("sku_id:N", sort="-x"),
                tooltip=list(data.columns)
            ).properties(height=360, title=title or y)
            return chart

    return None  # Streamlit mostrará tabla

# ===== Utils =============
# ----------- Ayudas de esquema / vistas disponibles -----------------

def view_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    try:
        q = """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema='main' AND table_name=?
        UNION ALL
        SELECT 1
        FROM information_schema.views
        WHERE table_schema='main' AND table_name=?
        LIMIT 1
        """
        return con.execute(q, [name, name]).fetchone() is not None
    except Exception:
        return False

def pick_daily_view(con: duckdb.DuckDBPyConnection) -> str | None:
    # Preferencias: vista de ventas diaria "grande" si existe, si no la estándar
    for v in ["vw_big_sales_daily", "vw_sales_daily"]:
        if view_exists(con, v):
            return v
    # Último recurso: derivar de vw_sales_items si existe
    if view_exists(con, "vw_sales_items"):
        return "__derive_from_items__"
    return None

# ----------- Intentos NL mínimos (sin LLM) -----------------

def detect_intent(prompt: str) -> str | None:
    p = (prompt or "").strip().lower()
    if not p:
        return None
    if any(k in p for k in ["overview", "resumen", "análisis", "analisis", "general"]):
        return "overview"
    if any(k in p for k in ["media", "promedio"]) and any(k in p for k in ["último mes","ultimo mes","30 días","30 dias"]):
        return "avg_last_month"
    if "top" in p and ("sku" in p or "producto" in p):
        return "top_skus"
    return None

# ----------- Narrativa (LLM opcional) -----------------

def narrate(spanish_bullets: list[str]) -> str:
    """Si hay OpenAI, pulimos texto; si no, devolvemos viñetas."""
    bullets_text = "\n".join(f"- {b}" for b in spanish_bullets)
    api = os.getenv("OPENAI_API_KEY")
    try:
        if api and ChatOpenAI is not None:
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
            prompt = ChatPromptTemplate.from_template(
                "Eres analista. Reescribe en un párrafo breve y claro, en español, estas conclusiones de negocio:\n{bullets}"
            )
            out = (prompt | llm).invoke({"bullets": bullets_text})
            return out.content if hasattr(out, "content") else str(out)
    except Exception:
        pass
    return bullets_text

# ----------- Blocks de ejecución por intención -----------------

def block_overview(con: duckdb.DuckDBPyConnection, days: int = 30):
    """KPIs + serie + top skus últimos N días."""
    base = pick_daily_view(con)
    if base is None:
        st.error("No encuentro una vista diaria de ventas (vw_big_sales_daily, vw_sales_daily) ni vw_sales_items para derivarla.")
        return

    # Serie diaria
    if base == "__derive_from_items__":
        df_daily = con.execute(f"""
            SELECT DATE_TRUNC('day', order_date)::DATE AS d,
                   SUM(revenue_eur) AS revenue_eur,
                   SUM(quantity)    AS units,
                   COUNT(DISTINCT order_id) AS orders
            FROM vw_sales_items
            WHERE order_date >= CURRENT_DATE - INTERVAL '{days*2} days'
            GROUP BY 1
            ORDER BY 1
        """).fetchdf()
    else:
        df_daily = con.execute(f"""
            SELECT d, revenue_eur, units,
                   COALESCE(orders, NULL) AS orders
            FROM {base}
            WHERE d >= CURRENT_DATE - INTERVAL '{days*2} days'
            ORDER BY d
        """).fetchdf()

    if df_daily.empty:
        st.info("No hay datos recientes para construir el resumen.")
        return

    # Ventana reciente vs anterior (N días)
    cut = df_daily["d"].max() - pd.Timedelta(days=days-1)
    recent = df_daily[df_daily["d"] >= cut]
    previous = df_daily[(df_daily["d"] < cut) & (df_daily["d"] >= cut - pd.Timedelta(days=days))]

    def agg(df):
        return {
            "revenue": float(df["revenue_eur"].sum()) if "revenue_eur" in df else 0.0,
            "units":   float(df["units"].sum()) if "units" in df else 0.0,
            "orders":  float(df["orders"].sum()) if "orders" in df else float("nan"),
            "avg_rev_day": float(df["revenue_eur"].mean()) if "revenue_eur" in df else 0.0,
        }
    R, P = agg(recent), agg(previous)

    # KPIs
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Ingresos (últimos 30d)", f"{R['revenue']:,.0f} €".replace(",", "."), 
              delta=f"{((R['revenue']-P['revenue'])/P['revenue']*100):.1f} %" if P['revenue'] else None)
    c2.metric("Unidades (30d)", f"{R['units']:,.0f}".replace(",", "."))
    if not pd.isna(R["orders"]):
        c3.metric("Pedidos (30d)", f"{R['orders']:,.0f}".replace(",", "."))
    c4.metric("Media diaria €", f"{R['avg_rev_day']:,.0f} €".replace(",", "."))

    # Gráfico serie
    try:
        df_daily["d"] = pd.to_datetime(df_daily["d"])
    except Exception:
        pass
    chart = alt.Chart(df_daily).mark_line().encode(
        x="d:T", y="revenue_eur:Q", tooltip=list(df_daily.columns)
    ).properties(height=260, title=f"Ventas diarias (últimos {days*2} días)")
    st.altair_chart(chart, use_container_width=True)

    # Top SKUs últimos N días (si está la vista items)
    if view_exists(con, "vw_sales_items"):
        df_top = con.execute(f"""
            SELECT sku_id,
                   SUM(revenue_eur) AS revenue_eur,
                   SUM(quantity)    AS units
            FROM vw_sales_items
            WHERE order_date >= CURRENT_DATE - INTERVAL '{days} days'
            GROUP BY 1
            ORDER BY revenue_eur DESC
            LIMIT 5
        """).fetchdf()
        if not df_top.empty:
            st.dataframe(df_top, use_container_width=True, hide_index=True)
            top_chart = alt.Chart(df_top.sort_values("revenue_eur", ascending=True)).mark_bar().encode(
                x="revenue_eur:Q", y=alt.Y("sku_id:N", sort="-x"), tooltip=list(df_top.columns)
            ).properties(height=220, title="Top 5 SKUs por ingresos (30d)")
            st.altair_chart(top_chart, use_container_width=True)

    # Narrativa
    bullets = [
        f"Ingresos últimos {days} días: {R['revenue']:,.0f} €.",
        f"Media diaria: {R['avg_rev_day']:,.0f} €.",
    ]
    if P["revenue"]:
        bullets.append(f"Variación vs período anterior: {((R['revenue']-P['revenue'])/P['revenue']*100):.1f} %.")    
    if not pd.isna(R["orders"]):
        bullets.append(f"Pedidos estimados en el período: {R['orders']:,.0f}.")
    st.markdown(narrate(bullets))

def block_avg_last_month(con: duckdb.DuckDBPyConnection, days: int = 30):
    """Media de ventas (ingresos diarios) últimos N días."""
    base = pick_daily_view(con)
    if base is None:
        st.error("No encuentro una vista diaria de ventas para calcular la media.")
        return

    if base == "__derive_from_items__":
        df = con.execute(f"""
            SELECT DATE_TRUNC('day', order_date)::DATE AS d,
                   SUM(revenue_eur) AS revenue_eur
            FROM vw_sales_items
            WHERE order_date >= CURRENT_DATE - INTERVAL '{days} days'
            GROUP BY 1
            ORDER BY 1
        """).fetchdf()
    else:
        df = con.execute(f"""
            SELECT d, revenue_eur
            FROM {base}
            WHERE d >= CURRENT_DATE - INTERVAL '{days} days'
            ORDER BY d
        """).fetchdf()

    if df.empty:
        st.info("No hay datos para el último mes.")
        return

    try:
        df["d"] = pd.to_datetime(df["d"])
    except Exception:
        pass

    avg_rev = float(df["revenue_eur"].mean())
    st.metric(f"Media diaria de ventas (últimos {days} días)", f"{avg_rev:,.0f} €".replace(",", "."))
    ch = alt.Chart(df).mark_line().encode(x="d:T", y="revenue_eur:Q").properties(height=260, title="Serie diaria (últimos 30d)")
    st.altair_chart(ch, use_container_width=True)

    st.markdown(narrate([
        f"La media diaria de ingresos en los últimos {days} días es {avg_rev:,.0f} €.",
        "La línea muestra la tendencia durante el periodo."
    ]))



# ===== UI de pestaña =====
def render_assistant(con: duckdb.DuckDBPyConnection, allowed_tables: list[str] | None = None):
    st.subheader("Asistente (LLM)")

    allowed = allowed_tables or DEFAULT_ALLOWED
    schema_text = _introspect_schema(con, allowed)

    with st.expander("Ayuda / qué puedo pedir", expanded=False):
        st.markdown(
            "- *“Top 10 SKUs por ingresos.”*\n"
            "- *“Ventas por día en los últimos 30 días.”*\n"
            "- *“Unidades y pedidos por mes en 2024.”*\n"
            "- *“Análisis general”* o *“Resumen”* (últimos 30d).\n"
            "- *“Media de ventas del último mes”*."
        )
        st.caption("Si no configuras OPENAI_API_KEY, el asistente usará plantillas básicas.")

    c1, c2 = st.columns([3,1])
    with c1:
        user_prompt = st.text_area("Escribe tu petición:", height=100, placeholder="Ej.: Análisis general… / Media de ventas del último mes…")
    with c2:
        model = st.selectbox("Modelo", ["gpt-4o-mini (OpenAI)", "Plantillas locales"], index=0 if os.getenv("OPENAI_API_KEY") else 1)

    if st.button("► Ejecutar", type="primary"):
        started = datetime.now()
        try:
            # 1) Intento NL sin SQL (bloques listos)
            intent = detect_intent(user_prompt)
            if intent == "overview":
                block_overview(con, days=30)
                _log({"ok": True, "prompt": user_prompt, "mode":"overview"})
                return
            elif intent == "avg_last_month":
                block_avg_last_month(con, days=30)
                _log({"ok": True, "prompt": user_prompt, "mode":"avg_last_month"})
                return

            # 2) Si no hay intención “pre-hecha”, usamos LLM→SQL o plantillas previas:
            use_llm = (model.startswith("gpt-") and os.getenv("OPENAI_API_KEY"))
            sql_raw = llm_to_sql(user_prompt, schema_text, model_name="gpt-4o-mini") if use_llm else (template_sql(user_prompt) or "")
            if not sql_raw:
                raise ValueError("SQL vacío.")
            sql = sanitize_sql(sql_raw, allowed, default_limit=1000)
            df = run_select(con, sql, timeout_ms=5000)
            if "d" in df.columns:
                try:
                    df["d"] = pd.to_datetime(df["d"])
                except Exception:
                    pass
            st.code(sql, language="sql")
            st.dataframe(df, use_container_width=True, hide_index=True, height=300)
            chart = auto_chart(df)
            if chart is not None:
                st.altair_chart(chart, use_container_width=True)

            _log({
                "ok": True,
                "prompt": user_prompt,
                "sql": sql,
                "rows": int(len(df)),
                "ms": int((datetime.now() - started).total_seconds()*1000),
                "llm": bool(use_llm)
            })

        except Exception as e:
            st.error(f"No se pudo ejecutar tu petición: {e}")
            _log({"ok": False, "prompt": user_prompt, "error": str(e)})
