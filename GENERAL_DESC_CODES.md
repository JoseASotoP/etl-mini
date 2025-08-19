# GENERAL_DESC_CODES.md

Descripción funcional (no técnica) de cada módulo del proyecto **etl-mini**. Para cada fichero se indica:
- **Objetivo fundamental**: qué papel cumple en el sistema.
- **Inputs**: qué recibe (parámetros, ficheros, configuración, servicios).
- **Outputs**: qué produce (tablas DuckDB, ficheros, métricas, registros).

> Nota: Algunos nombres aquí listados corresponden a archivos existentes y otros a paquetes o variantes mencionadas en la conversación. Si un nombre no existe literalmente en tu árbol de ficheros (p. ej. `sources.py`), su rol suele estar cubierto por el paquete `app/sources/` y su `__init__.py`.

---

## app/__main__.py
**Objetivo fundamental**  
Punto de entrada unificado (ejecutor). Permite lanzar desde consola distintas tareas (ETL, BI, runner, report) centralizando la experiencia de uso.

**Inputs**  
- Argumentos de línea de comandos (p. ej., modo de ejecución).
- Configuración básica del proyecto si la consulta.

**Outputs**  
- Invoca a los módulos correspondientes (no genera artefactos propios).
- Mensajes por consola sobre la tarea despachada.

---

## app/etl.py
**Objetivo fundamental**  
ETL mínima “local-first”. Carga ficheros desde `data/input/` y los deja disponibles en DuckDB para análisis posterior.

**Inputs**  
- Ficheros en `data/input/` (CSV/XLSX).  
- (Opcional) Parámetros de ejecución desde CLI.

**Outputs**  
- Tablas en `data/warehouse.duckdb` (una por fichero).  
- Log de ejecución en `data/reports/*.log`.  
- Mensajes por consola (“ETL finalizado”, conteos, avisos de formato).

---

## app/bi.py
**Objetivo fundamental**  
BI rápido (exploratorio). Ejecuta agregaciones sencillas y genera un gráfico básico sobre una tabla concreta.

**Inputs**  
- Nombre de una tabla existente en DuckDB.  
- (Opcional) Parámetros de agregación (según implementación).

**Outputs**  
- CSV con resultados agregados en `data/reports/`.  
- PNG del gráfico en `data/plots/`.  
- Mensajes por consola con rutas de salida y estado.

---

## app/clean.py
**Objetivo fundamental**  
Limpieza controlada de artefactos. Borra tablas de DuckDB y/o ficheros generados (por prefijo o en bloque).

**Inputs**  
- Flags de CLI: `--prefix`, `--all`, `--yes` (confirmación no interactiva).

**Outputs**  
- Eliminación de tablas en `data/warehouse.duckdb`.  
- Eliminación de ficheros en `data/reports/` y `data/plots/`.  
- Resumen por consola de lo borrado.

---

## app/report.py
**Objetivo fundamental**  
Generar un informe HTML simple (snapshot) con resultados/figuras de una tabla o ejecución.

**Inputs**  
- Nombre de tabla (u otros identificadores de contexto).  
- Datos ya presentes en DuckDB.  

**Outputs**  
- Informe HTML en `data/reports/*.html` (incluye títulos, métricas/resumen y/o gráficos).  
- Mensajes por consola con la ruta del reporte.

---

## app/runner.py
**Objetivo fundamental**  
Orquestador configurable. Lee `config/sources.yml` para ejecutar **grupos** de fuentes (p. ej. `daily`) y aplica reglas de calidad de `config/dq.yml` antes de cargar.

**Inputs**  
- `config/sources.yml`: definición de fuentes, grupos y parámetros.  
- `config/dq.yml`: reglas declarativas de calidad (tipos, nulos, unicidad, rangos).  
- Flags CLI: `--group <nombre>` (qué grupo ejecutar).  
- Acceso a Internet para fuentes remotas.

**Outputs**  
- Tablas en DuckDB por cada fuente ejecutada.  
- CSV snapshot opcional en `data/reports/`.  
- Log por consola con filas cargadas, tiempo y resultado DQ.  
- (Opcional/futuro) Métricas/ledger de ejecución para monitorización.

---

## app/sources.py *(si existe como módulo único; si no, ver paquete `app/sources/`)*
**Objetivo fundamental**  
Registro (registry) y utilidades comunes para resolver por **nombre** el adaptador/fuente a ejecutar. Centraliza “qué fuente usa qué clase”.

**Inputs**  
- Nombres de fuente (desde `config/sources.yml`).  
- Parámetros propios de cada adaptador.

**Outputs**  
- Instancias del adaptador correcto (no genera artefactos por sí mismo).

---

## app/status.py *(opcional, si existe)*
**Objetivo fundamental**  
Consulta del estado de ejecuciones recientes (últimos runs, métricas básicas).

**Inputs**  
- Tablas de seguimiento/ledger si existen (p. ej. `etl_runs`, `etl_metrics`) o inspección de timestamps y ficheros en `data/reports/`.

**Outputs**  
- Listados por consola o CSV/HTML con el último estado y estadísticas mínimas.

---

## app/utils.py
**Objetivo fundamental**  
Utilidades transversales: logging, conexión a DuckDB, helpers de tiempo/paths y guardado de artefactos (CSV/PNG).

