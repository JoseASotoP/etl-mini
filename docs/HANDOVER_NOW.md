# Handover inmediato (v0.4.x → v0.5.0 base)

## Qué hay en marcha
- Runner: app/runner.py (incremental + DQ + ledger + export parquet opcional).
- Config YAML: config/sources.yml (wb_esp_pop, aq_madrid_pm25, usgs_quakes_7d_m40).
- DQ: config/dq.yml.
- DB local: data/warehouse.duckdb (ledger: etl_runs, etl_metrics).
- UI: app/serve.py (Streamlit) — lanzar con `streamlit run app/serve.py` o `python -m streamlit run app/serve.py`.
- CI: .github/workflows/ci.yml (Python 3.11; smoke tests).

## Comandos de operación
- Ejecutar grupo diario: `python -m app.runner --group daily`
- Estado (tabla y JSON): `python -m app.status --last`  |  `python -m app.status --last --json`
- UI (Windows): 
  - `set PYTHONPATH=%CD%` (si hace falta) 
  - `streamlit run app\serve.py`
- Verificar parquet PM25:  
  `python - <<'PY'
import duckdb; con=duckdb.connect('data/warehouse.duckdb')
print(con.execute("SELECT year, month, COUNT(*) c FROM parquet_scan('data/parquet/aq_madrid_pm25/year=*/month=*/*.parquet') GROUP BY 1,2 ORDER BY 1,2").fetchdf())
PY`

## Rutas y particionado
- Parquet PM25: data/parquet/aq_madrid_pm25/year=*/month=*/*.parquet (creado desde export_parquet del YAML).

## Qué mirar si algo falla
- DQ: ver etl_metrics.dq_pass / dq_violations y logs en consola.
- Parquet vacío: comprobar `export_parquet` en YAML y permisos de `data/parquet/*`.
- Import UI: si sale `ModuleNotFoundError: app`, exportar PYTHONPATH como arriba.

## Próximos hitos (resumen roadmap)
- v0.5.0: UI sencilla (botón Ejecutar/Estado/Explorar/Export), NL→SQL básico con previsualización.
- v0.6.0: Copiloto (LangGraph) para explicar fallos, proponer DQ y graficar.
- v0.7.0: Forecast + anomalías con explicación natural.
- v0.8.0: Abstracción de storage (DuckDB/Parquet/S3/ClickHouse/Postgres).
- v0.9.0: Linaje, RBAC simple, cuarentena DQ, replays.
- v1.0.0: Installer/Docker, onboarding <30min, observabilidad.

## Commit/branch de referencia
- Rama activa: dev (tracking origin/dev).
- Últimos tags: v0.4.0 publicado.
