"""
Shopify Order Screenshot
Uses an existing Playwright CDP context so order and tracking screenshots
share the same Chrome session (single CDP connection, no parallel conflicts).
"""

import os
from playwright.sync_api import sync_playwright


def screenshot_with_context(context, order_url, output_path):
    """Take order screenshot using an already-open Playwright context."""
    page = context.new_page()
    print(f"Loading: {order_url}")
    page.goto(order_url, wait_until="domcontentloaded", timeout=60000)

    # Wait out any Cloudflare challenge
    for _ in range(8):
        content = page.content().lower()
        if "checking your browser" in content or "just a moment" in content:
            print("Cloudflare challenge, waiting...")
            page.wait_for_timeout(2000)
        else:
            break

    page.wait_for_timeout(4000)

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
    url = f"https://{store_url}/admin/orders?query={order_number}"
    output_path = os.path.join(output_dir, f"shopify_order_{order_number}.png")
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            return screenshot_with_context(browser.contexts[0], url, output_path)
    except Exception as e:
        print(f"Order screenshot error: {e}")
        return None


def screenshot_shopify_order_by_url(external_reference, order_number, output_dir="/tmp", tenant_id=None):
    if not external_reference:
        return None
    order_number = str(order_number).replace('#', '')
    output_path = os.path.join(output_dir, f"shopify_order_{order_number}.png")
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            return screenshot_with_context(browser.contexts[0], external_reference, output_path)
    except Exception as e:
        print(f"Order screenshot error: {e}")
        return None


def get_order_proof(store_url, order_number, output_dir="/tmp"):
    path = screenshot_shopify_order(store_url, order_number, output_dir)
    if path:
        return {"screenshot_path": path, "store_url": store_url, "order_number": order_number}
    return None
