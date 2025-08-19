# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Base de adaptadores para ETL-mini: registro, contrato y carga a DuckDB.

Define un registro global de adaptadores, un decorador de registro y la
clase base con pasos `fetch → normalize → postprocess → load → run`.

Parameters
----------
None

Returns
-------
None
    Módulo con utilidades para adaptadores.

Preconditions
--------------
Los adaptadores concretos deben heredar de `BaseAdapter` e implementar
`fetch()` como mínimo.

Example
--------
>>> @register_adapter("dummy")            # doctest: +SKIP
... class Dummy(BaseAdapter):             # doctest: +SKIP
...     def fetch(self): ...              # doctest: +SKIP
"""

from typing import Any, Dict, Optional, Tuple, List
import time

# Registro global de adaptadores
ADAPTERS: Dict[str, type["BaseAdapter"]] = {}


def register_adapter(name: str):
    """
    Decorador que registra una clase adaptador bajo un nombre.

    Parameters
    ----------
    name : str
        Clave con la que se registrará el adaptador.

    Returns
    -------
    Callable
        Función decoradora que inserta la clase en `ADAPTERS`.

    Preconditions
    --------------
    El decorado debe ser subclase de `BaseAdapter`.

    Example
    --------
    >>> @register_adapter("csv")          # doctest: +SKIP
    ... class CSVAdapter(BaseAdapter):    # doctest: +SKIP
    ...     def fetch(self): ...          # doctest: +SKIP
    """
    def _wrap(cls):
        ADAPTERS[name] = cls
        return cls
    return _wrap


class BaseAdapter:
    """
    Contrato mínimo de un adaptador de fuente.

    Proporciona el pipeline por defecto:
    `fetch()` → `normalize()` → `postprocess()` → `load()`.

    Parameters
    ----------
    params : Dict[str, Any]
        Parámetros específicos de la fuente.
    context : Dict[str, Any]
        Contexto de ejecución (p. ej., db_path, table, mode).

    Returns
    -------
    None

    Preconditions
    --------------
    Las claves esperadas en `context` son: `db_path`, `table` y `mode`.

    Example
    --------
    >>> a = BaseAdapter({}, {"db_path": "data/warehouse.duckdb",
    ...                      "table": "t", "mode": "replace"})  # doctest: +SKIP
    """
    def __init__(self, params: Dict[str, Any], context: Dict[str, Any]):
        self.params = params or {}
        self.context = context or {}

    def fetch(self):
        """
        Obtiene los datos fuente y los devuelve como DataFrame.

        Parameters
        ----------
        None

        Returns
        -------
        Any
            DataFrame (pandas) con datos crudos.

        Raises
        ------
        NotImplementedError
            Debe implementarse en subclases.

        Example
        --------
        >>> # Subclases deben devolver un DataFrame  # doctest: +SKIP
        """
        raise NotImplementedError

    def normalize(self, df):
        """
        Normaliza/transforma el DataFrame crudo.

        Parameters
        ----------
        df : Any
            DataFrame de entrada.

        Returns
        -------
        Any
            DataFrame normalizado (por defecto, el mismo).

        Preconditions
        --------------
        Debe ser un DataFrame de pandas.

        Example
        --------
        >>> # Por defecto, devuelve df sin cambios  # doctest: +SKIP
        """
        return df

    def postprocess(self, df):
        """
        Postprocesa `df` según `params['post']` (casts, dropna).

        Reglas soportadas:
        - cast: int | float | datetime | str
        - dropna_any: lista de columnas

        Parameters
        ----------
        df : Any
            DataFrame a postprocesar.

        Returns
        -------
        Any
            DataFrame resultante.

        Preconditions
        --------------
        Requiere pandas disponible.

        Example
        --------
        >>> # Aplica casts y dropna si se define en params  # doctest: +SKIP
        """
        import pandas as pd
        post = self.params.get("post", {})
        if not post:
            return df
        df = df.copy()
        for col, typ in (post.get("cast") or {}).items():
            if typ == "int":
                df[col] = pd.to_numeric(
                    df[col], errors="coerce"
                ).astype("Int64")
            elif typ == "float":
                df[col] = pd.to_numeric(df[col], errors="coerce")
            elif typ == "datetime":
                df[col] = pd.to_datetime(
                    df[col], errors="coerce", utc=True
                )
            elif typ == "str":
                df[col] = df[col].astype("string")
        dna = post.get("dropna_any") or []
        if dna:
            df = df.dropna(subset=dna)
        return df

    def _load_duckdb(self, df, table: str, mode: str) -> Tuple[str, int]:
        """
        Carga `df` en DuckDB según el modo (replace/append).

        Parameters
        ----------
        df : Any
            DataFrame a cargar.
        table : str
            Tabla destino.
        mode : str
            'replace' o 'append'.

        Returns
        -------
        Tuple[str, int]
            (tabla, filas totales en tabla tras la carga).

        Preconditions
        --------------
        `context['db_path']` debe existir o poder crearse.

        Example
        --------
        >>> # _load_duckdb(df, 't', 'replace')  # doctest: +SKIP
        """
        import duckdb
        con = duckdb.connect(self.context["db_path"])
        con.register("df_tmp", df)
        if mode == "append":
            con.execute(
                f"CREATE TABLE IF NOT EXISTS {table} "
                "AS SELECT * FROM df_tmp WHERE 1=0"
            )
            con.execute(f"INSERT INTO {table} SELECT * FROM df_tmp")
        else:
            con.execute(
                f"CREATE OR REPLACE TABLE {table} "
                "AS SELECT * FROM df_tmp"
            )
        rows = con.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]
        con.close()
        return table, int(rows)

    def load(self, df) -> Tuple[str, int]:
        """
        Carga `df` en la tabla definida en `context`.

        Parameters
        ----------
        df : Any
            DataFrame a cargar.

        Returns
        -------
        Tuple[str, int]
            (tabla, filas totales en tabla tras la carga).

        Preconditions
        --------------
        `context` debe contener `table` y `mode`.

        Example
        --------
        >>> # table, cnt = adapter.load(df)  # doctest: +SKIP
        """
        table = self.context["table"]
        mode = self.context.get("mode", "replace")
        return self._load_duckdb(df, table, mode)

    def run(self) -> Tuple[str, int, float]:
        """
        Ejecuta el pipeline completo y devuelve métricas básicas.

        Parameters
        ----------
        None

        Returns
        -------
        Tuple[str, int, float]
            (tabla, filas en tabla, duración en segundos).

        Preconditions
        --------------
        `fetch()` debe devolver un DataFrame válido.

        Example
        --------
        >>> # table, rows, dur = adapter.run()  # doctest: +SKIP
        """
        t0 = time.time()
        df = self.fetch()
        df = self.normalize(df)
        df = self.postprocess(df)
        table, rows = self.load(df)
        return table, rows, time.time() - t0


def get_adapter(name: str) -> type["BaseAdapter"]:
    """
    Recupera la clase adaptador registrada bajo un nombre.

    Parameters
    ----------
    name : str
        Clave del adaptador.

    Returns
    -------
    type[BaseAdapter]
        Clase del adaptador solicitado.

    Raises
    ------
    ValueError
        Si el nombre no está registrado.

    Example
    --------
    >>> # Adapter = get_adapter('csv')  # doctest: +SKIP
    """
    if name not in ADAPTERS:
        raise ValueError(f"Adapter '{name}' no registrado.")
    return ADAPTERS[name]
