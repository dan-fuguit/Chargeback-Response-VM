from playwright.sync_api import sync_playwright
import os
import json

COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.json")


def load_cookies():
    with open(COOKIES_FILE, 'r') as f:
        raw = json.load(f)
    cleaned = []
    for c in raw:
        entry = {
            'name': c['name'],
            'value': c['value'],
            'domain': c['domain'],
            'path': c.get('path', '/'),
        }
        if 'sameSite' in c:
            s = c['sameSite'].capitalize()
            entry['sameSite'] = s if s in ['Strict', 'Lax', 'None'] else 'Lax'
        if 'expirationDate' in c:
            entry['expires'] = c['expirationDate']
        if 'httpOnly' in c:
            entry['httpOnly'] = c['httpOnly']
        if 'secure' in c:
            entry['secure'] = c['secure']
        cleaned.append(entry)
    return cleaned


def _new_context(p):
    browser = p.chromium.launch(
        headless=True,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-dev-shm-usage',
        ]
    )
    context = browser.new_context(
        viewport={'width': 1280, 'height': 900},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    )
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    context.add_cookies(load_cookies())
    return browser, context


def _wait_past_cloudflare(page, timeout_ms=15000):
    elapsed = 0
    while elapsed < timeout_ms:
        content = page.content().lower()
        if 'checking your browser' in content or 'just a moment' in content:
            page.wait_for_timeout(2000)
            elapsed += 2000
            continue
        if 'sign in' in page.url.lower() or 'login' in page.url.lower():
            print("ERROR: Shopify session expired - update cookies via /shopify-cookies")
            return False
        return True
    print("Cloudflare challenge did not clear in time")
    return False


def do_scroll(page):
    selectors = [
        '[class*="_OrderDetailsMainColumn_"]',
        '[class*="OrderDetailsMainColumn"]',
        'text="Fulfilled"',
        'text="Unfulfilled"',
    ]
    for selector in selectors:
        try:
            el = page.locator(selector).first
            if el.is_visible(timeout=1000):
                el.scroll_into_view_if_needed()
                return True
        except:
            continue
    return False


def screenshot_shopify_order(store_url, order_number, output_dir="/tmp"):
    if not store_url.endswith('.myshopify.com'):
        store_url = f"{store_url}.myshopify.com"
    order_number = str(order_number).replace('#', '')
    output_path = os.path.join(output_dir, f"shopify_order_{order_number}.png")

    try:
        with sync_playwright() as p:
            browser, context = _new_context(p)
            page = context.new_page()

            url = f"https://{store_url}/admin/orders?query={order_number}"
            print(f"Loading: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)

            if not _wait_past_cloudflare(page):
                browser.close()
                return None
            page.wait_for_timeout(3000)

            try:
                order_link = page.locator(f'a:has-text("#{order_number}")').first
                order_link.click()
                page.wait_for_timeout(3000)
            except:
                try:
                    page.locator('table tbody tr').first.click()
                    page.wait_for_timeout(3000)
                except:
                    browser.close()
                    return None

            do_scroll(page)
            page.wait_for_timeout(1000)
            page.screenshot(path=output_path, full_page=False)
            print(f"Screenshot saved: {output_path}")
            browser.close()
            return output_path
    except Exception as e:
        print(f"Error: {e}")
        return None


def screenshot_shopify_order_by_url(external_reference, order_number, output_dir="/tmp"):
    if not external_reference:
        return None
    order_number = str(order_number).replace('#', '')
    output_path = os.path.join(output_dir, f"shopify_order_{order_number}.png")

    try:
        with sync_playwright() as p:
            browser, context = _new_context(p)
            page = context.new_page()

            print(f"Loading: {external_reference}")
            page.goto(external_reference, wait_until="domcontentloaded", timeout=60000)

            if not _wait_past_cloudflare(page):
                browser.close()
                return None
            page.wait_for_timeout(3000)

            do_scroll(page)
            page.wait_for_timeout(1000)
            page.screenshot(path=output_path, full_page=False)
            print(f"Screenshot saved: {output_path}")
            browser.close()
            return output_path
    except Exception as e:
        print(f"Error: {e}")
        return None


def get_order_proof(store_url, order_number, output_dir="/tmp"):
    path = screenshot_shopify_order(store_url, order_number, output_dir)
    if path:
        return {"screenshot_path": path, "store_url": store_url, "order_number": order_number}
    return None
