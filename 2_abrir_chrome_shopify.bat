@echo off
REM Abre un Chrome aparte (perfil propio) con el puerto 9222 que usa el programa
REM para las capturas de Shopify. Inicia sesion en el admin de Shopify en esta ventana
REM y dejala abierta mientras usas la app.
set CHROME="C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist %CHROME% set CHROME="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist C:\chrome-cb mkdir C:\chrome-cb
start "" %CHROME% --remote-debugging-port=9222 --user-data-dir=C:\chrome-cb https://admin.shopify.com
