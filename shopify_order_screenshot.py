"""
Shopify Order Details - API + Image Generation
Fetches order data via Shopify Admin API and renders a styled image with Pillow.
"""

import os
import requests
import mysql.connector
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

DB_CONFIG = {
    'host': 'fugu-sql-prod-rep.mysql.database.azure.com',
    'database': 'fuguprod',
    'user': 'geckoboard',
    'password': 'UrxP3FmJ+z1bF1Xjs<*%'
}


def _get_credentials(shop_name=None, tenant_id=None):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor(dictionary=True)
        if tenant_id:
            cur.execute(
                "SELECT shopname, accesstoken FROM shopifyintegration WHERE tenantid = %s LIMIT 1",
                (tenant_id,),
            )
        elif shop_name:
            name = shop_name.replace('.myshopify.com', '').strip()
            cur.execute(
                "SELECT shopname, accesstoken FROM shopifyintegration WHERE shopname LIKE %s LIMIT 1",
                (f"%{name}%",),
            )
        else:
            return None
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row
    except Exception as e:
        print(f"DB error getting Shopify credentials: {e}")
        return None


def _fetch_order(shop_url, token, order_reference):
    if not shop_url.endswith('.myshopify.com'):
        shop_url += '.myshopify.com'
    headers = {"X-Shopify-Access-Token": token}

    reference = str(order_reference).replace('#', '')
    for ref in (reference, f"#{reference}"):
        try:
            r = requests.get(
                f"https://{shop_url}/admin/api/2024-01/orders.json",
                headers=headers,
                params={"name": ref, "status": "any"},
                timeout=30,
            )
            if r.status_code == 200:
                orders = r.json().get("orders", [])
                if orders:
                    return orders[0]
        except Exception as e:
            print(f"API error: {e}")
    return None


def _fetch_order_by_id(shop_url, token, order_id):
    if not shop_url.endswith('.myshopify.com'):
        shop_url += '.myshopify.com'
    headers = {"X-Shopify-Access-Token": token}
    try:
        r = requests.get(
            f"https://{shop_url}/admin/api/2024-01/orders/{order_id}.json",
            headers=headers,
            timeout=30,
        )
        if r.status_code == 200:
            return r.json().get("order")
    except Exception as e:
        print(f"API error: {e}")
    return None


def _try_load_font(size):
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _try_load_bold_font(size):
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return _try_load_font(size)


def _format_date(date_str):
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime("%B %d, %Y at %I:%M %p")
    except:
        return date_str


def _format_money(amount_str):
    try:
        return f"${float(amount_str):,.2f}"
    except:
        return f"${amount_str}"


def _format_address(addr):
    if not addr:
        return []
    lines = []
    name = addr.get('name') or f"{addr.get('first_name', '')} {addr.get('last_name', '')}".strip()
    if name:
        lines.append(name)
    if addr.get('address1'):
        lines.append(addr['address1'])
    if addr.get('address2'):
        lines.append(addr['address2'])
    city_line = ', '.join(filter(None, [addr.get('city'), addr.get('province_code')]))
    if addr.get('zip'):
        city_line += f" {addr['zip']}"
    if city_line:
        lines.append(city_line)
    if addr.get('country'):
        lines.append(addr['country'])
    return lines


