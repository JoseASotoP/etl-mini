# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Adaptadores locales de CSV para ETL-mini.

Incluye dos estilos:

1) `CSVLocalAdapter` (registrado como "csv_local"):
   - Implementa sólo `fetch()`: lee un único CSV desde disco y devuelve
     un DataFrame sin cambios. El resto del pipeline (normalize/postprocess/load)
     lo gestiona la clase base.

2) `AdapterCSVLocal` (registrado como "csv_local_simple" y exportado como `Adapter`):
   - Variante declarativa "todo en uno": permite patrón de ficheros (glob),
     concatena varios CSV, aplica `apply_simple_transforms` y carga a DuckDB
     con `load_to_duckdb`. Devuelve (tabla, filas, 0.0).

Ambos comparten parámetros inspirados en `pandas.read_csv` para mayor control.
"""

from typing import Any, Dict, List, Tuple
import glob

import pandas as pd

from .base import (
    BaseAdapter,
    register_adapter,
    apply_simple_transforms,
    load_to_duckdb,
)


@register_adapter("csv_local")
class CSVLocalAdapter(BaseAdapter):
    """
    Adaptador que carga un CSV local a un DataFrame.

    Parameters
    ----------
    params : Dict[str, Any]
        Debe incluir `path` con la ruta al archivo CSV.
    context : Dict[str, Any]
        Contexto del pipeline (no se utiliza en `fetch`).

    Returns
    -------
    None

    Preconditions
    --------------
    El archivo CSV debe existir y ser legible con pandas.

    Example
    --------
    >>> adp = CSVLocalAdapter({'path': 'data.csv'}, {})
    >>> df = adp.fetch()  # doctest: +SKIP
    """
    def __init__(self, params: Dict[str, Any], context: Dict[str, Any]):
        super().__init__(params, context)

    def fetch(self) -> pd.DataFrame:
        """
        Lee el CSV indicado en `params['path']` y devuelve un DataFrame.

        Parameters
        ----------
        None

        Returns
        -------
        pandas.DataFrame
            DataFrame con el contenido del CSV.

        Preconditions
        --------------
        `params['path']` debe estar definido y apuntar a un archivo válido.

        Example
        --------
        >>> CSVLocalAdapter({'path': 'data.csv'}, {}).fetch()  # doctest: +SKIP
        """
        path = self.params.get("path")
        if not path:
            raise ValueError("csv_local.params.path es obligatorio")
        return pd.read_csv(path)


@register_adapter("csv_local_simple")
class AdapterCSVLocal:
    """
    Variante declarativa de adaptador CSV local con carga integrada.

    Flujo
    -----
    1) Expande `path` con `glob` (permite comodines) y concatena archivos.
    2) Lee con `pandas.read_csv` admitiendo opciones comunes (sep, encoding, …).
    3) Aplica transformaciones declarativas con `apply_simple_transforms`.
    4) Carga a DuckDB usando `load_to_duckdb`.

    Parámetros en `params`
    ----------------------
    path : str
        Ruta o patrón glob (p. ej., "data/*.csv").
    sep : str, optional
        Separador de columnas (por defecto ",").
    encoding : str, optional
        Codificación (por defecto "utf-8").
    usecols : list[str] | None, optional
        Subconjunto de columnas a leer.
    dtype : dict[str, str] | None, optional
        Tipos a forzar en la lectura.
    parse_dates : list[str] | None, optional
        Columnas que `read_csv` debe parsear como fechas.
    na_values : Any | list[Any] | dict, optional
        Valores que deben considerarse NA.
    skiprows : int | list[int], optional
        Filas a saltar al inicio.
    # Además, admite todas las claves soportadas por `apply_simple_transforms`
    # (select, rename, derive, select_final, dtypes, parse_dates, filter, dedupe_on).

    Contexto (`context`)
    --------------------
    db_path : str
        Ruta al fichero DuckDB.
    table : str
        Tabla destino.
    mode : str, optional
        "replace" (por defecto) o "append".

    Returns
    -------
    Tuple[str, int, float]
        (tabla, filas_insertadas, duración_en_segundos=0.0)

    Example
    -------
    >>> params = {"path": "data/2025-*.csv", "sep": ";", "select": ["id", "ts", "val"]}
    >>> ctx = {"db_path": "data/warehouse.duckdb", "table": "events", "mode": "append"}
    >>> AdapterCSVLocal(params, ctx).run()  # doctest: +SKIP
    """
    def __init__(self, params: Dict[str, Any], context: Dict[str, Any]):
        self.p = params or {}
        self.ctx = context or {}

    def run(self) -> Tuple[str, int, float]:
        """
        Ejecuta lectura (concat) → transforms declarativas → carga a DuckDB.

        Returns
        -------
        Tuple[str, int, float]
            (tabla, filas_insertadas, 0.0)

        Raises
        ------
        FileNotFoundError
            Si el patrón `path` no encuentra ficheros.
        KeyError
            Si faltan claves obligatorias en `context` (`db_path`, `table`).
        """
        path = self.p["path"]
        files: List[str] = sorted(glob.glob(path))
        if not files:
            raise FileNotFoundError(f"No hay ficheros para el patrón: {path}")

        dfs: List[pd.DataFrame] = []
        for f in files:
            df = pd.read_csv(
                f,
                sep=self.p.get("sep", ","),
                encoding=self.p.get("encoding", "utf-8"),
                usecols=self.p.get("usecols"),
                dtype=self.p.get("dtype"),
                parse_dates=self.p.get("parse_dates") or [],
                na_values=self.p.get("na_values"),
                skiprows=self.p.get("skiprows", 0),
            )
            dfs.append(df)
        df_all = pd.concat(dfs, ignore_index=True)

        # transforms declarativas
        df_all = apply_simple_transforms(df_all, self.p)

        # cargar
        table = self.ctx["table"]
        mode = self.ctx.get("mode", "replace")
        rows = load_to_duckdb(df_all, self.ctx["db_path"], table, mode)
        return table, rows, 0.0


# Export adicional para compatibilidad con cargas dinámicas externas
Adapter = AdapterCSVLocal
