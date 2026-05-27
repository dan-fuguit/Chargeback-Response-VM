"""
Shopify Order Screenshot
Connects to existing Chrome via CDP (same as shopify_tracking.py) and
opens a tab to the Shopify admin order page.
"""

import os
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def _screenshot_order_page(url, output_path):
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            print("Connected to existing Chrome")
        except Exception as e:
            print(f"Could not connect to Chrome on port 9222: {e}")
            raise

        context = browser.contexts[0]
        page = context.new_page()

        print(f"Loading: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Wait out any Cloudflare challenge
        for _ in range(8):
            content = page.content().lower()
            if "checking your browser" in content or "just a moment" in content:
                print("Cloudflare challenge detected, waiting...")
                page.wait_for_timeout(2000)
            else:
                break

        page.wait_for_timeout(4000)

        # Scroll order details into view if present
        for selector in [
            '[class*="_OrderDetailsMainColumn_"]',
            '[class*="OrderDetailsMainColumn"]',
            'text="Fulfilled"',
            'text="Unfulfilled"',
            'text="Paid"',
        ]:
            try:
                el = page.locator(selector).first
                if el.is_visible(timeout=1000):
                    el.scroll_into_view_if_needed()
                    break
            except:
                continue

        page.wait_for_timeout(1000)
        page.screenshot(path=output_path, full_page=False)
        print(f"Screenshot saved: {output_path}")
        page.close()
        return output_path


def screenshot_shopify_order(store_url, order_number, output_dir="/tmp", tenant_id=None):
    if not store_url.endswith('.myshopify.com'):
        store_url = f"{store_url}.myshopify.com"
    order_number = str(order_number).replace('#', '')
    output_path = os.path.join(output_dir, f"shopify_order_{order_number}.png")

    url = f"https://{store_url}/admin/orders?query={order_number}"
    try:
        return _screenshot_order_page(url, output_path)
    except Exception as e:
        print(f"Order screenshot error: {e}")
        return None


def screenshot_shopify_order_by_url(external_reference, order_number, output_dir="/tmp", tenant_id=None):
    if not external_reference:
        return None
    order_number = str(order_number).replace('#', '')
    output_path = os.path.join(output_dir, f"shopify_order_{order_number}.png")

    try:
        return _screenshot_order_page(external_reference, output_path)
    except Exception as e:
        print(f"Order screenshot error: {e}")
        return None


def get_order_proof(store_url, order_number, output_dir="/tmp"):
    path = screenshot_shopify_order(store_url, order_number, output_dir)
    if path:
        return {"screenshot_path": path, "store_url": store_url, "order_number": order_number}
    return None
