# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Fuentes de datos para ETL-mini: CSV, Excel, JSON local y API REST.

Define el modelo base de fuente, utilidades de lectura/escritura JSON,
acceso por rutas en objetos anidados y la fábrica `source_from_dict`.
"""

from typing import Any, Dict, List, Optional, Literal, Tuple
from pathlib import Path
import json
import os
import time

import pandas as pd
from pydantic import BaseModel, Field

# Para APIs
try:
    import requests
except ImportError as e:
    raise ImportError(
        "Falta 'requests'. Instala con: pip install requests"
    ) from e


# --------------------------- Utilidades pequeñas ---------------------------


def _read_json_file(path: Path) -> Dict[str, Any]:
    """
    Lee un archivo JSON y devuelve su contenido como dict.

    Parameters
    ----------
    path : pathlib.Path
        Ruta del archivo JSON.

    Returns
    -------
    Dict[str, Any]
        Contenido del JSON. Si no existe, devuelve {}.

    Preconditions
    --------------
    El archivo, si existe, debe tener formato JSON válido UTF-8.

    Example
    --------
    >>> _read_json_file(Path('no_existe.json'))
    {}
    """
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json_file(path: Path, data: Dict[str, Any]) -> None:
    """
    Escribe un dict como archivo JSON (UTF-8, sangría 2).

    Parameters
    ----------
    path : pathlib.Path
        Ruta destino del JSON.
    data : Dict[str, Any]
        Datos a serializar.

    Returns
    -------
    None

    Preconditions
    --------------
    La carpeta padre debe poder crearse si no existe.

    Example
    --------
    >>> _write_json_file(Path('out.json'), {'ok': True})  # doctest: +SKIP
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _json_path_get(obj: Any, path: Optional[str]) -> Any:
    """
    Accede a una ruta tipo 'a.b.c' en un objeto JSON anidado.

    Si `path` es None o vacío, devuelve `obj`.

    Parameters
    ----------
    obj : Any
        Objeto de entrada (dict/list anidados).
    path : Optional[str]
        Ruta separada por puntos.

    Returns
    -------
    Any
        Subobjeto encontrado o None si no existe.

    Preconditions
    --------------
    Se espera que `obj` sea indexable como dict a cada nivel.

    Example
    --------
    >>> _json_path_get({'a': {'b': 1}}, 'a.b')
    1
    """
    if not path:
        return obj
    cur = obj
    for k in path.split("."):
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    return cur


# ------------------------------- Modelos base ------------------------------


LoadMode = Literal["replace", "append", "upsert"]


class BaseSource(BaseModel):
    """
    Modelo base de fuente con metadatos y control incremental.

    Parameters
    ----------
    type : Literal['csv','excel','json','api']
        Tipo de fuente concreta.
    target_table : str
        Tabla destino en DuckDB.
    load_mode : LoadMode, default='replace'
        Modo de carga: replace | append | upsert.
    name : Optional[str]
        Nombre lógico de la fuente (por defecto, target_table).
    every_minutes : Optional[int]
        Periodicidad sugerida en minutos (si se programa).
    since_field : Optional[str]
        Campo incremental en datos fuente.
    since_value : Optional[str]
        Marca incremental previa (ISO/ID).
    key_columns : Optional[List[str]]
        Claves para upsert.

    Returns
    -------
    None

    Preconditions
    --------------
    Las subclases deben implementar `extract`.

    Example
    --------
    >>> class Dummy(BaseSource):
    ...     type: Literal['csv'] = 'csv'
    ...     path: str
    ...     def extract(self, state_dir: Path):
    ...         return pd.DataFrame(), None
    """
    type: Literal["csv", "excel", "json", "api"]
    target_table: str
    load_mode: LoadMode = "replace"
    name: Optional[str] = None
    every_minutes: Optional[int] = None

    # Incremental
    since_field: Optional[str] = None
    since_value: Optional[str] = None
    key_columns: Optional[List[str]] = None

    class Config:
        extra = "allow"

    def source_name(self) -> str:
        """Devuelve nombre lógico de la fuente."""
        return self.name or self.target_table

    def extract(self, state_dir: Path) -> Tuple[pd.DataFrame, Optional[str]]:
        """
        Ejecuta la extracción. Debe ser redefinida por subclases.

        Parameters
        ----------
        state_dir : pathlib.Path
            Carpeta para leer/escribir estado incremental.

        Returns
        -------
        Tuple[pandas.DataFrame, Optional[str]]
            Datos extraídos y nueva marca incremental.

        Raises
        ------
        NotImplementedError
            Si no se implementa en la subclase.
        """
        raise NotImplementedError


