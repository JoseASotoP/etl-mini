# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Reporte HTML simple de una ejecución ETL.

Genera un HTML agregando el contenido de `last_run.txt` y los perfiles
`profile_*.md` encontrados en la carpeta de reportes configurada.
"""

import datetime as dt
from pathlib import Path
from typing import List

from .utils import load_settings


def assemble_report() -> Path:
    """
    Construye un reporte HTML de la última ejecución ETL.

    La función compone un documento HTML con un resumen (`last_run.txt`)
    y la representación en texto plano de cada fichero `profile_*.md`.
    El archivo se guarda con nombre `run_YYYYmmdd_HHMMSS.html` en la
    carpeta de reportes configurada y devuelve su ruta.

    Parameters
    ----------
    None

    Returns
    -------
    pathlib.Path
        Ruta al archivo HTML generado.

    Preconditions
    --------------
    Debe existir configuración válida con la clave `reports_dir` o, en su
    defecto, la ruta por defecto `data/reports` debe poder crearse.

    Example
    --------
    >>> p = assemble_report()  # doctest: +SKIP
    >>> p.exists()             # doctest: +SKIP
    True
    """
    cfg = load_settings()
    reports_dir = Path(cfg.get("reports_dir", "data/reports"))
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = reports_dir / f"run_{ts}.html"

    profiles = sorted(reports_dir.glob("profile_*.md"))
    last_path = reports_dir / "last_run.txt"
    last_run = (
        last_path.read_text(encoding="utf-8") if last_path.exists() else ""
    )

    html = [
        (
            "<html><head><meta charset='utf-8'><title>ETL Run</title>"
            "</head><body>"
        ),
        "<h1>ETL – Reporte de ejecución</h1>",
        "<h2>Resumen</h2>",
        f"<pre>{last_run}</pre>",
        "<h2>Perfiles</h2>",
    ]

    for md in profiles:
        html.append(f"<h3>{md.name}</h3>")
        # Render plano (sin markdown).
        html.append(
            "<pre>"
            + md.read_text(encoding="utf-8")
            + "</pre>"
        )

    html.append("</body></html>")
    out.write_text("\n".join(html), encoding="utf-8")
    return out


if __name__ == "__main__":
    p = assemble_report()
    print("Reporte generado:", p)
