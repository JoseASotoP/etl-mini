@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Activa venv si existe (opcional)
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat

echo Ejecutando ETL-mini...
python -m app.etl %*
if errorlevel 1 (
  echo Hubo un error. Revisa data\reports\*.log
  pause
)
