# Changelog
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/)
y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-08-12
### Added
- Runner `app/runner.py` por configuración (`config/sources.yml`, `config/dq.yml`).
- Conectores confirmados: World Bank, Open-Meteo Air, USGS, GitHub (snapshot).
- Reglas DQ declarativas (tipos, nulos, unicidad, rangos).
- ETL/BI/Report mínimos (scripts ejecutables).
- Limpieza por prefijo o total (`app/clean.py`).
- Documentación inicial (`README.md`) y estructura de proyecto.

### Notes
- Datos y artefactos generados se ignoran en Git por defecto (`.gitignore`).
