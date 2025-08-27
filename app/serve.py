# -*- coding: utf-8 -*-
"""
Nítida — UI mínima para etl-mini

- Ejecutar cargas (runner)
- Estado (etl_runs / etl_metrics)
- Explorar tablas DuckDB
- Descargar informe HTML bajo demanda
- Subir e importar CSV/XLSX a DuckDB (stg_*)

Run:
    streamlit run app/serve.py
"""
from __future__ import annotations
# añade este import con fallback
try:
    from app.assistant import render_assistant
    ASSISTANT_OK = True
    ASSISTANT_ERR = ""
except Exception as _e:
    render_assistant = None
    ASSISTANT_OK = False
    ASSISTANT_ERR = str(_e)


import io
import os
import sys
import re
import subprocess
from pathlib import Path
from datetime import datetime, timezone

import duckdb
import pandas as pd
import streamlit as st

# --------------------------- Config básica ---------------------------

try:
    from app.utils import load_settings  # opcional
except Exception:
    load_settings = None  # fallback

DEFAULT_SETTINGS = {
    "paths": {
        "db_path": "data/warehouse.duckdb",
        "reports_dir": "data/reports",
    },
    "project": {"name": "etl-mini (Nítida)", "version": "0.5.0"},
}

def get_settings() -> dict:
    if load_settings:
        try:
            return load_settings()
        except Exception:
            pass
    return DEFAULT_SETTINGS

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

def df_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "Datos") -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name=sheet_name)
    buf.seek(0)
    return buf.read()

SET = get_settings()
ROOT = Path(__file__).resolve().parents[1]
DB_PATH = (SET.get("paths") or {}).get("db_path", "data/warehouse.duckdb")
REPORTS_DIR = Path((SET.get("paths") or {}).get("reports_dir", "data/reports"))
INPUT_DIR = ROOT / "data" / "input"
INPUT_DIR.mkdir(parents=True, exist_ok=True)
SHOW_DEMO_RUNNER = True 


st.set_page_config(page_title="Nítida · ETL-mini", layout="wide")
st.title("Nítida — ETL mini")
st.caption("KPIs rápidos, acciones clave y utilidades sobre DuckDB.")

# --------------------------- Conexión ---------------------------

@st.cache_resource(show_spinner=False)
def get_con():
    import shutil
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    try:
        return duckdb.connect(DB_PATH)
    except UnicodeDecodeError:
        # Base dañada o fichero no-DuckDB: respalda y recrea
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            if os.path.exists(DB_PATH):
                shutil.move(DB_PATH, f"{DB_PATH}.bad_{ts}")
            wal = DB_PATH + ".wal"
            if os.path.exists(wal):
                shutil.move(wal, f"{wal}.bad_{ts}")
        except Exception:
            pass
        return duckdb.connect(DB_PATH)


def table_or_view_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    q = """
    SELECT 1 FROM information_schema.tables WHERE table_schema='main' AND table_name=?
    UNION ALL
    SELECT 1 FROM information_schema.views  WHERE table_schema='main' AND table_name=?
    LIMIT 1
    """
    return bool(con.execute(q, [name, name]).fetchone())

