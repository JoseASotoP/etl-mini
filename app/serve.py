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
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Importa utilidades del runner
from app.runner import ensure_ledger
from app.nl2sql_simple import nl_to_sql
from app.utils import load_settings

DB_PATH = "data/warehouse.duckdb"
PARQUET_DIR = "data/parquet"

# ---------- helpers ----------
@st.cache_resource(show_spinner=False)
def get_con():
    """
    Devuelve una conexión a DuckDB, asegurando que el ledger existe.

    Returns
    -------
    duckdb.DuckDBPyConnection
    """
    os.makedirs("data", exist_ok=True)
    ensure_ledger(DB_PATH)
    con = duckdb.connect(DB_PATH)
    return con


def list_tables(con) -> list[str]:
    """
    Lista todas las tablas base de la base de datos.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection

    Returns
    -------
    list[str]
        Nombres de tablas.
    """
    sql = """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema='main' AND table_type='BASE TABLE'
    ORDER BY 1
    """
    return con.execute(sql).fetchdf()["table_name"].tolist()


def run_runner(group: str) -> tuple[int, str]:
    """
    Ejecuta el runner como subproceso.

    Parameters
    ----------
    group : str
        Grupo a ejecutar.

    Returns
    -------
    tuple[int, str]
        (exit_code, logs)
    """
    cmd = [sys.executable, "-m", "app.runner", "--group", group]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return proc.returncode, out


def fetch_df(con, sql: str) -> pd.DataFrame:
    """
    Ejecuta una consulta SQL y devuelve DataFrame seguro.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
    sql : str

    Returns
    -------
    pandas.DataFrame
    """
    try:
        return con.execute(sql).fetchdf()
    except Exception as e:
        st.error(f"Error ejecutando SQL: {e}")
        return pd.DataFrame()


def zip_parquet(base_dir: str) -> io.BytesIO | None:
    """
    Comprime ficheros Parquet en un ZIP en memoria.

    Parameters
    ----------
    base_dir : str
        Directorio base donde buscar .parquet.

    Returns
    -------
    io.BytesIO | None
    """
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

# === HOME · KPIs + CTAs (no destructivo) =====================================
# Reutiliza settings/DB_PATH si ya existen; si no, define fallback seguro
try:
    DB_PATH  # ya definido
except NameError:
    try:
        settings = load_settings()
        DB_PATH = settings["paths"]["db_path"]
    except Exception:
        DB_PATH = "data/warehouse.duckdb"

ROOT = Path(__file__).resolve().parents[1]


@st.cache_resource(show_spinner=False)
def _con_uiux():
    """
    Conexión caché para la portada HOME.

    Returns
    -------
    duckdb.DuckDBPyConnection
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return duckdb.connect(DB_PATH)


def _last_run_info(con) -> dict:
    """
    Devuelve información del último run registrado.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection

    Returns
    -------
    dict
        {'status': str, 'rows_total': int, 'finished_at_local': str}
    """
    try:
        df = con.execute("""
            SELECT status, rows_total, finished_at
            FROM etl_runs
            ORDER BY started_at DESC
            LIMIT 1
        """).fetchdf()
        if df.empty:
            return {"status": "—", "rows_total": 0, "finished_at_local": "—"}
        status = str(df.loc[0, "status"])
        rows_total = int(df.loc[0, "rows_total"] or 0)
        finished_at = df.loc[0, "finished_at"]
        if isinstance(finished_at, str):
            dt = datetime.fromisoformat(finished_at)
        elif isinstance(finished_at, pd.Timestamp):
            dt = finished_at.to_pydatetime()
        else:
            dt = finished_at
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            finished_local = dt.astimezone().strftime("%Y-%m-%d %H:%M:%S (%Z)")
        else:
            finished_local = "—"
        return {"status": status, "rows_total": rows_total, "finished_at_local": finished_local}
    except Exception:
        return {"status": "—", "rows_total": 0, "finished_at_local": "—"}


def _run_today_library_then_fallback(group: str = "daily"):
    """
    Ejecuta un grupo con preferencia modo librería y fallback a subprocess.

    Parameters
    ----------
    group : str
        Grupo a ejecutar.
    """
    with st.status(f"Ejecutando grupo '{group}'…", expanded=True) as status:
        try:
            from app.runner import run_group, ensure_ledger, load_yaml
            ensure_ledger(DB_PATH)
            cfg = load_yaml("config/sources.yml")
            dq = load_yaml("config/dq.yml")
            run_group(group, cfg, dq)
            status.update(label="Runner OK (modo librería)", state="complete")
            st.toast("Carga completada ✅", icon="✅")
            return
        except Exception as e:
            st.write("Fallo en modo librería, intentamos subprocess…")
            st.code(str(e), language="text")

        res = subprocess.run(
            [sys.executable, "-m", "app.runner", "--group", group],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        if res.stdout:
            st.code(res.stdout, language="bash")
        if res.returncode != 0:
            status.update(label="Runner terminó con error (subprocess)", state="error")
            if res.stderr:
                st.code(res.stderr, language="bash")
            st.error("Fallo al ejecutar el runner.")
        else:
            status.update(label="Runner OK (subprocess)", state="complete")
            st.toast("Carga completada ✅", icon="✅")


def _save_uploaded_files(files):
    """
    Guarda los ficheros subidos en data/input.

    Parameters
    ----------
    files : list
        Lista de ficheros (UploadedFile).

    Returns
    -------
    list[str]
        Rutas guardadas.
    """
    saved = []
    in_dir = Path("data/input")
    in_dir.mkdir(parents=True, exist_ok=True)
    for f in files or []:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = os.path.basename(f.name).replace(" ", "_")
        out = in_dir / f"{ts}__{safe_name}"
        with open(out, "wb") as w:
            w.write(f.getbuffer())
        saved.append(str(out))
    return saved


# ======= RENDER HOME =======
st.header("Mi Negocio (MVP)")
con_home = _con_uiux()
info = _last_run_info(con_home)
k1, k2, k3 = st.columns(3)
with k1:
    st.metric("Último estado", info["status"])
with k2:
    st.metric("Filas cargadas (último run)", f"{info['rows_total']:,}")
with k3:
    st.metric("Fin de ejecución", f"{info['finished_at_local']}  — hora local")

c1, c2, c3 = st.columns(3)
with c1:
    if st.button("▶ Ejecutar hoy", type="primary", use_container_width=True):
        _run_today_library_then_fallback("daily")
        st.rerun()
with c2:
    up = st.file_uploader("⬆️ Subir CSV/XLSX", type=["csv", "xlsx"], accept_multiple_files=True)
    if up:
        saved = _save_uploaded_files(up)
        st.toast(f"{len(saved)} archivo(s) guardado(s) en data/input/", icon="📁")
        with st.expander("Archivos guardados", expanded=False):
            for s in saved:
                st.write(s)
with c3:
    if st.button("📄 Generar informe", use_container_width=True):
        try:
            from app.report import assemble_report
            out = assemble_report()
            st.success("Informe generado")
            st.markdown(f"[Abrir informe]({out})")
        except Exception as e:
            st.error(f"No se pudo generar el informe: {e}")

st.divider()
# === Fin HOME ===

# ... aquí siguen tus tabs originales, Modo seguro, etc. (sin tocar) ...
