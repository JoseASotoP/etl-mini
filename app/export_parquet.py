# app/export_parquet.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, shutil, yaml, duckdb
from typing import Any, Dict, List

CFG_PATH = "config/sources.yml"

def _load_cfg(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def _ensure_dir(dirpath: str, overwrite: bool) -> None:
    if overwrite and os.path.exists(dirpath):
        shutil.rmtree(dirpath)
    os.makedirs(dirpath, exist_ok=True)

def _export_one(con: duckdb.DuckDBPyConnection, table: str, exp_cfg: Dict[str, Any]) -> None:
    out_dir: str = exp_cfg["dir"]
    overwrite: bool = bool(exp_cfg.get("overwrite", True))
    partition_by: List[str] = exp_cfg.get("partition_by", [])
    export_sql: str = exp_cfg.get("export_sql") or f"SELECT * FROM {table}"

    _ensure_dir(out_dir, overwrite)
    part_clause = f", PARTITION_BY ({', '.join(partition_by)})" if partition_by else ""
    con.execute(f"""
        COPY ({export_sql})
        TO '{out_dir}/'
        (FORMAT PARQUET{part_clause})
    """)

def main() -> None:
    cfg = _load_cfg(CFG_PATH)
    db_path = cfg.get("defaults", {}).get("db_path", "data/warehouse.duckdb")
    con = duckdb.connect(db_path)

    # Recorremos todos los grupos y sus fuentes
    groups = cfg.get("groups", {})
    total = 0
    for gname, sources in groups.items():
        for src in sources:
            exp_cfg = src.get("export_parquet")
            if not exp_cfg:
                continue
            table = src["table"]
            print(f"[EXPORT] {src['name']} → {table}")
            _export_one(con, table, exp_cfg)
            print(f"  → Parquet en {exp_cfg['dir']} (partitions={exp_cfg.get('partition_by', [])})")
            total += 1

    if total == 0:
        print("No hay fuentes con 'export_parquet' configurado.")
    con.close()

if __name__ == "__main__":
    main()
