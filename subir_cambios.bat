@echo off
chcp 65001 >nul
cd /d "%~dp0"
set BRANCH=fix/fugu-cookies-desde-chrome
echo === Subiendo cambios a GitHub (rama %BRANCH%) ===
echo.
git checkout -B %BRANCH%
if errorlevel 1 goto error
git add fugu_screenshot.py
git commit -m "FUGU screenshot: read live session cookies from Chrome on 9222 instead of pasted cookies; match Chrome user agent and wait out Cloudflare challenge"
git add requirements-local.txt probar_conexiones.py 1_instalar.bat 2_abrir_chrome_shopify.bat 3_probar_conexiones.bat 4_iniciar_app.bat subir_cambios.bat
git commit -m "Add Windows local setup scripts and connection diagnostic"
git push -u origin %BRANCH%
if errorlevel 1 goto error
echo.
echo === Listo, cambios subidos. Avisale a Claude. ===
pause
exit /b

:error
echo.
echo *** Hubo un error. Saca captura de esta ventana y mandasela a Claude. ***
pause
