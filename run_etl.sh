#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# activar venv
if [[ -f ".venv/Scripts/activate" ]]; then
  # Git Bash en Windows
  source ".venv/Scripts/activate"
else
  source ".venv/bin/activate"
fi
python -m app.etl
python -m app.bi
python -m app.report
echo
echo "Listo. Abre data/reports para ver resultados."
