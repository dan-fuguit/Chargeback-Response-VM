from playwright.sync_api import sync_playwright
import os
import json

COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.json")

def load_cookies():
    with open(COOKIES_FILE, 'r') as f:
        cookies = json.load(f)
    # Convert to Playwright format
    for c in cookies:
        if 'sameSite' in c:
            c['sameSite'] = c['sameSite'].capitalize()
            if c['sameSite'] not in ['Strict', 'Lax', 'None']:
                c['sameSite'] = 'Lax'
        if 'expirationDate' in c:
            c['expires'] = c.pop('expirationDate')
    return cookies

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
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(viewport={'width': 1280, 'height': 900})
            page = context.new_page()
            page.context.add_cookies(load_cookies())

            url = f"https://{store_url}/admin/orders?query={order_number}"
            print(f"Loading: {url}")
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2000)

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
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(viewport={'width': 1280, 'height': 900})
            page = context.new_page()
            page.context.add_cookies(load_cookies())

            print(f"Loading: {external_reference}")
            page.goto(external_reference, wait_until="networkidle", timeout=60000)
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
