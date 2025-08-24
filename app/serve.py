# -*- coding: utf-8 -*-
"""
Nítida — UI mínima para etl-mini

- Ejecutar cargas (runner)
- Estado (etl_runs / etl_metrics)
- Explorar tablas DuckDB
- Descargar informe HTML
- Subir e importar CSV/XLSX a DuckDB
- Modo seguro de ejecución

Run:
    streamlit run app/serve.py
"""
from __future__ import annotations

import os
import sys
import re
import io
import subprocess
from pathlib import Path
from datetime import datetime, timezone

import duckdb
import pandas as pd
import streamlit as st

# -------- settings / fallback --------
try:
    from app.utils import load_settings  # si existe
except Exception:
    load_settings = None

DEFAULT_SETTINGS = {
    "paths": {
        "db_path": "data/warehouse.duckdb",
        "reports_dir": "data/reports",
        "parquet_dir": "data/parquet",
    },
    "project": {"name": "etl-mini (Nítida)", "version": "0.4.0"},
}


def get_settings() -> dict:
    """
    Devolver la configuración de la aplicación.

    Si existe `load_settings` en app.utils, se utiliza. En caso de error o
    ausencia, se retornan los DEFAULT_SETTINGS.

    Returns
    -------
    dict
        Diccionario de configuración.
    """
    if load_settings:
        try:
            return load_settings()
        except Exception:
            pass
    return DEFAULT_SETTINGS


SET = get_settings()
ROOT = Path(__file__).resolve().parents[1]
DB_PATH = (SET.get("paths") or {}).get("db_path", "data/warehouse.duckdb")
REPORTS_DIR = Path((SET.get("paths") or {}).get("reports_dir", "data/reports"))
INPUT_DIR = ROOT / "data" / "input"
INPUT_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="Nítida · ETL-mini", layout="wide")
st.title("Nítida — ETL mini")
st.caption("KPIs rápidos, acciones clave y utilidades sobre DuckDB.")


# -------- conexión única --------
@st.cache_resource(show_spinner=False)
def get_con():
    """
    Obtener una conexión DuckDB única (cacheada para la sesión Streamlit).

    Returns
    -------
    duckdb.DuckDBPyConnection
        Conexión a la base de datos DuckDB.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return duckdb.connect(DB_PATH)


def table_or_view_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    """
    Comprobar si existe una tabla o vista en el esquema 'main'.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Conexión a DuckDB.
    name : str
        Nombre de la tabla o vista a verificar.

    Returns
    -------
    bool
        True si existe, False en caso contrario.
    """
    q = """
    SELECT 1 FROM information_schema.tables WHERE table_schema='main' AND table_name=?
    UNION ALL
    SELECT 1 FROM information_schema.views  WHERE table_schema='main' AND table_name=?
    LIMIT 1
    """
    return bool(con.execute(q, [name, name]).fetchone())


def df_safe(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    """
    Ejecutar una consulta SQL de forma segura.

    Si la consulta falla, devuelve un DataFrame vacío en lugar de lanzar
    una excepción.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Conexión a DuckDB.
    sql : str
        Consulta SQL a ejecutar.

    Returns
    -------
    pandas.DataFrame
        Resultado de la consulta o DataFrame vacío si falla.
    """
    try:
        return con.execute(sql).fetchdf()
    except Exception:
        return pd.DataFrame()


# -------- helpers UI/KPI --------
def last_run_info(con: duckdb.DuckDBPyConnection) -> dict:
    """
    Recuperar información del último run registrado en `etl_runs`.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Conexión a DuckDB.

    Returns
    -------
    dict
        Diccionario con claves: run_id, status, rows_total, finished_local.
        Devuelve {} si no hay información disponible.
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
        "run_id": row.get("run_id"),
        "status": row.get("status"),
        "rows_total": int(row.get("rows_total") or 0),
        "finished_local": local_str,
    }


