# tests/test_v04_extreme.py
import duckdb
import pandas as pd
import numpy as np
import os, shutil, time

def run_extreme():
    con = duckdb.connect(database="data/etl.db")
    con.execute("""
        CREATE TABLE IF NOT EXISTS wb_esp_sp_pop_totl (
            year INTEGER,
            value DOUBLE,
            indicator_id VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS aq_madrid_pm25 (
            datetime_utc TIMESTAMP,
            value DOUBLE,
            parameter VARCHAR,
            unit VARCHAR,
            latitude DOUBLE,
            longitude DOUBLE
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS wb_unemployment (
            country VARCHAR,
            year INTEGER,
            value DOUBLE,
            sector VARCHAR
        )
    """)
    # === BLOQUE 1: Población ===
    print("\n=== Población ===")
    pop_data = pd.DataFrame({
        "year": ["2019","2023","2025","2025","XXXX","2026"],
        "value": ["47000000","48347910","INVALID","49000000","50000000","51000000"],
        "indicator_id": ["SP.POP.TOTL"]*6,
        "extra_col":["noise"]*6
    })
    print(pop_data)

    con.register("pop_view", pop_data)
    before = con.execute("SELECT COUNT(*) FROM wb_esp_sp_pop_totl").fetchone()[0]
    con.execute("""
        INSERT INTO wb_esp_sp_pop_totl
        SELECT
            TRY_CAST(s.year AS INTEGER),
            TRY_CAST(s.value AS DOUBLE),
            s.indicator_id
        FROM pop_view s
        LEFT JOIN wb_esp_sp_pop_totl t
        ON TRY_CAST(s.year AS INTEGER) = t.year
        WHERE t.year IS NULL
          AND TRY_CAST(s.year AS INTEGER) IS NOT NULL
          AND TRY_CAST(s.value AS DOUBLE) IS NOT NULL
    """)
    after = con.execute("SELECT COUNT(*) FROM wb_esp_sp_pop_totl").fetchone()[0]
    print(f"Filas antes: {before}, después: {after}, nuevas: {after - before}")
    print(con.execute("SELECT * FROM wb_esp_sp_pop_totl ORDER BY year DESC LIMIT 5").fetchdf())

    # === BLOQUE 2: Contaminación (500k filas) ===
    print("\n=== PM25: staging masivo con nulos, duplicados y ruido ===")
    n = 1_000_000 // 2  # ~500k filas
    dates = pd.date_range("2020-01-01", periods=n, freq="h")

    pm25_data = pd.DataFrame({
        "datetime_raw": dates.astype(str),  # <-- siempre string
        "value_raw": np.random.randint(5, 150, size=n).astype(str),  # <-- siempre string
        "parameter": ["pm25"] * n,
        "unit": ["µg/m³"] * n,
        "latitude": np.random.uniform(40.3, 40.5, size=n),
        "longitude": np.random.uniform(-3.8, -3.6, size=n),
        "extra_noise": np.random.choice(list("ABC"), size=n),
    })

    # Introducir ruido en las columnas string
    pm25_data.loc[pm25_data.sample(frac=0.001, random_state=1).index, "datetime_raw"] = "INVALID"
    pm25_data.loc[pm25_data.sample(frac=0.001, random_state=2).index, "value_raw"] = "NaN"

    print(pm25_data.head())
    print(f"Filas en staging: {len(pm25_data)}")

    con.register("pm25_view", pm25_data)
    before = con.execute("SELECT COUNT(*) FROM aq_madrid_pm25").fetchone()[0]

    con.execute("""
        INSERT INTO aq_madrid_pm25
        SELECT
            TRY_CAST(s.datetime_raw AS TIMESTAMP) AS datetime_utc,
            TRY_CAST(s.value_raw AS DOUBLE) AS value,
            s.parameter,
            s.unit,
            TRY_CAST(s.latitude AS DOUBLE) AS latitude,
            TRY_CAST(s.longitude AS DOUBLE) AS longitude
        FROM pm25_view s
        LEFT JOIN aq_madrid_pm25 t
          ON TRY_CAST(s.datetime_raw AS TIMESTAMP) = t.datetime_utc
        WHERE t.datetime_utc IS NULL
          AND TRY_CAST(s.datetime_raw AS TIMESTAMP) IS NOT NULL
          AND TRY_CAST(s.value_raw AS DOUBLE) IS NOT NULL
    """)

    after = con.execute("SELECT COUNT(*) FROM aq_madrid_pm25").fetchone()[0]
    print(f"Filas antes: {before}, después: {after}, nuevas: {after - before}")
    print(con.execute("SELECT * FROM aq_madrid_pm25 ORDER BY datetime_utc DESC LIMIT 5").fetchdf())

    # === BLOQUE 3: Desempleo (500k filas) ===
    print("\n=== Desempleo: staging masivo con ruido ===")
    n = 500_000
    years = np.random.choice(range(2000,2030), size=n)
    countries = np.random.choice(["ES","FR","IT","DE"], size=n)
    values = np.random.uniform(5,25,size=n)
    unemploy_data = pd.DataFrame({
        "country": countries,
        "year": years,
        "value": values,
        "sector": np.random.choice(["agriculture","industry","services"], size=n)
    })
    unemploy_data.loc[unemploy_data.sample(frac=0.001, random_state=3).index,"year"] = "XXXX"
    unemploy_data.loc[unemploy_data.sample(frac=0.001, random_state=4).index,"value"] = "BAD"

    print(unemploy_data.head())
    con.register("unemp_view", unemploy_data)
    before = con.execute("SELECT COUNT(*) FROM wb_unemployment").fetchone()[0]
    con.execute("""
        INSERT INTO wb_unemployment
        SELECT
            s.country,
            TRY_CAST(s.year AS INTEGER),
            TRY_CAST(s.value AS DOUBLE),
            s.sector
        FROM unemp_view s
        LEFT JOIN wb_unemployment t
        ON s.country = t.country AND TRY_CAST(s.year AS INTEGER) = t.year
        WHERE t.year IS NULL
          AND TRY_CAST(s.year AS INTEGER) IS NOT NULL
          AND TRY_CAST(s.value AS DOUBLE) IS NOT NULL
    """)
    after = con.execute("SELECT COUNT(*) FROM wb_unemployment").fetchone()[0]
    print(f"Filas antes: {before}, después: {after}, nuevas: {after-before}")
    print(con.execute("SELECT * FROM wb_unemployment ORDER BY year DESC LIMIT 5").fetchdf())

    # === EXPORT PARQUET ===
    print("\n=== EXPORTAR Parquet ===")
    out_dir = "data/parquet/extreme"
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    # Población → partición por year
    con.execute(f"""
        COPY (
            SELECT year, value, indicator_id
            FROM wb_esp_sp_pop_totl
        )
        TO '{out_dir}/pop' (FORMAT PARQUET, PARTITION_BY (year))
    """)

    # PM25 → partición por year + month derivados de datetime_utc
    con.execute(f"""
        COPY (
            SELECT
                datetime_utc,
                value,
                parameter,
                unit,
                latitude,
                longitude,
                EXTRACT(year FROM datetime_utc) AS year,
                LPAD(EXTRACT(month FROM datetime_utc)::VARCHAR, 2, '0') AS month
            FROM aq_madrid_pm25
        )
        TO '{out_dir}/pm25' (FORMAT PARQUET, PARTITION_BY (year, month))
    """)

    # Desempleo → partición por country + year
    con.execute(f"""
        COPY (
            SELECT
                country,
                year,
                value,
                sector
            FROM wb_unemployment
        )
        TO '{out_dir}/unemp' (FORMAT PARQUET, PARTITION_BY (country, year))
    """)

    # === VALIDAR ===
    print("\n=== VALIDACIÓN ===")
    df_pop = con.execute(f"""
        SELECT year, COUNT(*) AS filas
        FROM parquet_scan('{out_dir}/pop/**/*.parquet')
        GROUP BY 1 ORDER BY 1
    """).fetchdf()

    df_pm25 = con.execute(f"""
        SELECT year, month, COUNT(*) AS filas
        FROM parquet_scan('{out_dir}/pm25/**/*.parquet')
        GROUP BY 1,2 ORDER BY 1,2
    """).fetchdf()

    df_unemp = con.execute(f"""
        SELECT country, year, COUNT(*) AS filas
        FROM parquet_scan('{out_dir}/unemp/**/*.parquet')
        GROUP BY 1,2 ORDER BY 1,2
    """).fetchdf()

    print("Población parquet:", df_pop.head())
    print("PM25 parquet:", df_pm25.head())
    print("Unemployment parquet:", df_unemp.head())

    total_parquet = (
        df_pop["filas"].sum() +
        df_pm25["filas"].sum() +
        df_unemp["filas"].sum()
    )
    total_tablas = (
        con.execute("SELECT COUNT(*) FROM wb_esp_sp_pop_totl").fetchone()[0] +
        con.execute("SELECT COUNT(*) FROM aq_madrid_pm25").fetchone()[0] +
        con.execute("SELECT COUNT(*) FROM wb_unemployment").fetchone()[0]
    )

    print(f"Total parquet={total_parquet}, Total tablas={total_tablas}")
    assert total_parquet == total_tablas, "❌ Conteos no coinciden"
    print("✅ Test EXTREMO completado correctamente")

if __name__ == "__main__":
    run_extreme()
