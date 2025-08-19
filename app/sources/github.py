# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Fuentes GitHub: snapshot de repos y actividad de commits (52 semanas).

Extrae metadatos de un repositorio, opcionalmente su actividad semanal,
los carga en DuckDB y genera copias CSV en `data/reports/`.

Parameters
----------
None

Returns
-------
None
    Módulo con punto de entrada CLI.

Preconditions
--------------
- Opcional: variable de entorno `GITHUB_TOKEN` para mayor cuota.
- Carpeta `data/` accesible. DuckDB en `data/warehouse.duckdb`.

Example
--------
$ python -m app.sources.github openai openai-python
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd


DB_PATH = "data/warehouse.duckdb"
REPORTS_DIR = Path("data/reports")


def _utc_now() -> datetime:
    """
    Devuelve la hora actual en UTC.

    Parameters
    ----------
    None

    Returns
    -------
    datetime.datetime
        Instante actual en UTC.
    """
    return datetime.now(timezone.utc)


def _fmt_ts(dt: datetime) -> str:
    """
    Formatea un datetime como 'YYYYmmdd_HHMMSS'.

    Parameters
    ----------
    dt : datetime.datetime
        Fecha/hora a formatear.

    Returns
    -------
    str
        Marca temporal legible.
    """
    return dt.strftime("%Y%m%d_%H%M%S")


def _headers() -> dict[str, str]:
    """
    Construye cabeceras HTTP para GitHub API (incluye token si existe).

    Parameters
    ----------
    None

    Returns
    -------
    Dict[str, str]
        Cabeceras con `Accept`, `User-Agent` y `Authorization` opcional.

    Preconditions
    --------------
    Puede usar `GITHUB_TOKEN` del entorno si está definido.
    """
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "etl-mini/0.1",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _slug(owner: str, repo: str) -> str:
    """
    Normaliza `<owner>/<repo>` a un identificador apto para tabla.

    Parameters
    ----------
    owner : str
        Propietario del repositorio.
    repo : str
        Nombre del repositorio.

    Returns
    -------
    str
        Identificador en minúsculas con `_` como separador.

    Example
    --------
    >>> _slug("OpenAI", "OpenAI-Python")
    'openai_openai_python'
    """
    s = f"{owner}_{repo}".lower()
    return re.sub(r"[^a-z0-9_]+", "_", s)


