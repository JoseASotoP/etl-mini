# Changelog

Todos los cambios notables de este proyecto se documentarán en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/)
y este proyecto se adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
