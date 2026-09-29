"""
FUGU APP SCREENSHOT MODULE
fugu_screenshot.py

Takes screenshots of payment information from Fugu app.
"""

from playwright.sync_api import sync_playwright
import os
import json
import urllib.request

COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fugu_cookies.json")
CDP_URL = "http://127.0.0.1:9222"
FUGU_URL = "https://app.fugu-it.com"


def load_fugu_cookies():
    with open(COOKIES_FILE, 'r') as f:
        return json.load(f)


def get_chrome_user_agent():
    """User-Agent of the Chrome running on port 9222 (so Cloudflare sees the same browser)."""
    try:
        with urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=3) as r:
            ua = json.load(r).get("User-Agent")
        return ua.replace("HeadlessChrome", "Chrome") if ua else None
    except Exception:
        return None


def get_live_fugu_cookies(p):
    """
    Read the FUGU session cookies straight from the Chrome running on port 9222
    (the one already logged in to Shopify / FUGU). Only reads cookies - does not
    open tabs or windows. Saves them to fugu_cookies.json as a backup.
    Returns None if that Chrome isn't running or isn't logged in to FUGU.
    """
    try:
        browser = p.chromium.connect_over_cdp(CDP_URL, timeout=5000)
        cookies = browser.contexts[0].cookies(FUGU_URL)
    except Exception as e:
        print(f"Could not read cookies from Chrome on 9222: {e}")
        return None
    if not any(c.get("name") == "session" for c in cookies):
        print("Chrome on 9222 is not logged in to app.fugu-it.com")
        return None
    try:
        with open(COOKIES_FILE, 'w') as f:
            json.dump(cookies, f, indent=2)
    except Exception:
        pass
    print(f"Using {len(cookies)} live FUGU cookies from Chrome")
    return cookies


def screenshot_payment_info(payment_id, tenant_id, output_dir="/tmp"):
    """
    Take a screenshot of payment information from Fugu app.

    Args:
        payment_id: The payment ID
        tenant_id: The tenant ID
        output_dir: Directory to save screenshot

    Returns:
        Path to screenshot file, or None if failed
    """
    if not payment_id or not tenant_id:
        print("Missing payment_id or tenant_id")
        return None

    # Build URL
    url = f"https://app.fugu-it.com/transactions/{payment_id}?embed=1&shopName=suleyman@fugu-it.com&apiKey=635241.Sl&tid={tenant_id}"

    output_path = os.path.join(output_dir, f"fugu_payment_{payment_id[:8]}.png")

    print(f"Loading Fugu: {url[:80]}...")

    try:
        with sync_playwright() as p:
            # Prefer fresh cookies from the logged-in Chrome; fall back to the file
            cookies = get_live_fugu_cookies(p) or load_fugu_cookies()
            user_agent = get_chrome_user_agent()

            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=user_agent) if user_agent else browser.new_context()

            # Add cookies
            context.add_cookies(cookies)

            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)

            # Wait out a Cloudflare challenge if one appears
            for _ in range(8):
                content = page.content().lower()
                if "just a moment" in content or "checking your browser" in content:
                    print("Cloudflare challenge, waiting...")
                    page.wait_for_timeout(2000)
                else:
                    break
            else:
                print("ERROR: Blocked by Cloudflare challenge")
                browser.close()
                return None

            # Check if logged in
            if "login" in page.url.lower():
                print("ERROR: Not logged in to FUGU - log in to app.fugu-it.com in the Chrome on port 9222")
                browser.close()
                return None

            # Hide elements outside our range and take screenshot
            result = page.evaluate("""
                () => {
                    // Find the Payment Information card
                    const cards = document.querySelectorAll('.card');
                    let paymentCard = null;

                    for (const card of cards) {
                        const header = card.querySelector('.card-header');
                        if (header && header.textContent.includes('Payment Information')) {
                            paymentCard = card;
                            break;
                        }
                    }

                    if (!paymentCard) return { error: 'Payment card not found' };

                    // Hide the card header
                    const cardHeader = paymentCard.querySelector('.card-header');
                    if (cardHeader) cardHeader.style.display = 'none';

                    const items = paymentCard.querySelectorAll('.list-group-item');
                    let startIdx = -1;
                    let endIdx = -1;

                    items.forEach((item, idx) => {
                        const text = item.textContent;
                        if (text.includes('Cardholder Name') && startIdx === -1) startIdx = idx;
                        if (text.includes('IP Location')) endIdx = idx;
                    });

                    if (startIdx === -1 || endIdx === -1) {
                        return { error: 'Start or end not found', startIdx, endIdx };
                    }

                    // Hide items outside our range
                    items.forEach((item, idx) => {
                        if (idx < startIdx || idx > endIdx) {
                            item.style.display = 'none';
                        }
                    });

                    return { success: true };
                }
            """)

            if result and result.get('success'):
                page.wait_for_timeout(500)

                # Screenshot the Payment Information card
                payment_card = page.locator("div.card-header:has-text('Payment Information')").locator("..").first
                payment_card.screenshot(path=output_path)
                print(f"Screenshot saved: {output_path}")

                browser.close()
                return output_path
            else:
                print(f"Error: {result}")
                browser.close()
                return None

    except Exception as e:
        print(f"Fugu screenshot error: {e}")
        return None


# Quick test
if __name__ == "__main__":
    # Test with sample IDs
    payment_id = input("Payment ID: ").strip()
    tenant_id = input("Tenant ID: ").strip()

    result = screenshot_payment_info(payment_id, tenant_id, output_dir=".")
    if result:
        print(f"\nSuccess! Screenshot: {result}")
    else:
        print("\nFailed to capture screenshot")