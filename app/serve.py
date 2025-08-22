# -*- coding: utf-8 -*-
"""
Nitida v0.5.0 — UI mínima para Paco
- Ejecutar cargas (llama al runner)
- Estado (etl_runs / etl_metrics)
- Explorar tablas DuckDB
- Descargar Parquet en .zip
- NL→SQL sencillo con guardrails (mostrar SQL antes de ejecutar)

Run:
  streamlit run app/serve.py
"""
from __future__ import annotations
import os
import io
import sys
import time
import zipfile
import subprocess
from datetime import datetime, timezone

import duckdb
import pandas as pd
import streamlit as st
from pathlib import Path

import os, sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Importa utilidades del runner
from app.runner import ensure_ledger
from app.nl2sql_simple import nl_to_sql

DB_PATH = "data/warehouse.duckdb"
PARQUET_DIR = "data/parquet"

# ---------- helpers ----------
@st.cache_resource(show_spinner=False)
def get_con():
    os.makedirs("data", exist_ok=True)
    ensure_ledger(DB_PATH)
    con = duckdb.connect(DB_PATH)
    return con

def list_tables(con) -> list[str]:
    sql = """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema='main' AND table_type='BASE TABLE'
    ORDER BY 1
    """
    return con.execute(sql).fetchdf()["table_name"].tolist()

def run_runner(group: str) -> tuple[int, str]:
    cmd = [sys.executable, "-m", "app.runner", "--group", group]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return proc.returncode, out

def fetch_df(con, sql: str) -> pd.DataFrame:
    try:
        return con.execute(sql).fetchdf()
    except Exception as e:
        st.error(f"Error ejecutando SQL: {e}")
        return pd.DataFrame()

def zip_parquet(base_dir: str) -> io.BytesIO | None:
    if not os.path.isdir(base_dir):
        return None
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(base_dir):
            for f in files:
                if f.endswith(".parquet"):
                    path = os.path.join(root, f)
                    arc = os.path.relpath(path, base_dir)
                    z.write(path, arcname=arc)
    buf.seek(0)
    return buf

# ---------- UI ----------
st.set_page_config(page_title="Nitida", page_icon="✨", layout="wide")
st.title("✨ Nitida — Datos nítidos, decisiones seguras")

con = get_con()

# Sidebar
st.sidebar.header("Acciones")
group = st.sidebar.selectbox("Grupo a ejecutar", ["daily"])
if st.sidebar.button("🚀 Ejecutar carga ahora"):
    with st.spinner("Ejecutando…"):
        code, logs = run_runner(group)
    st.session_state["runner_logs"] = logs
    if code == 0:
        st.success("Carga completada")
    else:
        st.error("Carga finalizada con errores")
    with st.expander("Ver logs de la ejecución"):
        st.code(st.session_state.get("runner_logs", ""), language="bash")

# Tabs principales
tab_status, tab_tables, tab_nlsql, tab_downloads = st.tabs(
    ["Estado", "Tablas", "Preguntar a mis datos", "Descargas"]
)

# ---- Estado ----
with tab_status:
    col1, col2 = st.columns([2, 3], gap="large")

    with col1:
        st.subheader("Últimas ejecuciones")
        runs = fetch_df(
            con,
            """
            SELECT run_id, started_at, finished_at, group_name, status, rows_total, duration_s
            FROM etl_runs
            ORDER BY started_at DESC
            LIMIT 20
            """,
        )
        if not runs.empty:
            st.dataframe(runs, use_container_width=True, height=430)
        else:
            st.info("Aún no hay ejecuciones registradas.")

    with col2:
        st.subheader("Métricas recientes por fuente")
        m = fetch_df(
            con,
            """
            SELECT run_id, source_name, table_name, rows_loaded, dq_pass, dq_violations, duration_s, loaded_at
            FROM etl_metrics
            ORDER BY loaded_at DESC
            LIMIT 100
            """,
        )
        if not m.empty:
            st.dataframe(m, use_container_width=True, height=430)
        else:
            st.info("Aún no hay métricas.")

# ---- Tablas ----
with tab_tables:
    st.subheader("Explorar tablas")
    tables = list_tables(con)
    if not tables:
        st.info("No hay tablas creadas todavía. Ejecuta una carga en la barra lateral.")
    else:
        tsel = st.selectbox("Tabla", tables)
        limit = st.slider("Filas a mostrar", min_value=10, max_value=1000, value=100, step=10)
        sql_preview = f"SELECT * FROM {tsel} LIMIT {limit}"
        st.code(sql_preview, language="sql")
        dfp = fetch_df(con, sql_preview)
        if not dfp.empty:
            st.dataframe(dfp, use_container_width=True, height=480)

        st.markdown("—")
        st.markdown("**Consulta SQL avanzada (opcional)**")
        user_sql = st.text_area("Escribe tu SQL y ejecútalo bajo tu responsabilidad", value=f"SELECT COUNT(*) AS filas FROM {tsel}")
        if st.button("▶ Ejecutar SQL"):
            dfa = fetch_df(con, user_sql)
            if not dfa.empty:
                st.dataframe(dfa, use_container_width=True, height=420)