def render_order_image(order, output_path):
    W = 900
    PAD = 30
    COL_W = W - 2 * PAD

    WHITE = (255, 255, 255)
    BG = (250, 251, 252)
    DARK = (26, 32, 44)
    GRAY = (74, 85, 104)
    LIGHT_GRAY = (160, 174, 192)
    BORDER = (226, 232, 240)
    GREEN = (39, 103, 73)
    GREEN_BG = (240, 255, 244)
    BLUE = (44, 82, 130)
    HEADER_BG = (247, 250, 252)

    font_sm = _try_load_font(13)
    font_md = _try_load_font(15)
    font_lg = _try_load_bold_font(17)
    font_xl = _try_load_bold_font(22)
    font_label = _try_load_bold_font(13)

    order_name = order.get('name', '')
    created = _format_date(order.get('created_at'))
    financial = (order.get('financial_status') or '').capitalize()
    fulfillment = (order.get('fulfillment_status') or 'Unfulfilled').capitalize()
    currency = order.get('currency', 'USD')

    customer = order.get('customer', {})
    cust_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or "Guest"
    cust_email = customer.get('email', '')

    line_items = order.get('line_items', [])
    shipping_addr = _format_address(order.get('shipping_address'))
    billing_addr = _format_address(order.get('billing_address'))

    # --- Measure height ---
    y = PAD
    y += 60  # header
    y += 35  # date line
    y += 20  # spacing
    y += 40  # customer section header
    y += 25  # customer name/email
    y += 25  # spacing
    y += 30  # items header
    y += len(line_items) * 28  # items
    y += 15  # spacing
    y += 4 * 24  # financial summary (subtotal, shipping, tax, total)
    y += 20  # spacing
    y += 30  # address header
    y += max(len(shipping_addr), len(billing_addr), 1) * 20 + 10
    y += PAD + 10

    H = max(y, 400)

    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)

    # White card background with border
    draw.rounded_rectangle([PAD - 10, PAD - 10, W - PAD + 10, H - PAD + 10],
                           radius=8, fill=WHITE, outline=BORDER, width=1)

    y = PAD + 5

    # --- HEADER ---
    draw.rounded_rectangle([PAD, y, W - PAD, y + 50], radius=6, fill=HEADER_BG, outline=BORDER)
    draw.text((PAD + 15, y + 12), f"Order {order_name}", font=font_xl, fill=DARK)

    # Status badges
    badge_x = W - PAD - 15

    def _draw_badge(x_right, y_pos, text, bg_color, text_color):
        bbox = draw.textbbox((0, 0), text, font=font_label)
        tw = bbox[2] - bbox[0]
        bx = x_right - tw - 16
        draw.rounded_rectangle([bx, y_pos + 2, x_right, y_pos + 22], radius=4, fill=bg_color)
        draw.text((bx + 8, y_pos + 4), text, font=font_label, fill=text_color)
        return bx - 10

    if fulfillment:
        f_bg = GREEN_BG if fulfillment.lower() == 'fulfilled' else (255, 250, 230)
        f_fg = GREEN if fulfillment.lower() == 'fulfilled' else (146, 119, 36)
        badge_x = _draw_badge(badge_x, y + 14, fulfillment, f_bg, f_fg)

    if financial:
        p_bg = GREEN_BG if financial.lower() == 'paid' else (255, 245, 245)
        p_fg = GREEN if financial.lower() == 'paid' else (155, 44, 44)
        _draw_badge(badge_x, y + 14, financial, p_bg, p_fg)

    y += 55

    # Date
    draw.text((PAD + 15, y), created, font=font_sm, fill=GRAY)
    y += 30

    # --- DIVIDER ---
    draw.line([(PAD, y), (W - PAD, y)], fill=BORDER, width=1)
    y += 15

    # --- CUSTOMER ---
    draw.text((PAD + 15, y), "CUSTOMER", font=font_label, fill=LIGHT_GRAY)
    y += 22
    draw.text((PAD + 15, y), cust_name, font=font_lg, fill=DARK)
    if cust_email:
        name_bbox = draw.textbbox((0, 0), cust_name, font=font_lg)
        name_w = name_bbox[2] - name_bbox[0]
        draw.text((PAD + 15 + name_w + 12, y + 2), cust_email, font=font_sm, fill=GRAY)
    y += 28

    # --- DIVIDER ---
    draw.line([(PAD, y), (W - PAD, y)], fill=BORDER, width=1)
    y += 15

    # --- LINE ITEMS ---
    draw.text((PAD + 15, y), "ITEMS", font=font_label, fill=LIGHT_GRAY)
    y += 24

    for item in line_items:
        name = item.get('title', 'Item')
        qty = item.get('quantity', 1)
        price = _format_money(item.get('price', '0'))
        variant = item.get('variant_title')
        label = f"{name}"
        if variant:
            label += f" - {variant}"

        draw.text((PAD + 15, y), label, font=font_md, fill=DARK)
        qty_text = f"x {qty}"
        draw.text((W - PAD - 200, y), qty_text, font=font_md, fill=GRAY)
        price_bbox = draw.textbbox((0, 0), price, font=font_md)
        price_w = price_bbox[2] - price_bbox[0]
        draw.text((W - PAD - 15 - price_w, y), price, font=font_md, fill=DARK)
        y += 28

    y += 5
    draw.line([(PAD, y), (W - PAD, y)], fill=BORDER, width=1)
    y += 12

    # --- FINANCIAL SUMMARY ---
    summary_rows = []
    subtotal = order.get('subtotal_price')
    if subtotal:
        summary_rows.append(("Subtotal", _format_money(subtotal)))

    shipping_lines = order.get('shipping_lines', [])
    if shipping_lines:
        ship_total = sum(float(s.get('price', 0)) for s in shipping_lines)
        summary_rows.append(("Shipping", _format_money(str(ship_total))))

    tax = order.get('total_tax')
    if tax and float(tax) > 0:
        summary_rows.append(("Tax", _format_money(tax)))

    total = order.get('total_price')
    if total:
        summary_rows.append(("Total", f"{_format_money(total)} {currency}"))

    for label, value in summary_rows:
        is_total = label == "Total"
        lfont = font_lg if is_total else font_md
        vfont = font_lg if is_total else font_md
        lcolor = DARK if is_total else GRAY
        vcolor = DARK

        draw.text((W - PAD - 280, y), label, font=lfont, fill=lcolor)
        vbbox = draw.textbbox((0, 0), value, font=vfont)
        vw = vbbox[2] - vbbox[0]
        draw.text((W - PAD - 15 - vw, y), value, font=vfont, fill=vcolor)
        y += 24

    y += 8
    draw.line([(PAD, y), (W - PAD, y)], fill=BORDER, width=1)
    y += 15

    # --- ADDRESSES ---
    mid = W // 2
    if shipping_addr or billing_addr:
        if shipping_addr:
            draw.text((PAD + 15, y), "SHIPPING ADDRESS", font=font_label, fill=LIGHT_GRAY)
        if billing_addr:
            draw.text((mid + 10, y), "BILLING ADDRESS", font=font_label, fill=LIGHT_GRAY)
        y += 22

        max_lines = max(len(shipping_addr), len(billing_addr))
        for i in range(max_lines):
            if i < len(shipping_addr):
                f = font_lg if i == 0 else font_sm
                draw.text((PAD + 15, y), shipping_addr[i], font=f, fill=DARK if i == 0 else GRAY)
            if i < len(billing_addr):
                f = font_lg if i == 0 else font_sm
                draw.text((mid + 10, y), billing_addr[i], font=f, fill=DARK if i == 0 else GRAY)
            y += 20

    img.save(output_path, quality=95)
    print(f"Order image saved: {output_path}")
    return output_path


