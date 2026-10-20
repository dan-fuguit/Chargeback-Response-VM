"""
Keeps the Shopify admin session alive in the VM's Chromium (CDP on :9222)
and detects when Shopify asks to log in again (2FA).

Every KEEPALIVE_MINUTES it opens admin.shopify.com in a new tab, checks where
it lands and closes the tab. If it lands on a login page:
  - STATUS['logged_in'] = False (web_app shows a red banner)
  - posts to SLACK_WEBHOOK_URL (env var or slack_webhook.txt), once per outage.
"""
import os
import threading
import time
import datetime
import requests
import base64
import hashlib
import hmac
import struct

KEEPALIVE_MINUTES = int(os.environ.get('KEEPALIVE_MINUTES', '20'))
CDP_URL = "http://127.0.0.1:9222"
LOGIN_MARKERS = ('/challenges/', 'user_verification', 'accounts.shopify.com', '/login', '/lookup', '/two-factor', '/verify')

TOTP_FILE = os.path.expanduser('~/.shopify_totp')  # one line: the authenticator secret (never in git)

STATUS = {'logged_in': None, 'checked_at': None, 'error': None}
_alert_sent = False


def _slack_url():
    url = os.environ.get('SLACK_WEBHOOK_URL', '').strip()
    if not url:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'slack_webhook.txt')
        if os.path.exists(path):
            url = open(path).read().strip()
    return url


def _notify(text):
    url = _slack_url()
    if not url:
        return
    try:
        requests.post(url, json={'text': text}, timeout=10)
    except Exception as e:
        print(f"[keepalive] Slack error: {e}")



def _totp_code():
    """6-digit authenticator code from the secret in ~/.shopify_totp (None if missing)."""
    try:
        secret = open(TOTP_FILE).read().strip().replace(' ', '').upper()
    except Exception:
        return None
    if not secret:
        return None
    key = base64.b32decode(secret + '=' * (-len(secret) % 8))
    counter = int(time.time()) // 30
    digest = hmac.new(key, struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1000000
    return f"{code:06d}"


def _auto_verify(page):
    """If Shopify shows the 'verify your account' (2FA) screen, type the code. Returns True if it passed."""
    if '/challenges/' not in page.url and 'user_verification' not in page.url:
        return False
    if int(time.time()) % 30 > 25:   # avoid a code that is about to expire
        time.sleep(6)
    code = _totp_code()
    if not code:
        print("[keepalive] 2FA screen but no ~/.shopify_totp secret")
        return False
    try:
        box = page.locator('input:visible').first
        box.click(timeout=10000)
        page.keyboard.type(code, delay=120)
        page.wait_for_timeout(1500)
        if '/challenges/' in page.url:
            page.keyboard.press('Enter')
        page.wait_for_timeout(6000)
    except Exception as e:
        print(f"[keepalive] auto-verify error: {e}")
        return False
    ok = '/challenges/' not in page.url and 'user_verification' not in page.url
    print(f"[keepalive] auto-verify {'OK' if ok else 'FAILED'}")
    return ok


def check_once():
    global _alert_sent
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            context = browser.contexts[0]
            page = context.new_page()
            try:
                page.goto("https://admin.shopify.com/", wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(5000)
                if _auto_verify(page):
                    page.goto("https://admin.shopify.com/", wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(4000)
                url = page.url
            finally:
                page.close()
        logged_in = not any(m in url for m in LOGIN_MARKERS)
        STATUS.update(logged_in=logged_in, checked_at=datetime.datetime.now(), error=None)
        print(f"[keepalive] Shopify {'OK' if logged_in else 'NEEDS LOGIN'} ({url[:80]})")
        if not logged_in and not _alert_sent:
            _notify(":warning: *Chargeback Responder*: Shopify pide iniciar sesion de nuevo (codigo 2FA). "
                    "Entra a la VM (10.80.4.4), abri Chromium y logueate en Shopify.")
            _alert_sent = True
        if logged_in and _alert_sent:
            _notify(":white_check_mark: *Chargeback Responder*: sesion de Shopify recuperada.")
            _alert_sent = False
    except Exception as e:
        STATUS.update(checked_at=datetime.datetime.now(), error=str(e))
        print(f"[keepalive] error: {e}")


def _loop():
    time.sleep(30)
    while True:
        check_once()
        time.sleep(KEEPALIVE_MINUTES * 60)


def start():
    t = threading.Thread(target=_loop, daemon=True, name='shopify-keepalive')
    t.start()
