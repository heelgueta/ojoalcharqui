@echo off
REM ojo al charqui - double-click launcher (Windows)
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

REM Prefer the py launcher, fall back to python on PATH
where py >nul 2>nul
if %errorlevel%==0 (
    py run.py
    goto :end
)
where python >nul 2>nul
if %errorlevel%==0 (
    python run.py
    goto :end
)

echo No se encontro Python. Instalalo desde https://www.python.org/downloads/
echo (marca "Add Python to PATH" durante la instalacion)
pause

:end