def screenshot_shopify_order(store_url, order_number, output_dir="/tmp", tenant_id=None):
    order_number = str(order_number).replace('#', '')
    output_path = os.path.join(output_dir, f"shopify_order_{order_number}.png")

    creds = _get_credentials(shop_name=store_url, tenant_id=tenant_id)
    if not creds:
        print(f"No Shopify credentials found for store: {store_url}")
        return None

    shop_url = creds['shopname']
    token = creds['accesstoken']

    print(f"Fetching order {order_number} via Shopify API...")
    order = _fetch_order(shop_url, token, order_number)
    if not order:
        print(f"Order {order_number} not found via API")
        return None

    return render_order_image(order, output_path)


def screenshot_shopify_order_by_url(external_reference, order_number, output_dir="/tmp", tenant_id=None):
    if not external_reference:
        return None
    order_number = str(order_number).replace('#', '')
    output_path = os.path.join(output_dir, f"shopify_order_{order_number}.png")

    # Parse store name from URL: https://admin.shopify.com/store/{name}/orders/{id}
    shop_name = None
    order_id = None
    if '/store/' in external_reference:
        parts = external_reference.split('/store/')[-1].split('/')
        if len(parts) >= 1:
            shop_name = parts[0]
        if len(parts) >= 3 and parts[1] == 'orders':
            order_id = parts[2]

    creds = _get_credentials(shop_name=shop_name, tenant_id=tenant_id)
    if not creds:
        print(f"No Shopify credentials found for store: {shop_name}")
        return None

    shop_url = creds['shopname']
    token = creds['accesstoken']

    order = None
    if order_id:
        print(f"Fetching order by ID {order_id} via Shopify API...")
        order = _fetch_order_by_id(shop_url, token, order_id)

    if not order:
        print(f"Fetching order by reference {order_number} via Shopify API...")
        order = _fetch_order(shop_url, token, order_number)

    if not order:
        print(f"Order not found via API")
        return None

    return render_order_image(order, output_path)


def get_order_proof(store_url, order_number, output_dir="/tmp"):
    path = screenshot_shopify_order(store_url, order_number, output_dir)
    if path:
        return {"screenshot_path": path, "store_url": store_url, "order_number": order_number}
    return None
