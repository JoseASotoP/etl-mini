# Changelog

Todos los cambios notables de este proyecto se documentarán en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/)
y este proyecto se adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2025-08-21
### Added
- **Runner incremental** con staging y *upsert* por claves:
  - Vista casteada con `TRY_CAST` y deduplicación por `incremental.key`.
  - Contadores de insertados, duplicados y claves nulas.
- **Export a Parquet** particionado (p. ej. `year=/month=`) configurable por YAML.
- **Ledger** completo en DuckDB:
  - Tablas `etl_runs` y `etl_metrics` con `loaded_at` por fuente.
  - Health JSON por ejecución en `data/reports/health_*.json`.
- **CLI de estado** (`python -m app.status`) con vistas:
  - Últimos runs, métricas recientes y `v_etl_last` (última carga por tabla).
- **CI (GitHub Actions)** con *smoke tests* y *bootstrap* de esquema local.
- **UI preliminar (preview)** con `app/serve.py` (Streamlit) para lanzar el runner y explorar estado.

### Changed
- `config/sources.yml` ahora soporta:
  - Bloque `mode: incremental` con `incremental.key` y `incremental.cast_map`.
  - Bloque `export_parquet` con `dir`, `partition_by`, `export_sql` y `overwrite`.
- Limpieza de *binder errors* previos (uso consistente de alias `s` en joins internos).

### Fixed
- Inserciones duplicadas en modo incremental al faltar `TRY_CAST` y filtrado de clave nula.
- Errores por vistas no encontradas al reintentar (creación/limpieza ordenada de `__castview` y `__to_insert`).

## [0.3.0] - 2025-08-19
### Added
- Configuración declarativa por YAML (`config/sources.yml`, `config/dq.yml`).
- CLI `app.status` con flags `--last` y `--json`.
- Vista `v_etl_last` para mostrar la última carga por tabla.

### Changed
- Documentación README y CHANGELOG.

## [0.2.0] - 2025-08-19
### Added
- Campo `loaded_at` en `etl_metrics` para ordenar cargas por tiempo.
- Vista `v_etl_last` inicial.
- Salida en JSON en CLI `status.py`.

## [0.1.1] - 2025-08-13
### Added
- Validación DQ con reglas `schema` y `checks` (`not_null`, `unique`, `range`).
- Registro de métricas `etl_metrics` y runs `etl_runs`.
- Reportes JSON de health.

### Changed
- Ledger `etl_metrics` con estrategia append-only.
- Observabilidad: campo `loaded_at` por fuente.

## [0.1.0] - 2025-08-12
### Added
- Estructura inicial del proyecto `etl-mini`.
- Adaptadores: CSV local y HTTP JSON.
- Motor ETL (`runner.py`) con ejecución por grupos.
