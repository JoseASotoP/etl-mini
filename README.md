# etl-mini

MVP sencillo para **ETL + DQ + carga en DuckDB** con ejecución por **configuración declarativa (YAML)**.  
Objetivo: acercar el dato a perfiles no técnicos y sentar base para BI/ML/LLM en siguientes versiones.

## 🚀 Características

### v0.1.0
- **Fuentes configuradas** en `config/sources.yml` (World Bank, Open-Meteo, USGS; extensible).
- **Reglas DQ** en `config/dq.yml` (tipos, nulos, unicidad, rangos).
- **Runner** `app/runner.py`: ejecuta grupo → aplica DQ → carga en `data/warehouse.duckdb`.
- **Informes/artefactos**: CSVs, logs en `data/reports/`, plots en `data/plots/`.
- **Utilidades mínimas**: `app/etl.py`, `app/bi.py`, `app/report.py`, `app/clean.py`.

### v0.2.0
- **Ledger en DuckDB**: tablas `etl_runs` y `etl_metrics`.  
- **Campo `loaded_at`** en métricas y cargas.  
- **CLI `app.status`** para ver ejecuciones recientes y métricas.

### v0.3.0 (actual)
- **Config-first**: definición de fuentes y grupos en `config/sources.yml`.
- **Adaptadores incluidos**: `csv_local`, `http_json`.
- **Data Quality (DQ)**: validación declarativa en `config/dq.yml` (`schema`, `checks`).
- **Observabilidad extendida**:
  - Vista `v_etl_last`: última carga consolidada por tabla.
  - CLI `app.status` con salida en consola o JSON.
- **Health reports**: JSON por ejecución en `data/reports/`.

---

## 📦 Requisitos

- Python 3.9+
- Instalar dependencias:
  ```bash
  pip install -r requirements.txt
  ```

---

## 📂 Estructura (simplificada en v0.3.0)

```
etl-mini/
├─ app/
│  ├─ adapters/         # adaptadores (csv_local, http_json)
│  ├─ runner.py         # motor ETL (ejecución por grupos)
│  ├─ status.py         # CLI de observabilidad (runs, métricas, últimas cargas)
│  └─ ...
├─ config/
│  ├─ sources.yml       # definición de fuentes y grupos
│  └─ dq.yml            # reglas de calidad de datos
├─ data/
│  ├─ warehouse.duckdb  # base de datos DuckDB
│  └─ reports/          # JSON por ejecución
├─ README.md
└─ CHANGELOG.md
```

---

## 🔧 Uso

### Ejecutar grupo de fuentes
```bash
python -m app.runner --group daily
```

### Ver estado (últimas ejecuciones y métricas)
```bash
python -m app.status
```

### Ver últimas cargas por tabla
```bash
python -m app.status --last
```

### Salida en JSON
```bash
python -m app.status --json
python -m app.status --last --json
```

---

## 🛣 Roadmap

- v0.4.0 → Almacenamiento incremental y particionado en DuckDB.  
- v0.5.0 → Integración con Power BI/Metabase (lectura directa del warehouse).  
- v0.6.0 → Nuevos adaptadores (SQL, APIs autenticadas).  
- v1.0.0 → Release estable con empaquetado vía `pip`.  

---

## 📜 Licencia
Apache 2.0 en LICENSE.
