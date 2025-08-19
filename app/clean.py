# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Limpieza de datos locales: tablas DuckDB y ficheros derivados.

Este módulo provee utilidades CLI para borrar tablas de DuckDB y limpiar
ficheros de reportes/plots por prefijo o en su totalidad.
"""

import argparse
import os
from pathlib import Path
from typing import List

import duckdb

WAREHOUSE = Path("data/warehouse.duckdb")
DATA_DIRS = [Path("data/reports"), Path("data/plots")]


def list_tables() -> List[str]:
    """
    Lista las tablas existentes en el esquema `main` de DuckDB.

    Recupera los nombres de tabla leyendo `information_schema.tables`.

    Parameters
    ----------
    None

    Returns
    -------
    List[str]
        Nombres de las tablas en el esquema `main`. Vacío si no hay DB.

    Preconditions
    --------------
    El archivo `data/warehouse.duckdb` debe existir y ser accesible.

    Example
    --------
    >>> list_tables()  # doctest: +SKIP
    ['ventas', 'clientes']
    """
    if not WAREHOUSE.exists():
        return []
    con = duckdb.connect(str(WAREHOUSE))
    try:
        query = (
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='main'"
        )
        rows = con.execute(query).fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()


def drop_by_prefix(prefix: str) -> List[str]:
    """
    Elimina tablas cuyo nombre comience por un prefijo dado.

    Recorre las tablas del esquema `main` y ejecuta `DROP TABLE` si
    coinciden con el prefijo.

    Parameters
    ----------
    prefix : str
        Prefijo de nombre de tabla a eliminar (p. ej., 'stg_', 'tmp_').

    Returns
    -------
    List[str]
        Lista de tablas eliminadas.

    Preconditions
    --------------
    Debe existir la base de datos DuckDB. El usuario debe tener permisos.

    Example
    --------
    >>> drop_by_prefix('tmp_')  # doctest: +SKIP
    ['tmp_ventas']
    """
    if not WAREHOUSE.exists():
        return []
    dropped: List[str] = []
    con = duckdb.connect(str(WAREHOUSE))
    try:
        for t in list_tables():
            if t.startswith(prefix):
                con.execute(f"DROP TABLE IF EXISTS {t}")
                dropped.append(t)
    finally:
        con.close()
    return dropped


def drop_all() -> List[str]:
    """
    Elimina todas las tablas del esquema `main`.

    Ejecuta `DROP TABLE IF EXISTS` sobre cada tabla listada por
    `list_tables()`.

    Parameters
    ----------
    None

    Returns
    -------
    List[str]
        Nombres de tablas eliminadas.

    Preconditions
    --------------
    Debe existir la base de datos y el usuario debe tener permisos.

    Example
    --------
    >>> drop_all()  # doctest: +SKIP
    ['ventas', 'clientes', 'etl_runs']
    """
    if not WAREHOUSE.exists():
        return []
    dropped: List[str] = []
    con = duckdb.connect(str(WAREHOUSE))
    try:
        for t in list_tables():
            con.execute(f"DROP TABLE IF EXISTS {t}")
            dropped.append(t)
    finally:
        con.close()
    return dropped


def clean_files(prefix: str | None = None) -> List[str]:
    """
    Borra ficheros en data/reports y data/plots filtrando por prefijo.

    Si no se indica prefijo, borra todos los ficheros de las carpetas
    configuradas. No elimina subcarpetas.

    Parameters
    ----------
    prefix : str | None
        Prefijo a filtrar en nombres de archivo. Si None, borra todos.

    Returns
    -------
    List[str]
        Rutas (str) de los ficheros eliminados.

    Preconditions
    --------------
    Las carpetas deben ser accesibles. Se crean si no existen.

    Example
    --------
    >>> clean_files('ventas')  # doctest: +SKIP
    ['data/reports/ventas_top.csv']
    """
    removed: List[str] = []
    for d in DATA_DIRS:
        d.mkdir(parents=True, exist_ok=True)
        for p in d.glob("*"):
            if p.is_file():
                matches = (
                    prefix is None
                    or p.name.startswith(prefix)
                    or f"_{prefix}_" in p.name
                )
                if matches:
                    try:
                        p.unlink()
                        removed.append(str(p))
                    except Exception:
                        # Silencio para no interrumpir limpieza
                        pass
        # No borramos subcarpetas para no ser agresivos
    return removed


def main():
    """
    Punto de entrada CLI para limpieza de tablas y ficheros.

    Acepta `--all` para borrar todo (tablas + ficheros) o `--prefix` para
    borrar por prefijo. Requiere confirmación a menos que se use `--yes`.

    Parameters
    ----------
    None

    Returns
    -------
    None
        Imprime el resultado por stdout.

    Preconditions
    --------------
    Si se usa `--all`, puede intentar eliminar el archivo de la base de
    datos tras dropear tablas.

    Example
    --------
    $ python -m app.clean --prefix ventas --yes
    """
    ap = argparse.ArgumentParser(
        description="Limpieza de datos (DuckDB + archivos)."
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="Borrar TODAS las tablas y ficheros (irreversible).",
    )
    ap.add_argument(
        "--prefix",
        type=str,
        default=None,
        help="Borrar por prefijo de tabla y ficheros asociados.",
    )
    ap.add_argument(
        "--yes",
        action="store_true",
        help="Confirmación no interactiva.",
    )
    args = ap.parse_args()

    if not args.all and not args.prefix:
        ap.error("Usa --all o --prefix <prefijo>.")

    if not args.yes:
        target = "TODO" if args.all else f"prefijo '{args.prefix}'"
        resp = input(
            f"Vas a borrar {target}. ¿Seguro? (yes/no): "
        ).strip().lower()
        if resp != "yes":
            print("Cancelado.")
            return

    if args.all:
        dropped = drop_all()
        removed = clean_files(None)
        if WAREHOUSE.exists():
            try:
                os.remove(WAREHOUSE)
            except Exception:
                # Ignorar fallos al borrar el archivo de la DB
                pass
        print(f"[CLEAN] Tablas borradas: {dropped}")
        print(f"[CLEAN] Ficheros borrados: {removed}")
        print("[CLEAN] Hecho (todo).")
        return

    # prefix
    dropped = drop_by_prefix(args.prefix)  # type: ignore[arg-type]
    removed = clean_files(args.prefix)
    print(f"[CLEAN] Tablas borradas (prefijo {args.prefix}): {dropped}")
    print(f"[CLEAN] Ficheros borrados (prefijo {args.prefix}): {removed}")
    print("[CLEAN] Hecho (por prefijo).")


if __name__ == "__main__":
    main()