def fetch_repo(owner: str, repo: str) -> pd.DataFrame:
    """
    Obtiene un snapshot de metadatos del repositorio.

    Parameters
    ----------
    owner : str
        Propietario del repo en GitHub.
    repo : str
        Nombre del repositorio.

    Returns
    -------
    pandas.DataFrame
        Una fila con campos relevantes del repositorio.

    Preconditions
    --------------
    Requiere acceso a `https://api.github.com/repos/{owner}/{repo}`.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}"
    print(f"[GH] GET {url}")
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))

    row = {
        "full_name": data.get("full_name"),
        "description": data.get("description"),
        "visibility": data.get("visibility"),
        "fork": data.get("fork"),
        "archived": data.get("archived"),
        "disabled": data.get("disabled"),
        "language": data.get("language"),
        "license": (
            (data.get("license") or {}).get("spdx_id")
            if data.get("license")
            else None
        ),
        "topics": ",".join(data.get("topics", [])),
        "default_branch": data.get("default_branch"),
        "stars": data.get("stargazers_count"),
        "forks": data.get("forks_count"),
        "open_issues": data.get("open_issues_count"),
        "watchers": data.get("subscribers_count"),
        "size_kb": data.get("size"),
        "created_at": data.get("created_at"),
        "pushed_at": data.get("pushed_at"),
        "updated_at": data.get("updated_at"),
        "owner": (data.get("owner") or {}).get("login"),
        "repo": data.get("name"),
        "snapshot_utc": _utc_now().isoformat(),
    }
    return pd.DataFrame([row])


def fetch_commit_activity(
    owner: str,
    repo: str,
) -> pd.DataFrame | None:
    """
    Descarga actividad de commits (hasta 52 semanas) desde /stats.

    Puede devolver 202 (processing). Se reintenta hasta 3 veces y, si
    persiste, se retorna None.

    Parameters
    ----------
    owner : str
        Propietario del repositorio.
    repo : str
        Nombre del repositorio.

    Returns
    -------
    pandas.DataFrame | None
        Filas con `week_start_utc` y `total_commits`, o None.

    Preconditions
    --------------
    Endpoint: `.../stats/commit_activity`.
    """
    url = (
        f"https://api.github.com/repos/{owner}/{repo}/stats/commit_activity"
    )
    for attempt in range(3):
        try:
            print(f"[GH] GET {url} (attempt {attempt + 1}/3)")
            req = urllib.request.Request(url, headers=_headers())
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
            if not isinstance(data, list):
                return None
            rows = []
            for w in data:
                epoch = w.get("week")
                week_start = (
                    datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
                    if epoch
                    else None
                )
                rows.append(
                    {
                        "week_start_utc": week_start,
                        "total_commits": w.get("total"),
                    }
                )
            df = pd.DataFrame(rows)
            if not df.empty:
                df = df.sort_values("week_start_utc").reset_index(drop=True)
            return df
        except urllib.error.HTTPError as e:
            if e.code == 202:
                time.sleep(2)
                continue
            raise
    print("[GH] Commit activity no disponible (202 persistente u otro error).")
    return None


def load_to_duckdb(df: pd.DataFrame, table: str) -> int:
    """
    Crea o reemplaza `table` en DuckDB con el contenido de `df`.

    Parameters
    ----------
    df : pandas.DataFrame
        Datos a cargar.
    table : str
        Nombre de la tabla destino.

    Returns
    -------
    int
        Número de filas en la tabla tras la carga.

    Preconditions
    --------------
    `DB_PATH` debe ser accesible para escritura.
    """
    con = duckdb.connect(DB_PATH)
    try:
        con.register("df_tmp", df)
        con.execute(
            f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM df_tmp"
        )
        n = con.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]
        return int(n)
    finally:
        try:
            con.close()
        except Exception:
            pass


def to_csv(df: pd.DataFrame, stem: str) -> Path:
    """
    Escribe `df` como CSV en `data/reports/{stem}_<ts>.csv`.

    Parameters
    ----------
    df : pandas.DataFrame
        Datos a exportar.
    stem : str
        Prefijo base del archivo.

    Returns
    -------
    pathlib.Path
        Ruta al CSV generado.

    Preconditions
    --------------
    `REPORTS_DIR` debe existir o poder crearse.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / f"{stem}_{_fmt_ts(_utc_now())}.csv"
    df.to_csv(out, index=False)
    return out


def main() -> None:
    """
    Punto de entrada CLI para snapshot y actividad de un repositorio.

    Usage
    -----
    python -m app.sources.github <owner> <repo>
    ej.: python -m app.sources.github openai openai-python

    Parameters
    ----------
    None

    Returns
    -------
    None
        Imprime progreso y rutas de salida por stdout.

    Preconditions
    --------------
    Conexión a internet y, opcionalmente, `GITHUB_TOKEN`.
    """
    if len(sys.argv) < 3:
        print("Uso: python -m app.sources.github <owner> <repo>")
        sys.exit(2)

    owner, repo = sys.argv[1], sys.argv[2]
    slug = _slug(owner, repo)

    # Snapshot
    df_repo = fetch_repo(owner, repo)
    tbl_repo = f"gh_{slug}"
    n1 = load_to_duckdb(df_repo, tbl_repo) if not df_repo.empty else 0
    print(f"[GH] Cargado → tabla: {tbl_repo} (filas: {n1})")
    if n1 > 0:
        csv1 = to_csv(df_repo, f"github_{tbl_repo}")
        print(f"[GH] Copia CSV → {csv1}")

    # Commit activity (opcional)
    try:
        df_commits = fetch_commit_activity(owner, repo)
    except Exception as e:
        print(f"[GH] Commit activity error: {e}")
        df_commits = None

    if isinstance(df_commits, pd.DataFrame) and not df_commits.empty:
        tbl_comm = f"{tbl_repo}_commits"
        n2 = load_to_duckdb(df_commits, tbl_comm)
        print(f"[GH] Cargado → tabla: {tbl_comm} (filas: {n2})")
        csv2 = to_csv(df_commits, f"github_{tbl_comm}")
        print(f"[GH] Copia CSV → {csv2}")
    else:
        print("[GH] Commit activity no disponible; solo snapshot de repo.")


if __name__ == "__main__":
    main()
