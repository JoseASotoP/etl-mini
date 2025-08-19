# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Utilidades comunes: creación de carpetas, carga de settings (TOML),
logger con archivo por ejecución y conexión a DuckDB.

Parameters
----------
None

Returns
-------
None
    Módulo con funciones auxiliares.

Preconditions
--------------
Rutas de `config/settings.toml` y `data/` deben ser accesibles.

Example
--------
>>> cfg = load_settings()            # doctest: +SKIP
>>> log = get_logger()               # doctest: +SKIP
>>> con = connect_duckdb('data/warehouse.duckdb')  # doctest: +SKIP
"""

import os
import logging
import datetime as dt
from pathlib import Path
from typing import Any, Dict

try:
    import tomllib  # py311+
except ImportError:
    import tomli as tomllib  # fallback

import duckdb


def ensure_dirs(*paths: str | Path) -> None:
    """
    Crea directorios si no existen (anidados).

    Parameters
    ----------
    *paths : str | pathlib.Path
        Rutas de carpetas a asegurar.

    Returns
    -------
    None

    Preconditions
    --------------
    Permisos de escritura en el sistema de archivos.

    Example
    --------
    >>> ensure_dirs('data/reports', 'data/plots')  # doctest: +SKIP
    """
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)


def load_settings(path: str = "config/settings.toml") -> Dict[str, Any]:
    """
    Carga la configuración desde un archivo TOML.

    Parameters
    ----------
    path : str, default='config/settings.toml'
        Ruta del fichero de configuración.

    Returns
    -------
    Dict[str, Any]
        Diccionario con claves/valores del TOML.

    Preconditions
    --------------
    El archivo debe existir y ser TOML válido.

    Example
    --------
    >>> cfg = load_settings()  # doctest: +SKIP
    """
    with open(path, "rb") as f:
        return tomllib.load(f)


def get_logger(
    name: str = "etl-mini",
    logs_dir: str = "data/reports",
) -> logging.Logger:
    """
    Devuelve un logger con salida a archivo y a consola.

    Crea `logs_dir` si no existe. El archivo se nombra `run_YYYYmmdd_HHMMSS`.
    Reinicia handlers para evitar duplicados.

    Parameters
    ----------
    name : str, default='etl-mini'
        Nombre del logger.
    logs_dir : str, default='data/reports'
        Carpeta donde guardar el log.

    Returns
    -------
    logging.Logger
        Instancia configurada lista para usar.

    Preconditions
    --------------
    Deben poder crearse/escribirse archivos en `logs_dir`.

    Example
    --------
    >>> logger = get_logger()  # doctest: +SKIP
    """
    ensure_dirs(logs_dir)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(logs_dir) / f"run_{ts}.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fh = logging.FileHandler(log_path, encoding="utf-8")
    ch = logging.StreamHandler()

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)

    logger.info("Log file: %s", log_path)
    return logger


def connect_duckdb(db_path: str) -> duckdb.DuckDBPyConnection:
    """
    Abre una conexión a DuckDB asegurando la carpeta del archivo.

    Parameters
    ----------
    db_path : str
        Ruta del archivo `.duckdb`.

    Returns
    -------
    duckdb.DuckDBPyConnection
        Conexión abierta a la base de datos.

    Preconditions
    --------------
    La carpeta padre de `db_path` debe existir o poder crearse.

    Example
    --------
    >>> con = connect_duckdb('data/warehouse.duckdb')  # doctest: +SKIP
    """
    ensure_dirs(Path(db_path).parent)
    return duckdb.connect(db_path)