# ---- NL→SQL sencillo con guardrails ----
with tab_nlsql:
    st.subheader("Preguntar a mis datos (NL→SQL con confirmación)")
    q = st.text_input("Ejemplo: '¿Cuántas lecturas PM2.5 hay este mes?'  ·  ‘Top 10 magnitudes de terremotos’")
    if "proposed_sql" not in st.session_state:
        st.session_state["proposed_sql"] = ""

    tables = list_tables(con)
    if st.button("🧠 Proponer SQL"):
        sql, msg = nl_to_sql(q, tables=tables)
        st.session_state["proposed_sql"] = sql or ""
        if msg:
            st.info(msg)

    if st.session_state.get("proposed_sql"):
        st.markdown("**SQL propuesto (revísalo antes de ejecutar):**")
        st.code(st.session_state["proposed_sql"], language="sql")
        if st.button("✅ Ejecutar SQL propuesto"):
            dfq = fetch_df(con, st.session_state["proposed_sql"])
            if not dfq.empty:
                st.dataframe(dfq, use_container_width=True, height=430)

# ---- Descargas ----
with tab_downloads:
    st.subheader("Descargar Parquet")
    buf = zip_parquet(PARQUET_DIR)
    if buf is None:
        st.info("Aún no hay ficheros Parquet exportados.")
    else:
        st.download_button(
            "⬇️ Descargar Parquet (.zip)",
            data=buf,
            file_name=f"nitida_parquet_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip",
        )

# === MODO SEGURO: ejecutar runner y refrescar KPIs SIN bloquear el arranque ===

try:
    settings = load_settings()  # si no está importado arriba, añade: from app.utils import load_settings
except Exception:
    settings = {"paths": {"db_path": "data/warehouse.duckdb"}}

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = settings["paths"]["db_path"]

@st.cache_resource(show_spinner=False)
def _con():
    return duckdb.connect(DB_PATH)

def _run_group_safe(group: str):
    # Preferimos ejecución "en memoria" (sin subprocess) para evitar problemas de encoding del proceso hijo.
    with st.status(f"Ejecutando '{group}'…", expanded=True) as s:
        try:
            # Import tardío para no romper el arranque de Streamlit si hubiera errores en el runner
            from app.runner import run_group, load_yaml, ensure_ledger

            # 1) Asegura ledger y conexión
            ensure_ledger(DB_PATH)
            # 2) Carga de YAML de fuentes y DQ
            cfg = load_yaml("config/sources.yml")
            dq = load_yaml("config/dq.yml")
            # 3) Ejecuta el grupo directamente (misma sesión Python que la UI)
            run_group(group, cfg, dq)

            s.update(label="Completado", state="complete")
            st.toast("Carga finalizada", icon="✅")
        except Exception as e:
            # Fallback a subprocess SOLO si algo impide el modo librería (p.ej. import roto)
            import sys, subprocess, os
            st.warning(f"No se pudo ejecutar en modo librería ({e}). Intentando en subprocess…")
            env = os.environ.copy()
            # Fuerza UTF-8 en el hijo por si el sistema no lo trae (Windows)
            env["PYTHONUTF8"] = "1"
            ROOT = Path(__file__).resolve().parents[1]
            res = subprocess.run(
                [sys.executable, "-m", "app.runner", "--group", group],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                env=env,
            )
            if res.stdout:
                st.code(res.stdout, language="bash")
            if res.returncode != 0:
                s.update(label="Fallo en runner (subprocess)", state="error")
                if res.stderr:
                    st.code(res.stderr, language="bash")
            else:
                s.update(label="Completado (subprocess)", state="complete")
                st.toast("Carga finalizada", icon="✅")

st.divider()
st.subheader("Modo seguro — ejecutar y refrescar")
c1, c2 = st.columns(2)
with c1:
    if st.button("▶ Ejecutar daily (modo seguro)"):
        _run_group_safe("daily")
        st.rerun()
with c2:
    if st.button("↻ Refrescar métricas"):
        st.rerun()

# KPIs básicos (lectura perezosa, no bloquea el arranque)
try:
    con = _con()
    runs = con.execute("""
        SELECT run_id, started_at, finished_at, group_name, status, rows_total, duration_s
        FROM etl_runs ORDER BY started_at DESC LIMIT 10
    """).fetchdf()
    st.dataframe(runs, use_container_width=True, height=260, hide_index=True)
except Exception as e:
    st.info(f"No se pudieron leer KPIs: {e}")