def df_safe(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    try:
        return con.execute(sql).fetchdf()
    except Exception:
        return pd.DataFrame()
        
def render_schema_graph(con: duckdb.DuckDBPyConnection):
    st.subheader("Esquema de datos (auto)")
    cols = con.execute("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema='main'
    """).fetchdf()

    tables = set(cols["table_name"].unique())
    edges = set()
    for _, row in cols.iterrows():
        t = row["table_name"]; c = row["column_name"]
        if c.endswith("_id"):
            base = c[:-3]
            # heurística: dim_<base> o stg_<base>s
            targets = [f"dim_{base}", f"stg_{base}s", f"{base}", f"{base}s"]
            for tgt in targets:
                if tgt in tables and tgt != t:
                    edges.add((t, tgt))

    dot = ["digraph G { rankdir=LR; node [shape=box, style=rounded];"]
    for t in sorted(tables):
        dot.append(f'"{t}";')
    for a, b in sorted(edges):
        dot.append(f'"{a}" -> "{b}";')
    dot.append("}")
    st.graphviz_chart("\n".join(dot), use_container_width=True)

# --------------------------- Helpers ---------------------------
def last_run_summary(con: duckdb.DuckDBPyConnection) -> str | None:
    try:
        q = """
        WITH last AS (SELECT MAX(started_at) AS mx FROM etl_runs)
        SELECT r.run_id,
               COALESCE(SUM(m.rows_loaded),0) AS rows_loaded,
               COUNT(m.table_name)            AS tables_loaded,
               BOOL_AND(COALESCE(m.dq_pass, TRUE)) AS all_pass
        FROM etl_runs r
        LEFT JOIN etl_metrics m USING(run_id)
        WHERE r.started_at = (SELECT mx FROM last)
        GROUP BY r.run_id
        """
        df = con.execute(q).fetchdf()
        if df.empty:
            return None
        row = df.iloc[0]
        ok = "OK" if bool(row.get("all_pass", True)) else "con incidencias"
        return f"Carga {row['run_id']}: {int(row['tables_loaded'])} tablas, {int(row['rows_loaded']):,} filas, DQ {ok}."
    except Exception:
        return None

# -------- Report: preparar y devolver contenido para descarga --------
def prepare_report_download(con: duckdb.DuckDBPyConnection) -> tuple[str, bytes]:
    """
    Genera el informe HTML (usando app.report.assemble_report si existe)
    y devuelve (nombre_archivo, contenido_bytes). NO se ejecuta salvo que tú la llames.
    """
    try:
        from app.report import assemble_report
    except Exception:
        def assemble_report():
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            out = REPORTS_DIR / f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.html"
            out.write_text("<html><body><h1>Reporte</h1><p>(dummy)</p></body></html>", encoding="utf-8")
            print(f"Reporte generado: {out}")
            return str(out)

    out_path = assemble_report()
    with open(out_path, "rb") as f:
        data = f.read()
    return Path(out_path).name, data




def last_run_info(con: duckdb.DuckDBPyConnection) -> dict:
    """
    Devuelve info del último run. Si etl_runs.rows_total es NULL/0,
    lo calcula como SUM(rows_loaded) en etl_metrics para ese run_id.
    """
    if not table_or_view_exists(con, "etl_runs"):
        return {}
    df = con.execute("""
        SELECT run_id, status, rows_total, finished_at
        FROM etl_runs
        ORDER BY started_at DESC
        LIMIT 1
    """).fetchdf()
    if df.empty:
        return {}

    row = df.iloc[0]
    run_id = row["run_id"]
    status = row.get("status")

    # rows_total “robusto”
    rows_total = row.get("rows_total")
    try:
        rows_total_val = int(rows_total) if pd.notna(rows_total) else 0
    except Exception:
        rows_total_val = 0
    if rows_total_val == 0 and table_or_view_exists(con, "etl_metrics"):
        try:
            rows_total_val = int(con.execute(
                "SELECT COALESCE(SUM(rows_loaded),0) FROM etl_metrics WHERE run_id = ?",
                [run_id]
            ).fetchone()[0] or 0)
        except Exception:
            rows_total_val = 0

    # fecha local
    finished = row.get("finished_at")
    try:
        if pd.isna(finished):
            local_str = "—"
        else:
            ts = pd.to_datetime(finished, utc=True)
            local_ts = ts.tz_convert(datetime.now().astimezone().tzinfo)
            local_str = local_ts.strftime("%Y-%m-%d %H:%M:%S") + " (hora local)"
    except Exception:
        local_str = str(finished)

    return {
        "run_id": run_id,
        "status": status,
        "rows_total": rows_total_val,
        "finished_local": local_str,
    }


def sanitize_table_name(name: str) -> str:
    base = name.split("#", 1)[0]
    base = Path(base).stem.lower()
    base = re.sub(r"[^a-z0-9_]+", "_", base)
    base = re.sub(r"_+", "_", base).strip("_")
    if not base:
        base = "stg_table"
    return f"stg_{base}"

def import_file_to_duckdb(con: duckdb.DuckDBPyConnection, path: Path) -> tuple[str, int]:
    fname = path.name
    table = sanitize_table_name(fname)
    p = str(path)
    sheet_name = None
    if "#" in fname and (fname.endswith(".xlsx") or fname.endswith(".xls")):
        base, sheet_name = fname.split("#", 1)
        path = path.with_name(base)
        p = str(path)

    if fname.lower().endswith((".csv", ".txt")):
        sql = (
            f"CREATE OR REPLACE TABLE {table} AS "
            f"SELECT * FROM read_csv_auto('{Path(p).as_posix()}', "
            f"HEADER=TRUE, SAMPLE_SIZE=-1, NORMALIZE_NAMES=TRUE)"
        )
        con.execute(sql)
    elif fname.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(p, sheet_name=(sheet_name or 0))
        con.register("df_tmp_import", df)
        con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM df_tmp_import")
        con.unregister("df_tmp_import")
    else:
        raise RuntimeError("Formato no soportado (usa CSV/TXT/XLSX/XLS).")

    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return table, int(n)

# --------------------------- Informe (descarga bajo demanda) ---------------------------

def download_report_button(con: duckdb.DuckDBPyConnection):
    """
    Botón de descarga que genera el reporte SOLO cuando se pulsa.
    No hay generación automática al renderizar la página.
    """
    try:
        from app.report import assemble_report
    except Exception:
        assemble_report = None

    if st.button("📄 Generar y descargar informe", use_container_width=True):
        if assemble_report is None:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            out = REPORTS_DIR / f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.html"
            out.write_text("<html><body><h1>Reporte</h1><p>(dummy)</p></body></html>", encoding="utf-8")
            data = out.read_bytes()
            name = out.name
        else:
            out_path = assemble_report()
            out = Path(out_path)
            data = out.read_bytes()
            name = out.name
        st.download_button(
            "⬇️ Descargar informe (HTML)",
            data=data,
            file_name=name,
            mime="text/html",
            use_container_width=True,
        )
        st.caption(f"Guardado también en: {out}")

# --------------------------- Vistas ---------------------------
def render_home(con: duckdb.DuckDBPyConnection):
    st.subheader("Panel")
    with st.expander("¿Qué hace Nítida? (2 líneas)", expanded=False):
            st.markdown("""
            - **Automatiza**: ingesta de archivos/APIs → limpieza/normalización → tablas/vistas de negocio.
            - **Audita**: guarda runs y métricas en `etl_runs`/`etl_metrics`. **Analiza**: panel, consultas SQL y asistente.
            """)

    k = last_run_info(con)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Último estado", k.get("status", "—"))
    with c2:
        st.metric("Filas del último run", f"{k.get('rows_total', 0):,}".replace(",", "."))
    with c3:
        st.metric("Finalizado", k.get("finished_local", "—"))

    st.markdown("### Acciones rápidas")
    col_run, col_report = st.columns([1, 1])

    # --- Botón Ejecutar hoy (siempre visible) ---
    with col_run:
        if st.button("▶ Ejecutar hoy", use_container_width=True, type="primary"):
            with st.status("Ejecutando grupo 'daily'…", expanded=True) as status:
                try:
                    from app.runner import run_group, load_yaml, ensure_ledger
                    ensure_ledger(DB_PATH)
                    cfg = load_yaml("config/sources.yml")
                    dq  = load_yaml("config/dq.yml")
                    result = run_group("daily", cfg, dq)  # "ok" / "fail"
                    status.update(label=f"Runner OK (status={result})", state="complete")
                    st.success("Carga completada ✅")
                except Exception as e:
                    st.write("Fallo en modo librería, probamos subprocess…")
                    st.code(str(e), language="text")
                    env = os.environ.copy()
                    env["PYTHONUTF8"] = "1"
                    env["PYTHONIOENCODING"] = "utf-8"
                    res = subprocess.run(
                        [sys.executable, "-m", "app.runner", "--group", "daily"],
                        cwd=str(ROOT),
                        capture_output=True,
                        text=True,
                        env=env,
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
                        st.success("Carga completada ✅")
            # refresca métricas sin cerrar la conexión cacheada
            resumen = last_run_summary(con)
            if resumen:
                st.success(resumen)

            st.rerun()


    # --- Informe: solo generar/servir al pulsar ---
    with col_report:
        # preparar/actualizar informe BAJO DEMANDA (no al cargar la página)
        if st.button("📄 Preparar informe", use_container_width=True):
            try:
                name, data = prepare_report_download(con)
                st.session_state["_report_ready"] = (name, data)
                st.success("Informe preparado. Ahora puedes descargarlo.")
            except Exception as e:
                st.error(f"No se pudo preparar el informe: {e}")

        if "_report_ready" in st.session_state:
            name, data = st.session_state["_report_ready"]
            st.download_button(
                "⬇️ Descargar informe (HTML)",
                data=data,
                file_name=name,
                mime="text/html",
                use_container_width=True,
            )
    st.markdown("---")
    st.subheader("Ventas — resumen rápido")
    render_dashboard(con)


# -------- Dash de ventas simple (auto-crea vistas si hay staging) --------
def render_dashboard(con: duckdb.DuckDBPyConnection):
    # 1) Si no existe la staging, mostramos ayuda
    if not table_or_view_exists(con, "stg_fact_sales_order_items"):
        st.info("Sube e importa tu fichero de ventas (CSV/XLSX) en la pestaña **Datos**. "
                "La tabla esperada es **stg_fact_sales_order_items**.")
        return

    # 2) Asegura vistas mínimas (idempotente)
    try:
        con.execute("""
            CREATE OR REPLACE VIEW vw_sales_items AS
            SELECT
              order_id,
              order_item_id,
              sku_id,
              CAST(quantity_units AS BIGINT)      AS quantity,
              CAST(line_total_eur AS DOUBLE)      AS revenue_eur,
              CAST(discount_pct   AS DOUBLE)      AS discount_pct,
              CAST(tax_pct        AS DOUBLE)      AS tax_pct,
              promised_date,
              shipped_date,
              COALESCE(shipped_date, promised_date) AS order_date
            FROM stg_fact_sales_order_items
        """)
        con.execute("""
            CREATE OR REPLACE VIEW vw_sales_daily AS
            SELECT
              DATE_TRUNC('day', order_date)::DATE AS d,
              SUM(revenue_eur)                    AS revenue_eur,
              SUM(quantity)                       AS units,
              COUNT(DISTINCT order_id)            AS orders
            FROM vw_sales_items
            WHERE order_date IS NOT NULL
            GROUP BY 1
            ORDER BY 1
        """)
        con.execute("""
            CREATE OR REPLACE VIEW vw_top_sku AS
            SELECT
              sku_id,
              SUM(revenue_eur) AS revenue_eur,
              SUM(quantity)    AS units
            FROM vw_sales_items
            GROUP BY sku_id
            ORDER BY revenue_eur DESC
            LIMIT 10
        """)
    except Exception as e:
        st.error(f"No se pudieron crear/actualizar las vistas de ventas: {e}")
        return

    # 3) KPIs
    kpi = con.execute("""
        SELECT
          COALESCE(SUM(revenue_eur),0) AS revenue_eur,
          COALESCE(SUM(quantity),0)    AS units,
          COALESCE(COUNT(DISTINCT order_id),0) AS orders
        FROM vw_sales_items
    """).fetchdf()
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Ingresos totales (€)", f"{kpi.loc[0,'revenue_eur']:,.0f}".replace(",", "."))
    with c2: st.metric("Unidades", f"{int(kpi.loc[0,'units']):,}".replace(",", "."))
    with c3: st.metric("Pedidos", f"{int(kpi.loc[0,'orders']):,}".replace(",", "."))

    # 4) Serie temporal
    df_daily = con.execute("SELECT * FROM vw_sales_daily").fetchdf()
    st.line_chart(df_daily.set_index("d")[["revenue_eur", "units"]])

    # 5) Top SKUs
    df_top = con.execute("SELECT * FROM vw_top_sku").fetchdf()
    st.bar_chart(df_top.set_index("sku_id")[["revenue_eur"]])


def render_data(con: duckdb.DuckDBPyConnection):
    st.subheader("Sube tus CSV/XLSX de ventas y mermas")

    uploaded = st.file_uploader(
        "Arrastra aquí archivos CSV/TXT/XLSX/XLS (se guardan en data/input/)",
        type=["csv", "txt", "xlsx", "xls"],
        accept_multiple_files=True,
    )
    if uploaded:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        for uf in uploaded:
            dest = INPUT_DIR / f"{ts}_{uf.name}"
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                f.write(uf.getbuffer())
        st.toast("Archivo(s) guardado(s) en data/input/", icon="✅")

    ALLOWED = {".csv", ".txt", ".xlsx", ".xls"}
    files = sorted(
        [p for p in INPUT_DIR.rglob("*") if p.is_file() and p.suffix.lower() in ALLOWED],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


    if files:
        if st.button("📥 Importar TODO a DuckDB (stg_*)", type="primary", use_container_width=True):
            ok, err = 0, 0
            for p in files:
                try:
                    import_file_to_duckdb(con, p)
                    ok += 1
                except Exception:
                    err += 1
            st.success(f"Importación masiva: {ok} ok, {err} con error.")
            st.rerun()

        st.markdown("#### Archivos guardados (incluye subcarpetas)")
        for p in files[:50]:
            c1, c2, c3, c4 = st.columns([5, 3, 2, 2])
            with c1:
                try:
                    rel = p.relative_to(INPUT_DIR)
                    st.write(str(rel))
                except Exception:
                    st.write(p.name)
            with c2:
                st.code(sanitize_table_name(p.name), language="bash")
            with c3:
                if st.button("Importar", key=f"imp_{p}"):
                    try:
                        table, n = import_file_to_duckdb(con, p)
                        st.success(f"{table}: {n} filas")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            with c4:
                st.caption(f"{int(p.stat().st_size/1024)} KB")
    else:
        st.info("No hay archivos en data/input/ (puedes crear subcarpetas y arrastrar aquí).")

    st.markdown("#### Mis tablas")
    tdf = df_safe(con, """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='main'
        ORDER BY table_name
    """)
    if tdf.empty:
        st.info("No hay tablas en 'main'.")
    else:
        sel = st.selectbox("Selecciona una tabla para previsualizar (50 filas)", tdf["table_name"].tolist())
        if sel:
            try:
                prev = con.execute(f"SELECT * FROM {sel} LIMIT 50").fetchdf()
                st.dataframe(prev, use_container_width=True, height=360, hide_index=True)
            except Exception as e:
                st.error(f"No se pudo leer {sel}: {e}")

def render_status(con: duckdb.DuckDBPyConnection):
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Últimos runs (etl_runs)")
        if table_or_view_exists(con, "etl_runs"):
            df = con.execute("""
                SELECT run_id, started_at, finished_at, group_name, status, rows_total, duration_s
                FROM etl_runs
                ORDER BY started_at DESC
                LIMIT 20
            """).fetchdf()
            st.dataframe(df, use_container_width=True, height=350, hide_index=True)
        else:
            st.info("No existe etl_runs. Ejecuta un grupo para generar historial.")

    with c2:
        st.subheader("Métricas recientes (etl_metrics)")
        if table_or_view_exists(con, "etl_metrics"):
            df = con.execute("""
                SELECT run_id, source_name, table_name, rows_loaded, dq_pass, dq_violations, duration_s, loaded_at
                FROM etl_metrics
                ORDER BY loaded_at DESC NULLS LAST, run_id DESC
                LIMIT 50
            """).fetchdf()
            st.dataframe(df, use_container_width=True, height=350, hide_index=True)
        else:
            st.info("No existe etl_metrics.")

    st.subheader("Últimas cargas por tabla (v_etl_last)")
    if table_or_view_exists(con, "v_etl_last"):
        df = con.execute("SELECT * FROM v_etl_last ORDER BY loaded_at DESC").fetchdf()
        st.dataframe(df, use_container_width=True, height=260, hide_index=True)
    else:
        st.info("La vista v_etl_last no existe todavía (se crea desde app.status).")

def render_explorer(con: duckdb.DuckDBPyConnection):
    with st.expander("Consulta SQL (avanzado)", expanded=False):
        default_sql = "SELECT CURRENT_TIMESTAMP AS now"
        sql = st.text_area("Escribe tu SQL y ejecuta", value=default_sql, height=140, key="sql_textarea")
        if st.button("▶ Ejecutar SQL", key="exec_sql_btn"):
            try:
                dfq = con.execute(sql).fetchdf()
                st.dataframe(dfq, use_container_width=True, height=360)
            except Exception as e:
                st.error(f"Error SQL: {e}")

    st.divider()
    st.subheader("Explorador de tablas/vistas")

    with st.expander("📈 Esquema (auto-grafo por *_id)", expanded=False):
        render_schema_graph(con)

    # Listado
    tbls = con.execute("""
        SELECT table_name, table_type
        FROM information_schema.tables
        WHERE table_schema='main'
        UNION ALL
        SELECT table_name, 'VIEW' AS table_type
        FROM information_schema.views
        WHERE table_schema='main'
        ORDER BY table_type, table_name
    """).fetchdf().drop_duplicates(subset=["table_name"])

    if tbls.empty:
        st.info("No hay tablas ni vistas en 'main'.")
        return

    sel = st.selectbox("Selecciona", tbls["table_name"].tolist())
    n = st.slider("Filas a mostrar", 10, 2000, 200, step=10)

    if sel:
        try:
            df = con.execute(f"SELECT * FROM {sel} LIMIT {int(n)}").fetchdf()
            st.dataframe(df, use_container_width=True, height=420)

            with st.expander("🔎 Perfil rápido (hasta 5.000 filas)", expanded=False):
                samp = con.execute(f"SELECT * FROM {sel} LIMIT 5000").fetchdf()
                prof = pd.DataFrame({
                    "col": samp.columns,
                    "dtype": [str(samp[c].dtype) for c in samp.columns],
                    "nulls": [int(samp[c].isna().sum()) for c in samp.columns],
                    "distinct": [int(samp[c].nunique(dropna=True)) for c in samp.columns],
                })
                st.dataframe(prof, use_container_width=True, hide_index=True, height=260)

            # Exportar
            csv_b = df_to_csv_bytes(df)
            xlsx_b = df_to_xlsx_bytes(df, sheet_name=sel)
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("⬇️ Exportar CSV", data=csv_b, file_name=f"{sel}.csv", mime="text/csv", use_container_width=True)
            with c2:
                st.download_button("⬇️ Exportar Excel", data=xlsx_b, file_name=f"{sel}.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   use_container_width=True)

        except Exception as e:
            st.error(f"No se pudo leer {sel}: {e}")


def render_safe_mode():
    """
    Modo seguro: ejecuta el runner SIEMPRE vía subprocess (sin modo librería),
    con UTF-8 forzado. Evita choques con ensure_ledger.
    """
    ROOT_L = Path(__file__).resolve().parents[1]

    def _run_group_safe(group: str):
        with st.status(f"Ejecutando '{group}'…", expanded=True) as s:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            res = subprocess.run(
                [sys.executable, "-m", "app.runner", "--group", group],
                cwd=str(ROOT_L),
                capture_output=True,
                text=True,
                env=env,
            )
            if res.stdout:
                st.code(res.stdout, language="bash")
            if res.returncode != 0:
                s.update(label="Fallo en runner", state="error")
                if res.stderr:
                    st.code(res.stderr, language="bash")
                return False
            s.update(label="Completado", state="complete")
            st.toast("Carga finalizada", icon="✅")
            return True

    st.divider()
    st.subheader("Modo seguro — ejecutar y refrescar")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("▶ Ejecutar daily (modo seguro)"):
            ok = _run_group_safe("daily")
            if ok:
                st.rerun()
    with c2:
        if st.button("↻ Refrescar métricas"):
            st.rerun()

    try:
        con = get_con()
        runs = con.execute("""
            SELECT run_id, started_at, finished_at, group_name, status, rows_total, duration_s
            FROM etl_runs ORDER BY started_at DESC LIMIT 10
        """).fetchdf()
        st.dataframe(runs, use_container_width=True, height=260, hide_index=True)
    except Exception as e:
        st.info(f"No se pudieron leer KPIs: {e}")

# --------------------------- Main ---------------------------

def main():
    con = get_con()

    t_home, t_status, t_explorer, t_data, t_assistant = st.tabs(
        ["Panel", "Estado", "Consultas", "Subir y limpiar", "Asistente"]
    )

    with t_home:
        render_home(con)

    with t_status:
        render_status(con)
        render_safe_mode()

    with t_explorer:
        render_explorer(con)

    with t_data:
        render_data(con)

    with t_assistant:
        if ASSISTANT_OK and callable(render_assistant):
            render_assistant(con)
        else:
            st.error("No se pudo cargar el asistente.")
            if ASSISTANT_ERR:
                st.caption(f"Detalle: {ASSISTANT_ERR}")
            st.info("Verifica `app/assistant.py` y dependencias.")


if __name__ == "__main__":
    main()
