@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Instalando Chargeback Responder ===
echo.

set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY where python >nul 2>nul && set PY=python
if not defined PY (
    echo No se encontro Python. Instalando Python 3.12 con winget...
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    echo.
    echo Python instalado. CERRA esta ventana y volve a abrir 1_instalar.bat
    pause
    exit /b
)

echo [1/4] Creando entorno virtual...
if not exist venv %PY% -m venv venv
if errorlevel 1 goto error

echo [2/4] Instalando dependencias...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements-local.txt
if errorlevel 1 goto error

echo [3/4] Instalando Chromium para Playwright...
python -m playwright install chromium
if errorlevel 1 goto error

echo [4/4] Creando carpeta C:\tmp para capturas...
if not exist C:\tmp mkdir C:\tmp

echo.
echo === Listo. Ahora corre 3_probar_conexiones.bat ===
pause
exit /b

:error
echo.
echo *** Hubo un error. Copia lo que aparece arriba y mandaselo a Claude. ***
pause
