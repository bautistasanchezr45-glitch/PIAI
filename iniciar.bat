@echo off
cd /d "%~dp0"
python server.py
if errorlevel 1 (
  echo.
  echo No se pudo iniciar. Asegurate de tener Python 3 instalado y disponible como "python".
  pause
)
