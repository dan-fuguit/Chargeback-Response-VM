"""
FUGU card screenshots taken from the FUGU app embedded in Shopify admin.

Uses the Chrome already running on port 9222 (logged in to Shopify), so it
needs no FUGU cookies and never hits app.fugu-it.com's login / Cloudflare.
Sections are located by their labels inside the embedded app iframe.
"""
import os

FUGU_APP_HANDLE = "fugu-sensing-post-payment-risk-1"

IDENTITY_LABELS = [
    "Billing Name", "Shipping Name", "Shipping Phone", "Phone Number", "Email",
    "Billing Address", "Shipping Address", "IP Address", "Caller ID Verification",
]
AVS_LABELS = ["Credit Card Number", "Card Holder", "Currency", "AVS"]

_FIND_ROWS_JS = """
(labels) => {
  const norm = s => (s || '').replace(/\\s+/g, ' ').trim().replace(/:$/, '').toLowerCase();
  const all = [...document.querySelectorAll('body *')];
  const out = [];
  for (const lab of labels) {
    const want = lab.toLowerCase();
    let el = all.find(e => e.children.length === 0 && norm(e.textContent) === want);
    if (!el) el = all.find(e => e.childElementCount <= 4 && norm(e.textContent).startsWith(want + ':')
                             && e.textContent.length < 200);
    if (!el) continue;
    let row = el;
    while (row.parentElement) {
      const r = row.parentElement.getBoundingClientRect();
      if (r.height > 60 || r.width > window.innerWidth * 0.45) break;
      row = row.parentElement;
    }
    row.scrollIntoView({block: 'nearest'});
    const r = row.getBoundingClientRect();
    if (r.width && r.height) out.push({x: r.left, y: r.top, w: r.width, h: r.height});
  }
  return out;
}
"""


def _find_fugu_frame(page, timeout_ms=30000):
    waited = 0
    while waited < timeout_ms:
        for fr in page.frames:
            if "fugu-it.com" in (fr.url or ""):
                return fr
        page.wait_for_timeout(1000)
        waited += 1000
    return None


def _capture_labels(page, frame, labels, output_path, pad=10):
    rows = frame.evaluate(_FIND_ROWS_JS, labels)
    if len(rows) < max(2, len(labels) // 2):
        print(f"  FUGU: only found {len(rows)}/{len(labels)} fields for {os.path.basename(output_path)}")
        if not rows:
            return None
    fb = frame.frame_element().bounding_box()
    x0 = min(r["x"] for r in rows); y0 = min(r["y"] for r in rows)
    x1 = max(r["x"] + r["w"] for r in rows); y1 = max(r["y"] + r["h"] for r in rows)
    clip = {
        "x": max(fb["x"] + x0 - pad, 0), "y": max(fb["y"] + y0 - pad, 0),
        "width": (x1 - x0) + 2 * pad, "height": (y1 - y0) + 2 * pad,
    }
    page.screenshot(path=output_path, clip=clip)
    return output_path


def capture_fugu_sections(context, shop_name, payment_id, output_dir="/tmp"):
    """Returns {'identity_screenshot': path, 'avs_screenshot': path} (keys only on success)."""
    results = {}
    if not shop_name or not payment_id:
        return results
    shop = shop_name.replace(".myshopify.com", "")
    url = f"https://admin.shopify.com/store/{shop}/apps/{FUGU_APP_HANDLE}/payments/{payment_id}"
    page = context.new_page()
    try:
        page.set_viewport_size({"width": 1600, "height": 1100})
        print(f"Loading FUGU in Shopify: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        frame = _find_fugu_frame(page)
        if not frame:
            print("  FUGU: embedded app frame not found (is Chrome logged in to this store?)")
            return results
        try:
            frame.wait_for_selector("text=Payment Information", timeout=30000)
        except Exception:
            print("  FUGU: 'Payment Information' not found in app")
            return results
        page.wait_for_timeout(2500)

        pid = payment_id[:8]
        for key, labels, name in (
            ("identity_screenshot", IDENTITY_LABELS, f"fugu_identity_{pid}.png"),
            ("avs_screenshot", AVS_LABELS, f"fugu_avs_{pid}.png"),
        ):
            try:
                path = _capture_labels(page, frame, labels, os.path.join(output_dir, name))
                if path:
                    results[key] = path
                    print(f"  ✓ FUGU {key}")
            except Exception as e:
                print(f"  FUGU {key} error: {e}")
    finally:
        page.close()
    return results
