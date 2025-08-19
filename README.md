# etl-mini

MVP sencillo para **ETL + DQ + carga en DuckDB** con ejecución por **configuración** (YAML).  
Objetivo: acercar el dato a perfiles no técnicos y sentar base para BI/ML/LLM en siguientes versiones.

## Características (v0.1.0)
- **Fuentes configuradas** en `config/sources.yml` (World Bank, Open-Meteo, USGS; extensible).
- **Reglas DQ** declarativas por tabla en `config/dq.yml` (tipos, nulos, unicidad, rangos).
- **Runner** `app/runner.py`: ejecuta grupo → fuentes, aplica DQ, carga en `data/warehouse.duckdb`.
- **Informes/artefactos**: CSVs y logs en `data/reports/`; plots en `data/plots/`.
- **Limpieza** segura por prefijo o completa (`app/clean.py`).

> Requisitos: Python 3.11+, DuckDB, pandas, matplotlib, pydantic, apscheduler.

## Estructura
app/
runner.py # orquestador por config (YAML)
etl.py # ETL mínima local
bi.py # BI mínima (top N / plot)
report.py # reporte HTML mínimo
clean.py # limpieza de tablas/archivos
utils.py # utilidades comunes
sources/ # conectores
base.py
csv_local.py
http_json.py
worldbank.py
openmeteo_air.py
usgs.py
github.py
config/
sources.yml # definición de fuentes y grupos
dq.yml # reglas de calidad por tabla
data/
input/ # CSV/XLSX de entrada
reports/ # logs, csvs volcados, html
plots/ # imágenes generadas

## Cómo ejecutar
```bash
# 1) ETL mínima local (si hay data/input/ventas.csv)
python -m app.etl

# 2) BI mínima sobre tabla 'ventas'
python -m app.bi ventas

# 3) Reporte HTML mínimo
python -m app.report ventas

# 4) Runner por configuración (grupo 'daily')
python -m app.runner --group daily

# 5) Limpiar artefactos
python -m app.clean --prefix wb_ --yes   # por prefijo
python -m app.clean --all --yes          # limpiar todo
```

## Configuración
• Fuentes: `config/sources.yml` (grupos, endpoints/queries, mapeos, destino DuckDB).  
• Calidad: `config/dq.yml` (tipos esperados, no nulos, unicidad, rangos, expresiones).

## Roadmap corto
• v0.2.0: Ledger de ejecuciones + app/status.py (observabilidad mínima).  
• v0.3.0: Fuente csv_local/http_json desde YAML (sin tocar código).  
• v0.4.0: Exportadores (Parquet), dashboard básico (Grafana/Metabase).  
• v1.0.0: LLM/Agente asistente + LangGraph (opt-in).

## Licencia
Apache 2.0 en LICENSE.