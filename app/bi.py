from __future__ import annotations

"""BI mínimo: selección de ejes, agregación y gráficos automáticos."""

import sys
from pathlib import Path
from typing import Optional, Tuple

import duckdb
import matplotlib.pyplot as plt
import pandas as pd
import pandas.api.types as ptypes

from .utils import load_settings, connect_duckdb, ensure_dirs, get_logger


def _pick_xy(df: pd.DataFrame) -> Tuple[str, str]:
    """
    Selecciona columnas x (no numérica) e y (numérica) para graficar.

    Elige como eje x la primera columna no numérica disponible y, como eje y,
    la primera columna numérica distinta de x. Si no se encuentran, aplica
    una política de reserva usando la primera o última columna.

    Parameters
    ----------
    df : pandas.DataFrame
        Conjunto de datos de entrada con ≥1 columna.

    Returns
    -------
    Tuple[str, str]
        Nombres de columnas seleccionadas para x e y, respectivamente.

    Preconditions
    --------------
    El DataFrame debe contener al menos una columna. Para mejores resultados,
    es recomendable que exista al menos una columna no numérica y otra
    numérica.

    Example
    --------
    >>> import pandas as pd
    >>> datos = pd.DataFrame({'fecha': ['2024-01-01', '2024-01-02'],
    ...                       'valor': [10, 12]})
    >>> _pick_xy(datos)
    ('fecha', 'valor')
    """
    cols = list(df.columns)
    x = next(
        (c for c in cols if not ptypes.is_numeric_dtype(df[c])),
        cols[0],
    )
    y = next(
        (c for c in cols if c != x and ptypes.is_numeric_dtype(df[c])),
        cols[-1] if len(cols) > 1 else cols[0],
    )
    return x, y


def _autoplot(df: pd.DataFrame, out: Path, title: str) -> str:
    """
    Genera un PNG: línea si x parece fecha; en otro caso, barras (top 10).

    Detecta si x es fecha (o convertible) para decidir el tipo de gráfico.
    Guarda el resultado en `out` y devuelve la ruta como cadena.

    Parameters
    ----------
    df : pandas.DataFrame
        Datos con, al menos, dos columnas relevantes (x e y).
    out : pathlib.Path
        Ruta de salida del archivo PNG.
    title : str
        Título del gráfico.

    Returns
    -------
    str
        Ruta del archivo PNG generado.

    Preconditions
    --------------
    Debe existir al menos una columna interpretable como x y otra como y.
    Si x no es fecha, se seleccionan las 10 categorías con mayor y.

    Example
    --------
    >>> import pandas as pd
    >>> from pathlib import Path
    >>> datos = pd.DataFrame({'categoria': ['A', 'B'], 'total': [5, 7]})
    >>> _autoplot(datos, Path('salida.png'), 'Demo')
    'salida.png'
    """
    x, y = _pick_xy(df)
    plt.figure()

    # Si x parece fecha → línea; si no → barras
    looks_date = (
        ptypes.is_datetime64_any_dtype(df[x])
        or pd.to_datetime(df[x], errors="coerce").notna().mean() > 0.7
    )

    plot_df = df[[x, y]].dropna()
    if looks_date:
        plot_df = plot_df.copy()
        plot_df[x] = pd.to_datetime(plot_df[x], errors="coerce")
        plot_df = plot_df.sort_values(x)
        plt.plot(plot_df[x], plot_df[y])
    else:
        plot_df = plot_df.sort_values(y, ascending=False).head(10)
        plt.bar(plot_df[x].astype(str), plot_df[y])
        if plot_df[x].nunique() > 10:
            plt.xticks(rotation=45, ha="right")

    plt.title(title)
    plt.xlabel(x)
    plt.ylabel(y)
    plt.tight_layout()

    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out)
    plt.close()
    return str(out)


def run() -> int:
    """
    Agrega tablas de DuckDB y exporta CSV + PNG por tabla (top-k).

    Carga configuración, localiza tablas en el esquema `main`, infiere ejes
    con una muestra de hasta 2000 filas y realiza agregaciones por x con SUM
    o COUNT según sea y. Exporta un CSV y un PNG por tabla.

    Parameters
    ----------
    None

    Returns
    -------
    int
        Código de salida: 0 (ok), 2 (error en ejecución).

    Preconditions
    --------------
    Debe existir (o poder crearse) la base de datos DuckDB indicada en la
    configuración. Las tablas deben ser consultables por el usuario actual.

    Example
    --------
    >>> import sys
    >>> if __name__ == "__main__":
    ...     sys.exit(run())
    """
    cfg = load_settings()
    logger = get_logger("bi", cfg.get("reports_dir", "data/reports"))
    db_path = cfg.get("db_path", "data/warehouse.duckdb")
    plots_dir = Path(cfg.get("plots_dir", "data/plots"))
    ensure_dirs(plots_dir)

    con = connect_duckdb(db_path)
    try:
        query_tables = (
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='main'"
        )
        tables = [r[0] for r in con.execute(query_tables).fetchall()]

        if not tables:
            logger.info("No hay tablas para BI.")
            return 0

        for t in tables:
            # Muestra hasta 2000 filas para inferir tipos con pandas
            sample = con.execute(f"SELECT * FROM {t} LIMIT 2000").fetchdf()
            if sample.empty or len(sample.columns) < 2:
                continue

            x, y = _pick_xy(sample)

            # Agregación por x (topk configurable)
            topk = int(cfg.get("bi", {}).get("topk", 10))
            if ptypes.is_numeric_dtype(sample[y]):
                agg = con.execute(
                    (
                        f"SELECT {x} AS key, SUM({y}) AS total FROM {t} "
                        "GROUP BY 1 ORDER BY total DESC "
                        f"LIMIT {topk}"
                    )
                ).fetchdf()
            else:
                agg = con.execute(
                    (
                        f"SELECT {x} AS key, COUNT(*) AS total FROM {t} "
                        "GROUP BY 1 ORDER BY total DESC "
                        f"LIMIT {topk}"
                    )
                ).fetchdf()

            csv_out = (
                Path(cfg.get("reports_dir", "data/reports")) / f"{t}_top.csv"
            )
            agg.to_csv(csv_out, index=False, encoding="utf-8")
            logger.info("CSV BI → %s", csv_out.name)

            png_out = plots_dir / f"{t}_top.png"
            _autoplot(
                agg.rename(columns={"key": x, "total": "total"}),
                png_out,
                f"{t} – Top",
            )
            logger.info("Plot BI → %s", png_out.name)

        logger.info("BI mínimo OK.")
        return 0
    except Exception as e:
        logger.error("Fallo en BI: %s", e)
        return 2
    finally:
        try:
            con.close()
        except:
            pass


if __name__ == "__main__":
    sys.exit(run())
