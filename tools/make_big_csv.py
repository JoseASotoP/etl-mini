# tools/make_big_csv.py
# -*- coding: utf-8 -*-
"""
Genera CSV(s) grandes para pruebas, compatibles con stg_fact_sales_order_items.
Soporta: muchos registros, columnas extra 'attr_*', tipos mezclados, y split en chunks.

Campos base:
- order_id, order_item_id, sku_id
- quantity_units, line_total_eur, discount_pct, tax_pct
- promised_date, shipped_date (a veces vacío)
- ship_from_warehouse_id
+ attr_001..attr_N (opcionales)

Uso típico:
  python tools/make_big_csv.py --rows 1500000 --out data/input/coffee/fact_sales_big.csv

Split (p.ej. 2M en 4 archivos de 500k):
  python tools/make_big_csv.py --rows 2000000 --chunk 500000 --out data/input/coffee/fact_sales_big.csv

Ancho + tipos mezclados (200 columnas attr_*):
  python tools/make_big_csv.py --rows 400000 --wide 200 --mixed

Añade negativos raros para DQ:
  python tools/make_big_csv.py --rows 500000 --negatives

"""

from __future__ import annotations
import argparse, csv, json, os, random
from datetime import datetime, timedelta
from pathlib import Path

def make_attr_value(i: int, mixed: bool, R: random.Random):
    """Valor para attr_i: si mixed=True, mezcla tipos; si no, número."""
    if not mixed:
        # solo numéricos sencillos
        return R.randint(0, 100000)
    # mezcla: int/float/texto/fecha/bool
    t = R.choice(["int", "float", "text", "date", "bool", "na"])
    if t == "int":
        return R.randint(-1000, 100000)
    if t == "float":
        return round(R.uniform(-1000, 100000), 3)
    if t == "text":
        return R.choice(["N/A", "desconocido", "ok", "pendiente", "error42"])
    if t == "date":
        d = datetime(2019,1,1) + timedelta(days=R.randint(0, 2000))
        return d.strftime("%Y-%m-%d")
    if t == "bool":
        return R.choice([True, False])
    return ""  # NA vacío

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=1_500_000, help="Filas totales a generar")
    ap.add_argument("--out", type=str, default="data/input/fact_sales_big.csv", help="Ruta base de salida")
    ap.add_argument("--seed", type=int, default=42, help="Semilla")
    ap.add_argument("--negatives", action="store_true", help="Insertar un pequeño %% de cantidades negativas")
    ap.add_argument("--chunk", type=int, default=0, help="Si >0, parte la salida en archivos de 'chunk' filas")
    ap.add_argument("--wide", type=int, default=0, help="N columnas extra attr_* (p.ej. 200)")
    ap.add_argument("--mixed", action="store_true", help="Si se usa --wide, mezcla tipos en attr_*")
    args = ap.parse_args()

    R = random.Random(args.seed)

    out_base = Path(args.out)
    out_base.parent.mkdir(parents=True, exist_ok=True)

    start = datetime(2018, 1, 1)
    end   = datetime(2025, 8, 1)
    total_days = (end - start).days

    max_sku = 5000
    warehouses = [10, 11, 12, 20, 21, 30]

    # cabeceras
    headers = [
        "order_id","order_item_id","sku_id",
        "quantity_units","line_total_eur","discount_pct","tax_pct",
        "promised_date","shipped_date","ship_from_warehouse_id",
    ]
    if args.wide > 0:
        headers += [f"attr_{i:03d}" for i in range(1, args.wide+1)]

    def write_chunk(path: Path, nrows: int, start_order_id: int) -> int:
        """Escribe nrows a 'path'. Devuelve el siguiente order_id libre."""
        next_order_id = start_order_id
        item_in_order = 0
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(headers)
            for i in range(nrows):
                # cambio de pedido cada ~5-8 líneas
                if item_in_order == 0 or R.random() < 0.18:
                    next_order_id += 1
                    item_in_order = 1
                else:
                    item_in_order += 1

                order_id = next_order_id
                order_item_id = item_in_order
                sku_id = R.randint(1, max_sku)

                qty = R.randint(1, 8)
                if args.negatives and R.random() < 0.002:
                    qty = -qty

                price = round(R.uniform(2.0, 150.0), 2)
                discount_pct = round(R.choice([0.0, 0.05, 0.10, 0.15, 0.20]) if R.random() < 0.35 else 0.0, 2)
                tax_pct = round(R.choice([0.0, 0.04, 0.10, 0.21]), 2)

                gross = qty * price
                net = gross * (1.0 - discount_pct)
                total = round(net * (1.0 + tax_pct), 2)

                pday = start + timedelta(days=R.randint(0, total_days))
                delta_days = R.choice([0, 1, 2, 3, None])
                sday = None if delta_days is None else (pday + timedelta(days=delta_days))

                promised_date = pday.strftime("%Y-%m-%d")
                shipped_date = "" if sday is None else sday.strftime("%Y-%m-%d")

                wh = R.choice(warehouses)

                row = [
                    order_id, order_item_id, sku_id,
                    qty, total, discount_pct, tax_pct,
                    promised_date, shipped_date, wh,
                ]
                if args.wide > 0:
                    row += [make_attr_value(i, args.mixed, R) for i in range(1, args.wide+1)]

                w.writerow(row)
        return next_order_id

    files = []
    remaining = args.rows
    order_seed = 0
    if args.chunk and args.chunk > 0:
        # múltiples archivos
        idx = 1
        while remaining > 0:
            n = min(remaining, args.chunk)
            path = out_base.with_name(f"{out_base.stem}_part{idx:02d}{out_base.suffix}")
            next_order = write_chunk(path, n, order_seed)
            order_seed = next_order
            remaining -= n
            files.append(str(path))
            idx += 1
    else:
        # único archivo
        path = out_base
        next_order = write_chunk(path, args.rows, order_seed)
        files = [str(path)]

    # manifest (auditoría básica)
    manifest = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "rows": args.rows,
        "out": str(out_base),
        "files": files,
        "seed": args.seed,
        "negatives": bool(args.negatives),
        "chunk": args.chunk,
        "wide": args.wide,
        "mixed": bool(args.mixed),
        "columns": headers,
    }
    man_path = out_base.with_suffix(out_base.suffix + ".manifest.json")
    with man_path.open("w", encoding="utf-8") as mf:
        json.dump(manifest, mf, ensure_ascii=False, indent=2)

    print(f"✔ Generado(s):")
    for f in files:
        print("  -", f)
    print("└─ Manifest:", man_path)

if __name__ == "__main__":
    main()