def sanitize_table_name(name: str) -> str:
    """
    Generar un nombre de tabla 'staging' seguro a partir de un nombre de fichero.

    Parameters
    ----------
    name : str
        Nombre del fichero (posiblemente con #hoja para Excel).

    Returns
    -------
    str
        Nombre de tabla seguro, prefijado con 'stg_'.
    """
    base = name
    if "#" in base:
        base = base.split("#", 1)[0]
    base = Path(base).stem.lower()
    base = re.sub(r"[^a-z0-9_]+", "_", base)
    base = re.sub(r"_+", "_", base).strip("_")
    if not base:
        base = "stg_table"
    return f"stg_{base}"


def import_file_to_duckdb(con: duckdb.DuckDBPyConnection, path: Path) -> tuple[str, int]:
    """
    Importar un archivo CSV/TXT/XLSX/XLS como tabla staging en DuckDB.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Conexión a DuckDB.
    path : pathlib.Path
        Ruta del archivo a importar.

    Returns
    -------
    tuple[str, int]
        (nombre_tabla, filas_importadas)
    """
    fname = path.name
    table = sanitize_table_name(fname)
    p = str(path)
    sheet_name = None
    # Soporte nombre tipo "archivo.xlsx#Hoja2"
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
        try:
            df = pd.read_excel(p, sheet_name=(sheet_name or 0))
        except Exception as e:
            raise RuntimeError(f"No se pudo leer Excel: {e}")
        con.register("df_tmp_import", df)
        con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM df_tmp_import")
        con.unregister("df_tmp_import")
    else:
        raise RuntimeError("Formato no soportado (usa CSV/TXT/XLSX/XLS).")

    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return table, int(n)


