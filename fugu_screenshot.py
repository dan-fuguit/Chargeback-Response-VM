"""
FUGU APP SCREENSHOT MODULE
fugu_screenshot.py

Takes screenshots of payment information from Fugu app.
"""

from playwright.sync_api import sync_playwright
import os
import json

COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fugu_cookies.json")


def load_fugu_cookies():
    with open(COOKIES_FILE, 'r') as f:
        return json.load(f)


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
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()

            # Add cookies
            context.add_cookies(load_fugu_cookies())

            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)

            # Check if logged in
            if "login" in page.url.lower():
                print("ERROR: Cookies expired - update via the web app /cookies page")
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