# ------------------------------- Fuentes file ------------------------------


class FileCSVSource(BaseSource):
    """
    Fuente de archivo CSV.

    Parameters
    ----------
    path : str
        Ruta al archivo CSV.
    encoding : Optional[str]
        Codificación del archivo.
    sep : Optional[str]
        Separador de columnas.

    Returns
    -------
    None
    """
    type: Literal["csv"] = "csv"
    path: str
    encoding: Optional[str] = None
    sep: Optional[str] = None

    def extract(self, state_dir: Path) -> Tuple[pd.DataFrame, Optional[str]]:
        """
        Lee un CSV y devuelve el DataFrame.

        Parameters
        ----------
        state_dir : pathlib.Path
            No se usa; presente por interfaz.

        Returns
        -------
        Tuple[pandas.DataFrame, Optional[str]]
            DataFrame y None (sin incremental).
        """
        df = pd.read_csv(self.path, encoding=self.encoding, sep=self.sep)
        return df, None


class FileExcelSource(BaseSource):
    """
    Fuente de archivo Excel.

    Parameters
    ----------
    path : str
        Ruta al archivo Excel.
    sheet : Optional[str]
        Nombre de pestaña.

    Returns
    -------
    None
    """
    type: Literal["excel"] = "excel"
    path: str
    sheet: Optional[str] = None

    def extract(self, state_dir: Path) -> Tuple[pd.DataFrame, Optional[str]]:
        """
        Lee un Excel (requiere `openpyxl`) y devuelve el DataFrame.

        Parameters
        ----------
        state_dir : pathlib.Path
            No se usa; presente por interfaz.

        Returns
        -------
        Tuple[pandas.DataFrame, Optional[str]]
            DataFrame y None (sin incremental).
        """
        df = pd.read_excel(self.path, sheet_name=self.sheet)
        return df, None


class FileJSONSource(BaseSource):
    """
    Fuente de archivo JSON.

    Parameters
    ----------
    path : str
        Ruta al archivo JSON.
    records_path : Optional[str]
        Ruta dentro del JSON (p. ej., 'data.items').

    Returns
    -------
    None
    """
    type: Literal["json"] = "json"
    path: str
    records_path: Optional[str] = None

    def extract(self, state_dir: Path) -> Tuple[pd.DataFrame, Optional[str]]:
        """
        Lee JSON y normaliza registros (aplica `records_path` si existe).

        Parameters
        ----------
        state_dir : pathlib.Path
            No se usa; presente por interfaz.

        Returns
        -------
        Tuple[pandas.DataFrame, Optional[str]]
            DataFrame normalizado y None (sin incremental).
        """
        raw = _read_json_file(Path(self.path))
        payload = _json_path_get(raw, self.records_path)
        if payload is None:
            # Si no hay records_path válido, usa la raíz tal cual
            if isinstance(raw, list):
                payload = raw
            else:
                payload = raw
        df = pd.json_normalize(payload)
        return df, None


# -------------------------------- Fuente API --------------------------------