# -------- Report: solo descarga (robusto) --------
def prepare_report_download(con: duckdb.DuckDBPyConnection) -> tuple[str, bytes]:
    """
    Preparar un informe HTML para descarga.

    Intenta usar `assemble_report()` si existe en `app.report`. En caso de
    no encontrarlo, genera un informe "dummy". El contenido binario y el
    nombre se almacenan en `st.session_state` para evitar recomputaciones.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Conexión a DuckDB (para conocer el último run).

    Returns
    -------
    tuple[str, bytes]
        (nombre_archivo, contenido_html_bytes)
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

    # Genera SOLO si ha cambiado el último run_id (o nunca se generó)
    info = last_run_info(con)
    last_id = info.get("run_id", "none")
    key_id = st.session_state.get("report_last_id")
    if key_id != last_id or "report_bytes" not in st.session_state:
        out_path = assemble_report()
        with open(out_path, "rb") as f:
            st.session_state["report_bytes"] = f.read()
        st.session_state["report_name"] = Path(out_path).name
        st.session_state["report_last_id"] = last_id

    name = st.session_state.get("report_name", f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
    data = st.session_state["report_bytes"]
    return name, data


# -------- vista: KPIs + CTAs + Uploader --------
def render_home(con: duckdb.DuckDBPyConnection):
    st.subheader("Cómo va mi tienda hoy")

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

    with col_run:
        if st.button("▶ Ejecutar hoy", use_container_width=True, type="primary"):
            with st.status("Ejecutando grupo 'daily'…", expanded=True) as status:
                try:
                    from app.runner import run_group, load_yaml, ensure_ledger
                    ensure_ledger(DB_PATH)
                    cfg = load_yaml("config/sources.yml")
                    dq = load_yaml("config/dq.yml")
                    run_group("daily", cfg, dq)
                    status.update(label="Runner OK", state="complete")
                    st.success("Carga completada ✅")
                except Exception:
                    res = subprocess.run(
                        [sys.executable, "-m", "app.runner", "--group", "daily"],
                        cwd=str(ROOT),
                        capture_output=True,
                        text=True,
                    )
                    if res.stdout:
                        st.code(res.stdout, language="bash")
                    if res.returncode != 0:
                        status.update(label="Runner terminó con error", state="error")
                        if res.stderr:
                            st.code(res.stderr, language="bash")
                        st.error("Fallo al ejecutar el runner.")
                    else:
                        status.update(label="Runner OK", state="complete")
                        st.success("Carga completada ✅")
            st.rerun()

    with col_report:
        name, data = prepare_report_download(con)
        st.download_button(
            "📄 Descargar informe",
            data=data,
            file_name=name,
            mime="text/html",
            use_container_width=True,
        )

def render_data(con: duckdb.DuckDBPyConnection):
    st.subheader("Sube tus CSV/XLSX de ventas y mermas")

    uploaded = st.file_uploader(
        "Arrastra aquí archivos CSV/TXT/XLSX/XLS",
        type=["csv", "txt", "xlsx", "xls"],
        accept_multiple_files=True,
    )
    if uploaded:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        for uf in uploaded:
            dest = INPUT_DIR / f"{ts}_{uf.name}"
            with open(dest, "wb") as f:
                f.write(uf.getbuffer())
        st.toast("Archivo(s) guardado(s) en data/input/", icon="✅")

    files = sorted(INPUT_DIR.glob("*.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if files:
        st.markdown("#### Archivos guardados")
        for p in files[:20]:
            cols = st.columns([4, 2, 2])
            with cols[0]:
                st.write(p.name)
            with cols[1]:
                tbl_name = sanitize_table_name(p.name)
                if st.button(f"Importar a DuckDB → {tbl_name}", key=f"imp_{p.name}"):
                    try:
                        table, n = import_file_to_duckdb(con, p)
                        st.toast(f"Importadas {n} filas en {table}", icon="✅")
                        st.success(f"{table}: {n} filas")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            with cols[2]:
                st.caption(f"{int(p.stat().st_size/1024)} KB")

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


# -------- vistas secundarias --------
def render_status(con: duckdb.DuckDBPyConnection):
    """
    Renderizar la pestaña de estado con runs y métricas recientes.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Conexión a DuckDB.
    """
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
    """
    Renderizar el explorador de tablas/vistas con previsualización.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Conexión a DuckDB.
    """
    st.subheader("Explorador de tablas/vistas")
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
        except Exception as e:
            st.error(f"No se pudo leer {sel}: {e}")


# -------- Modo seguro (conservado) --------
def render_safe_mode():
    """
    Renderizar la sección de modo seguro para ejecutar 'daily' mediante subprocess.
    """
    try:
        settings = load_settings()  # si no existe, caerá al except
    except Exception:
        settings = {"paths": {"db_path": DB_PATH}}

    ROOT_L = Path(__file__).resolve().parents[1]
    DBP = settings["paths"]["db_path"]

    @st.cache_resource(show_spinner=False)
    def _con():
        """
        Devolver una conexión DuckDB para la sección de modo seguro.

        Returns
        -------
        duckdb.DuckDBPyConnection
        """
        return duckdb.connect(DBP)

    def _run_group_safe(group: str):
        """
        Ejecutar el runner en modo seguro como subproceso.

        Parameters
        ----------
        group : str
            Nombre del grupo a ejecutar.

        Returns
        -------
        bool
            True si finaliza con código 0, False en caso contrario.
        """
        with st.status(f"Ejecutando '{group}'…", expanded=True) as s:
            res = subprocess.run(
                [sys.executable, "-m", "app.runner", "--group", group],
                cwd=str(ROOT_L),
                capture_output=True,
                text=True,
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
        con = _con()
        runs = con.execute("""
            SELECT run_id, started_at, finished_at, group_name, status, rows_total, duration_s
            FROM etl_runs ORDER BY started_at DESC LIMIT 10
        """).fetchdf()
        st.dataframe(runs, use_container_width=True, height=260, hide_index=True)
    except Exception as e:
        st.info(f"No se pudieron leer KPIs: {e}")


# -------- main --------
def main():
    con = get_con()
    tabs = st.tabs(["Inicio", "Estado", "Explorar", "Datos"])

    with tabs[0]:
        render_home(con)

    with tabs[1]:
        render_status(con)
        render_safe_mode()

    with tabs[2]:
        render_explorer(con)

    with tabs[3]:
        render_data(con)


if __name__ == "__main__":
    main()
