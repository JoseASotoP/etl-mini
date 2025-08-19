# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Adaptador HTTP JSON y utilidades de resolución/selección de registros.

Provee `_resolve_now_token` para tokens de tiempo, `_dig` para navegar
objetos anidados y `HTTPJSONAdapter` para consumir APIs JSON con
paginación ligera y transformaciones específicas (Open-Meteo, USGS).
"""

from typing import Any, Dict, List, Union
from datetime import datetime, timedelta, timezone
import json
import urllib.parse
import urllib.request

import pandas as pd

from .base import BaseAdapter, register_adapter


def _resolve_now_token(val: str) -> str:
    """
    Resuelve tokens de tiempo: '@now', '@now-7d', '@now-24h'.

    Parameters
    ----------
    val : str
        Token o valor literal.

    Returns
    -------
    str
        Fecha/fecha-hora ISO resultante o el valor original.

    Preconditions
    --------------
    Se usa hora actual en UTC.

    Example
    --------
    >>> isinstance(_resolve_now_token("@now"), str)
    True
    """
    if not isinstance(val, str) or not val.startswith("@now"):
        return val
    now = datetime.now(timezone.utc)
    if val == "@now":
        return now.date().isoformat()
    if "-7d" in val:
        return (now - timedelta(days=7)).date().isoformat()
    if "-24h" in val:
        return (now - timedelta(hours=24)).isoformat()
    return now.isoformat()


def _dig(obj: Any, key_chain: List[Union[str, int]]):
    """
    Navega por `obj` siguiendo claves/índices en `key_chain`.

    Parameters
    ----------
    obj : Any
        Estructura anidada (dict/list).
    key_chain : List[Union[str, int]]
        Secuencia de claves (str) e índices (int).

    Returns
    -------
    Any
        Subobjeto localizado.

    Preconditions
    --------------
    Los pasos deben existir; no hay validación defensiva.

    Example
    --------
    >>> _dig({'a': [{'b': 1}]}, ['a', 0, 'b'])
    1
    """
    cur = obj
    for k in key_chain:
        if isinstance(k, int):
            cur = cur[k]
        else:
            cur = cur.get(k)
    return cur


@register_adapter("http_json")
class HTTPJSONAdapter(BaseAdapter):
    """
    Adaptador HTTP→JSON con transforms opcionales.

    Soporta:
    - `query`: dict de parámetros (resuelve '@now', '@now-7d', '@now-24h').
    - `records_key_chain`: lista de claves/índices para ubicar registros.
    - `transform`: 'hourly_time_value' (Open-Meteo) o 'usgs_features'.
    - Ruta genérica: normaliza listas/dicts y permite select/rename/enrich.

    Parameters
    ----------
    params : Dict[str, Any]
        Configuración de la fuente (url, query, transforms, …).
    context : Dict[str, Any]
        Contexto del pipeline (no usado en `fetch`).

    Returns
    -------
    None

    Preconditions
    --------------
    La URL debe devolver JSON válido y ser accesible.

    Example
    --------
    >>> # HTTPJSONAdapter({...}, {...}).fetch()  # doctest: +SKIP
    """
    def fetch(self) -> pd.DataFrame:
        """
        Llama a la API, localiza registros y devuelve un DataFrame.

        Aplica transforms específicos si se declaran; en otro caso,
        intenta normalizar la estructura JSON de forma genérica.

        Parameters
        ----------
        None

        Returns
        -------
        pandas.DataFrame
            Datos tabulares obtenidos de la API.

        Preconditions
        --------------
        `params['url']` debe existir. Tiempo de espera fijo (60 s).

        Example
        --------
        >>> # df = HTTPJSONAdapter({'url': '...'}, {}).fetch()  # doctest: +SKIP
        """
        url = self.params.get("url")
        q = self.params.get("query") or {}
        q = {k: _resolve_now_token(v) for k, v in q.items()}

        url = url + "?" + urllib.parse.urlencode(q, doseq=True)
        with urllib.request.urlopen(url, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))

        # Localizar registros si hay key_chain
        records = None
        key_chain = self.params.get("records_key_chain")
        if key_chain:
            chain = [int(k) if str(k).isdigit() else k for k in key_chain]
            records = _dig(data, chain)

        # ----------------- Transforms específicos -----------------
        if self.params.get("transform") == "hourly_time_value":
            # Open-Meteo hourly → DataFrame(t, v, +enrich)
            h = (data or {}).get("hourly", {}) or {}
            e = self.params.get("transform_args") or {}
            tkey = e.get("time_key", "time")
            vkey = e.get("value_key", "pm2_5")
            time_list = h.get(tkey) or []
            val_list = h.get(vkey) or []
            df = pd.DataFrame(
                {
                    "datetime_utc": pd.to_datetime(
                        time_list, utc=True, errors="coerce"
                    ),
                    "value": val_list,
                }
            )
            df["parameter"] = e.get("parameter")
            df["unit"] = e.get("unit")
            df["latitude"] = e.get("latitude")
            df["longitude"] = e.get("longitude")
            return df

        if self.params.get("transform") == "usgs_features":
            # USGS GeoJSON features → properties + geometry.coordinates
            feats = records if isinstance(records, list) else []
            rows: List[Dict[str, Any]] = []
            for it in feats:
                props = ((it or {}).get("properties", {})) or {}
                geom = ((it or {}).get("geometry", {})) or {}
                coords = geom.get("coordinates") or [None, None, None]
                t_ms = props.get("time")
                dt_ = (
                    pd.to_datetime(t_ms, unit="ms", utc=True, errors="coerce")
                    if t_ms is not None
                    else pd.NaT
                )
                rows.append(
                    {
                        "datetime_utc": dt_,
                        "magnitude": props.get("mag"),
                        "place": props.get("place"),
                        "event_id": props.get("code"),
                        "type": props.get("type"),
                        "status": props.get("status"),
                        "longitude": coords[0],
                        "latitude": coords[1],
                        "depth_km": coords[2],
                    }
                )
            return pd.DataFrame(rows)

        # ---------------- Ruta genérica de normalización --------------
        if records is None:
            if isinstance(data, list):
                records = data
            elif isinstance(data, dict):
                for cand in ("results", "data", "items"):
                    if cand in data and isinstance(data[cand], list):
                        records = data[cand]
                        break

        if records is None:
            # Si no hay lista clara, normalizar raíz en una fila
            return pd.json_normalize(data)

        explode_props = self.params.get("explode_properties")
        rows = []
        if explode_props:
            for it in records:
                props = ((it or {}).get(explode_props, {})) or {}
                rows.append(props)
        else:
            rows = records

        df = pd.json_normalize(rows, max_level=2)

        # select / rename / enrich
        sel = self.params.get("select")
        if sel:
            df = df[[c for c in sel if c in df.columns]]

        ren = self.params.get("rename") or {}
        if ren:
            df = df.rename(columns=ren)

        enrich = self.params.get("enrich") or {}
        for k, v in enrich.items():
            df[k] = v

        return df