class APISource(BaseSource):
    """
    Fuente de API REST con paginación e incremental opcional.

    Parameters
    ----------
    method : Literal['GET','POST'], default='GET'
        Método HTTP.
    url : str
        URL base de la API.
    params : Dict[str, Any]
        Parámetros de consulta iniciales.
    headers : Dict[str, str]
        Cabeceras (admite ${ENV_VAR}).
    json_body : Optional[Dict[str, Any]]
        Cuerpo JSON para POST.
    records_path : Optional[str]
        Ruta en el JSON donde están los registros.
    next_field : Optional[str]
        Clave donde viene el cursor/URL de siguiente página.
    next_param : Optional[str]
        Nombre del parámetro para pasar el cursor.
    max_pages : int
        Límite de páginas a recorrer.
    page_sleep : float
        Pausa entre páginas (seg).

    Returns
    -------
    None
    """
    type: Literal["api"] = "api"
    method: Literal["GET", "POST"] = "GET"
    url: str
    params: Dict[str, Any] = Field(default_factory=dict)
    headers: Dict[str, str] = Field(default_factory=dict)
    json_body: Optional[Dict[str, Any]] = None

    # Dónde están los registros
    records_path: Optional[str] = None

    # Paginación (opcional)
    next_field: Optional[str] = None
    next_param: Optional[str] = None
    max_pages: int = 5
    page_sleep: float = 0.5

    def extract(self, state_dir: Path) -> Tuple[pd.DataFrame, Optional[str]]:
        """
        Extrae registros desde API con soporte de paginación e incremental.

        Lee estado previo (since_value), añade a params si aplica, recorre
        páginas hasta `max_pages`, normaliza a DataFrame y devuelve `df`
        junto con nueva marca (máximo de `since_field`).

        Parameters
        ----------
        state_dir : pathlib.Path
            Carpeta donde se guarda/lee el estado incremental.

        Returns
        -------
        Tuple[pandas.DataFrame, Optional[str]]
            DataFrame de registros y nueva since (o None).

        Preconditions
        --------------
        La API debe responder JSON. Si hay `next_param` se usa cursor, si
        no, se asume `next_field` como URL completa.

        Example
        --------
        >>> # APISource(...).extract(Path('data/state'))  # doctest: +SKIP
        """
        session = requests.Session()
        session.headers.update(self._resolved_headers())

        state_path = state_dir / f"{self.source_name()}.json"
        state = _read_json_file(state_path)
        last_since = state.get("since_value") or self.since_value

        params = dict(self.params or {})
        if self.since_field and last_since:
            params[self.since_field] = last_since

        all_rows: List[Dict[str, Any]] = []
        url = self.url
        pages = 0
        new_since: Optional[str] = None

        while pages < self.max_pages and url:
            if self.method == "GET":
                resp = session.get(
                    url, params=params, json=None, timeout=30
                )
            else:
                resp = session.post(
                    url, params=None, json=self.json_body, timeout=30
                )

            resp.raise_for_status()
            data = resp.json()
            records = _json_path_get(data, self.records_path) or data

            rows = pd.json_normalize(records).to_dict(orient="records")
            all_rows.extend(rows)

            nxt = (
                _json_path_get(data, self.next_field)
                if self.next_field
                else None
            )
            if nxt and self.next_param:
                params[self.next_param] = nxt
            else:
                url = nxt if isinstance(nxt, str) else None

            pages += 1
            if url and not self.next_param:
                # Si next es URL completa, no mantenemos params
                params = {}
            if url:
                time.sleep(self.page_sleep)

        df = pd.DataFrame(all_rows)

        if (
            self.since_field
            and self.since_field in df.columns
            and not df.empty
        ):
            try:
                new_since = str(df[self.since_field].max())
            except Exception:
                new_since = None

        return df, new_since

    def _resolved_headers(self) -> Dict[str, str]:
        """
        Expande variables de entorno en headers del tipo ${ENV_VAR}.

        Parameters
        ----------
        None

        Returns
        -------
        Dict[str, str]
            Cabeceras con sustituciones aplicadas.

        Example
        --------
        >>> # APISource(...)._resolved_headers()  # doctest: +SKIP
        """
        out: Dict[str, str] = {}
        for k, v in (self.headers or {}).items():
            if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                env_key = v[2:-1]
                out[k] = os.getenv(env_key, "")
            else:
                out[k] = v
        return out


# ---------------------------- Fábrica de fuentes ----------------------------


def source_from_dict(d: Dict[str, Any]) -> BaseSource:
    """
    Construye una fuente concreta a partir de un dict de configuración.

    Parameters
    ----------
    d : Dict[str, Any]
        Configuración con clave `type` y campos específicos.

    Returns
    -------
    BaseSource
        Instancia de la fuente correspondiente.

    Raises
    ------
    ValueError
        Si el tipo indicado no es reconocido.

    Example
    --------
    >>> source_from_dict({'type': 'csv', 'path': 'f.csv', 'target_table': 't'})
    ... # doctest: +ELLIPSIS
    """
    t = d.get("type")
    if t == "csv":
        return FileCSVSource(**d)
    if t == "excel":
        return FileExcelSource(**d)
    if t == "json":
        return FileJSONSource(**d)
    if t == "api":
        return APISource(**d)
    raise ValueError(f"Tipo de fuente desconocido: {t}")
