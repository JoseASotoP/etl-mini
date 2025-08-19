# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Adaptador local de CSV para ETL-mini.

Lee un archivo CSV desde disco y lo entrega como DataFrame sin cambios.
"""

from typing import Any, Dict

import pandas as pd

from .base import BaseAdapter, register_adapter


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
