"""
Diagnostico: verifica que esta PC llega a todo lo que necesita el Chargeback Responder.
No imprime contraseñas ni cookies.
"""
import os, sys, json, socket
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OK, FAIL, WARN = "[OK]  ", "[FALLA]", "[AVISO]"
results = []

def check(name, fn):
    try:
        msg = fn()
        print(f"{OK} {name}" + (f" - {msg}" if msg else ""))
        results.append(True)
    except Exception as e:
        print(f"{FAIL} {name} - {type(e).__name__}: {e}")
        results.append(False)

print("=== Probando conexiones ===\n")

def py_deps():
    import flask, playwright, docx, reportlab, mysql.connector, redis, requests, PIL  # noqa
    return f"Python {sys.version.split()[0]}"
check("Dependencias de Python", py_deps)

def tmp_dir():
    path = "/tmp"
    os.makedirs(path, exist_ok=True)
    test = os.path.join(path, "_cb_test.txt")
    open(test, "w").write("ok"); os.remove(test)
    return os.path.abspath(path)
check("Carpeta de capturas (/tmp)", tmp_dir)

def mysql_db():
    import mysql.connector
    from chargeback_main import DB_CONFIG
    conn = mysql.connector.connect(**DB_CONFIG, connection_timeout=10)
    cur = conn.cursor(); cur.execute("SELECT 1"); cur.fetchall(); conn.close()
    return DB_CONFIG["host"]
check("Base de datos MySQL (Azure)", mysql_db)

def redis_db():
    import redis
    from public_records import REDIS_CONFIG
    r = redis.Redis(**REDIS_CONFIG, socket_timeout=10)
    r.ping()
check("Redis (public records)", redis_db)

def n8n():
    host = "dan-fugu.app.n8n.cloud"
    socket.create_connection((host, 443), timeout=10).close()
    return "alcanzable (no se envio nada)"
check("n8n", n8n)

def chrome_cdp():
    import urllib.request
    data = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5))
    return data.get("Browser", "")
check("Chrome con puerto 9222 (capturas Shopify)", chrome_cdp)

def fugu_cookies():
    cookies = json.load(open("fugu_cookies.json"))
    names = {c["name"] for c in cookies}
    if "session" not in names:
        raise ValueError("falta la cookie 'session'")
    return f"{len(cookies)} cookies"
check("Cookies de FUGU (archivo)", fugu_cookies)

def fugu_app():
    from playwright.sync_api import sync_playwright
    from fugu_screenshot import load_fugu_cookies
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(); ctx.add_cookies(load_fugu_cookies())
        page = ctx.new_page()
        page.goto("https://app.fugu-it.com/", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(4000)
        html, url = page.content().lower(), page.url
        b.close()
    if "just a moment" in html or "checking your browser" in html or "challenge-platform" in html:
        raise RuntimeError("Cloudflare bloqueo el navegador automatico")
    if "login" in url.lower():
        raise RuntimeError("cookies vencidas (redirigio a login)")
    return "cargo sin desafio de Cloudflare"
check("App de FUGU con navegador automatico", fugu_app)

print(f"\n=== {sum(results)}/{len(results)} OK ===")
if not all(results):
    print("Copia este resultado y mandaselo a Claude.")