**Inputs**  
- Parámetros de funciones utilitarias (p. ej., nombre de tabla, DataFrame, ruta).  
- (Opcional) Config global si se leyera desde `config/settings.toml`.

**Outputs**  
- Conexión a `data/warehouse.duckdb`.  
- Ficheros guardados en `data/reports/` y `data/plots/`.  
- Registros estandarizados en consola y/o logs.

---

## app/__init__.py
**Objetivo fundamental**  
Marcar `app/` como paquete Python. Opción de exponer metadatos (p. ej., `__version__`).

**Inputs**  
- No aplica (salvo importaciones puntuales).

**Outputs**  
- Disponibilidad del paquete para `python -m app.<módulo>` e importaciones.

---

# Paquete de fuentes: `app/sources/`

Contiene adaptadores concretos por proveedor y utilidades base. Cada adaptador se encarga de **obtener**, **normalizar** y **cargar** datos en DuckDB.

## app/sources/github.py
**Objetivo fundamental**  
Consumir la API pública de GitHub para obtener **metadatos de repositorio** (y, cuando esté disponible, estadísticas de commits).

**Inputs**  
- Parámetros: `owner`, `repo`.  
- API pública de GitHub (opcional `GITHUB_TOKEN`/`Authorization` para elevar límites).

**Outputs**  
- Tabla en DuckDB `gh_<owner>_<repo>` (1 fila de snapshot).  
- CSV snapshot en `data/reports/` (opcional).  
- Mensajes de estado por consola.

---

## app/sources/openmeteo_air.py
**Objetivo fundamental**  
Descargar datos de **calidad del aire** (p. ej., PM2.5) horarios con lat/lon desde Open-Meteo.

**Inputs**  
- Parámetros: `latitude`, `longitude`, `parameter` (ej.: `pm25`), `past_days`.  
- API pública de Open-Meteo (sin autenticación).

**Outputs**  
- Tabla en DuckDB `aq_<nombre>_<parameter>` (p. ej., `aq_madrid_pm25`).  
- CSV snapshot en `data/reports/` (opcional).  
- Mensajes de filas y rutas por consola.

---

## app/sources/usgs.py
**Objetivo fundamental**  
Ingerir eventos sísmicos (terremotos) desde USGS en rango de fechas y filtro de magnitud.

**Inputs**  
- Parámetros: `starttime/endtime` (o días recientes), `minmagnitude`.  
- API pública USGS (GeoJSON).

**Outputs**  
- Tabla `usgs_quakes_<ventana>_m<minmag>` (p. ej., `usgs_quakes_7d_m40`).  
- CSV snapshot en `data/reports/` (opcional).  
- Mensajes por consola con conteos y nombres de tabla.

---

## app/sources/worldbank.py
**Objetivo fundamental**  
Traer series anuales de indicadores macro (Banco Mundial), normalizadas por país/indicador.

**Inputs**  
- Parámetros: `country` (ISO-2/3), `indicator` (p. ej., `SP.POP.TOTL`).  
- API pública World Bank (JSON).

**Outputs**  
- Tabla `wb_<country>_<indicator>` (p. ej., `wb_esp_sp_pop_totl`).  
- CSV snapshot en `data/reports/` (opcional).  
- Mensajes por consola con filas y rutas de salida.

---

## app/sources/base.py
**Objetivo fundamental**  
Definir la **interfaz** de un adaptador de fuente y utilidades comunes (fetch → normalize → load). Base para implementar nuevas fuentes sin romper el runner.

**Inputs**  
- Parámetros genéricos de inicialización (nombre lógico, destino de tabla, opciones de red/timeout).  
- Data cruda obtenida por `fetch()` en cada implementación.

**Outputs**  
- DataFrame normalizado listo para `load()` en DuckDB.  
- Contratos claros que cumplen los adaptadores concretos.

---

## app/sources/csv_local.py
**Objetivo fundamental**  
Cargar ficheros locales CSV/XLSX con normalización básica de columnas y tipos.

**Inputs**  
- Rutas de ficheros locales (p. ej., `data/input/*.csv`).  
- (Opcional) Mapeos de nombres/tipos desde config para normalizar.

**Outputs**  
- Tabla en DuckDB por fichero (o por patrón configurado).  
- Mensajes por consola; CSV/plots secundarios si se programan.

---

## app/sources/http_json.py
**Objetivo fundamental**  
Adaptador genérico para **endpoints HTTP/JSON**. Permite parametrizar URL, headers y mapeo “JSON → columnas” sin escribir código nuevo por fuente.

**Inputs**  
- URL (con plantillas de parámetros), headers opcionales.  
- (Opcional) Reglas de extracción (paths/keys) y casting de tipos desde `config/sources.yml`.

**Outputs**  
- Tabla en DuckDB con las columnas definidas.  
- CSV snapshot opcional en `data/reports/`.  
- Mensajes por consola con estado, filas y tiempos.

---

## app/sources/__init__.py
**Objetivo fundamental**  
Marcar `app/sources/` como paquete y, si se desea, registrar/descubrir adaptadores disponibles para el runner.

**Inputs**  
- Importaciones de adaptadores concretos.  
- (Opcional) Registro estático/dinámico de clases.

**Outputs**  
- Disponibilidad del paquete para `python -m app.sources.<modulo>`.  
- Posible diccionario/registry para resolver adaptadores por nombre.
