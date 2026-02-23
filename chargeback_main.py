"""
MAIN CHARGEBACK RESPONSE GENERATOR (ASYNC)
"""

import sys
import os
import asyncio
import requests
import json
import mysql.connector
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chargeback_generator_fraud import generate_pdf as generate_fraud_pdf
from chargeback_generator_pnr import generate_pdf as generate_pnr_pdf
from chargeback_generator_pna import generate_pdf as generate_pna_pdf
from chargeback_generator_cnp import generate_pdf as generate_cnp_pdf
from session_evidence_extractor import SessionEvidenceExtractor
from shopify_order_screenshot import screenshot_shopify_order, screenshot_shopify_order_by_url
from shopify_tracking import get_shipping_proof
from fugu_screenshot import screenshot_payment_info
from public_records import get_public_records
from map_generator import generate_location_map
from card_details import get_card_details_image, get_avs_details_image

N8N_WEBHOOK = "https://dan-fugu.app.n8n.cloud/webhook/55614aa6-0d64-4390-ab2c-d595b6e0fda4"
SCREENSHOT_DIR = "/tmp"

DB_CONFIG = {
    'host': 'fugu-sql-prod-rep.mysql.database.azure.com',
    'database': 'fuguprod',
    'user': 'geckoboard',
    'password': 'UrxP3FmJ+z1bF1Xjs<*%'
}

executor = ThreadPoolExecutor(max_workers=6)


def get_payment_info(paymentid):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        query = """
            SELECT p.Tenants_tntid, p.externalreference, s.shopname, p.payer_mobile 
            FROM payments p
            LEFT JOIN shopifyintegration s ON p.Tenants_tntid = s.tenantid
            WHERE p.paymentid = %s
        """
        cursor.execute(query, (paymentid,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            shopname = result[2]
            store_name = shopname.replace('.myshopify.com', '').strip() if shopname else None
            return {
                'tenant_id': result[0],
                'external_reference': result[1],
                'shop_name': store_name,
                'payer_mobile': result[3]
            }
        return None
    except Exception as e:
        print(f"Error getting payment info: {e}")
        return None


FRAUD_REASONS = ["unrecognized_transaction", "fraud", "fraudulent", "unauthorized", "stolen_card", "card_not_present", "no_authorization"]
PNR_REASONS = ["product_not_received", "merchandise_not_received", "13.1", "delivery_confirmed"]
PNA_REASONS = ["product_unacceptable", "not_as_described", "services_not_rendered", "quality_issue"]
CNP_REASONS = ["credit_not_processed", "credit_not_issued", "refund_not_processed"]


def get_reason_type(reason):
    if not reason:
        return "fraud"
    reason_lower = reason.lower().strip().replace(" ", "_").replace("-", "_")
    if reason_lower in FRAUD_REASONS:
        return "fraud"
    elif reason_lower in PNR_REASONS:
        return "pnr"
    elif reason_lower in PNA_REASONS:
        return "pna"
    elif reason_lower in CNP_REASONS:
        return "cnp"
    return "fraud"


def parse_response(response):
    llm_data = {}
    kyc_images = {'id_card': None, 'selfie': None, 'card': None}
    reason = None
    tenant = None

    if isinstance(response, dict):
        if 'output' in response:
            output = response['output']
            if isinstance(output, str):
                try:
                    llm_data = json.loads(output)
                except:
                    pass
            else:
                llm_data = output
        if 'kyc_images' in response:
            kyc_images = response['kyc_images']
        reason = response.get('reason') or llm_data.get('chargeback_reason')
        tenant = response.get('tenant') or response.get('tenant_name') or llm_data.get('tenant') or 'default'

    return llm_data, kyc_images, reason, tenant


# Async wrappers
async def async_run(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, func, *args)


async def async_call_webhook(paymentid):
    def _call():
        try:
            r = requests.post(N8N_WEBHOOK, json={"paymentid": paymentid}, timeout=120)
            return r.json() if r.text else None
        except Exception as e:
            print(f"Webhook error: {e}")
            return None
    return await async_run(_call)


async def async_screenshot_order(shop_name, external_reference, clean_reference):
    def _screenshot():
        try:
            if external_reference and shop_name:
                url = f"https://admin.shopify.com/store/{shop_name}/orders/{external_reference}"
                return screenshot_shopify_order_by_url(url, clean_reference, SCREENSHOT_DIR)
            return screenshot_shopify_order(shop_name, clean_reference, SCREENSHOT_DIR)
        except Exception as e:
            print(f"Order screenshot error: {e}")
            return None
    return await async_run(_screenshot)


async def async_screenshot_tracking(tenant_id, tenant_name, clean_reference):
    def _screenshot():
        try:
            return get_shipping_proof(tenant_id=tenant_id, tenant_name=tenant_name, reference=clean_reference, output_dir=SCREENSHOT_DIR)
        except Exception as e:
            print(f"Tracking error: {e}")
            return None
    return await async_run(_screenshot)


async def async_screenshot_identity(paymentid, tenant_id):
    def _screenshot():
        try:
            return screenshot_payment_info(paymentid, tenant_id, SCREENSHOT_DIR)
        except Exception as e:
            print(f"Identity error: {e}")
            return None
    return await async_run(_screenshot)


async def async_get_session_evidence(paymentid):
    def _get():
        try:
            extractor = SessionEvidenceExtractor()
            evidence = extractor.get_session_evidence(paymentid)
            extractor.close()
            return None if 'error' in evidence else evidence
        except:
            return None
    return await async_run(_get)


async def async_get_card_details(tenant_id, external_reference, reference):
    def _get():
        try:
            return get_card_details_image(tenant_id, external_reference, reference, SCREENSHOT_DIR)
        except:
            return None
    return await async_run(_get)


async def async_get_avs_details(tenant_id, external_reference, reference):
    def _get():
        try:
            return get_avs_details_image(tenant_id, external_reference, reference, SCREENSHOT_DIR)
        except:
            return None
    return await async_run(_get)


async def async_get_public_records(payer_mobile):
    def _get():
        try:
            return get_public_records(payer_mobile)
        except:
            return None
    return await async_run(_get)


async def async_generate_location_map(paymentid):
    def _generate():
        try:
            return generate_location_map(paymentid, SCREENSHOT_DIR)
        except:
            return None
    return await async_run(_generate)


async def process_chargeback_async(paymentid):
    print("=" * 50)
    print("CHARGEBACK DISPUTE GENERATOR")
    print("=" * 50)
    print(f"Payment ID: {paymentid}")

    # Get payment info
    print("Getting payment info from database...")
    payment_info = get_payment_info(paymentid)
    tenant_id = payment_info.get('tenant_id') if payment_info else None
    external_reference = payment_info.get('external_reference') if payment_info else None
    shop_name = payment_info.get('shop_name') if payment_info else None
    payer_mobile = payment_info.get('payer_mobile') if payment_info else None

    print(f"Tenant ID: {tenant_id}")
    print(f"External Reference: {external_reference}")
    print(f"Shop Name: {shop_name}")

    # Call webhook
    print("Sending request to n8n...")
    response = await async_call_webhook(paymentid)
    if not response:
        return None

    data, kyc_images, reason, tenant = parse_response(response)
    reference = data.get('reference') or paymentid
    reason_type = get_reason_type(reason)
    clean_reference = str(reference).replace('#', '')

    print(f"Reference: {reference}")
    print(f"Reason: {reason}")
    print(f"Reason Type: {reason_type}")
    print(f"Tenant: {tenant}")
    print("=" * 50)

    screenshots = {}
    session_evidence = None
    public_records_data = None
    location_map_data = None

    if reason_type == "fraud":
        print("Running parallel tasks for FRAUD case...")

        tasks = {
            'order': async_screenshot_order(shop_name or tenant, external_reference, clean_reference),
            'tracking': async_screenshot_tracking(tenant_id, tenant, clean_reference),
            'identity': async_screenshot_identity(paymentid, tenant_id),
            'card_details': async_get_card_details(tenant_id, external_reference, reference),
            'session': async_get_session_evidence(paymentid),
        }

        if data.get('location_proof'):
            tasks['location'] = async_generate_location_map(paymentid)
        if data.get('public_records_proof') and payer_mobile:
            tasks['public_records'] = async_get_public_records(payer_mobile)

        payment_proof = data.get('payment_proof', {})
        payment_text = payment_proof.get('text', '') if isinstance(payment_proof, dict) else str(payment_proof)
        if 'AVS' in payment_text.upper() and ('Y' in payment_text or 'match' in payment_text.lower()):
            tasks['avs'] = async_get_avs_details(tenant_id, external_reference, reference)

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        results_dict = dict(zip(tasks.keys(), results))

        if results_dict.get('order') and not isinstance(results_dict['order'], Exception):
            screenshots['order_screenshot'] = results_dict['order']
            print(f"  ✓ Order screenshot")
        if results_dict.get('tracking') and not isinstance(results_dict['tracking'], Exception):
            tracking = results_dict['tracking']
            if tracking and tracking.get('screenshot_path'):
                screenshots['tracking_screenshot'] = tracking['screenshot_path']
                screenshots['tracking_url'] = tracking.get('tracking_url')
                print(f"  ✓ Tracking screenshot")
        if results_dict.get('identity') and not isinstance(results_dict['identity'], Exception):
            screenshots['identity_screenshot'] = results_dict['identity']
            print(f"  ✓ Identity screenshot")
        if results_dict.get('card_details') and not isinstance(results_dict['card_details'], Exception):
            if results_dict['card_details'].get('screenshot_path'):
                screenshots['card_details_screenshot'] = results_dict['card_details']['screenshot_path']
                print(f"  ✓ Card details")
        if results_dict.get('session') and not isinstance(results_dict['session'], Exception):
            session_evidence = results_dict['session']
            print(f"  ✓ Session evidence")
        if results_dict.get('location') and not isinstance(results_dict['location'], Exception):
            location_map_data = results_dict['location']
            if location_map_data and location_map_data.get('screenshot_path'):
                screenshots['location_screenshot'] = location_map_data['screenshot_path']
                print(f"  ✓ Location map")
        if results_dict.get('public_records') and not isinstance(results_dict['public_records'], Exception):
            public_records_data = results_dict['public_records']
            public_records_data['_phone_number'] = payer_mobile
            print(f"  ✓ Public records")
        if results_dict.get('avs') and not isinstance(results_dict['avs'], Exception):
            if results_dict['avs'].get('screenshot_path'):
                screenshots['avs_screenshot'] = results_dict['avs']['screenshot_path']
                print(f"  ✓ AVS details")

        output_path = f"bulk_responses/chargeback_fraud_{reference}.pdf"
        os.makedirs("bulk_responses", exist_ok=True)
        generate_fraud_pdf(data, kyc_images, output_path, session_evidence, tenant, screenshots, public_records_data, location_map_data)

    elif reason_type == "pnr":
        print("Running parallel tasks for PNR case...")

        tasks = {
            'order': async_screenshot_order(shop_name or tenant, external_reference, clean_reference),
            'tracking': async_screenshot_tracking(tenant_id, tenant, clean_reference),
            'card_details': async_get_card_details(tenant_id, external_reference, reference),
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        results_dict = dict(zip(tasks.keys(), results))

        if results_dict.get('order') and not isinstance(results_dict['order'], Exception):
            screenshots['order_screenshot'] = results_dict['order']
            print(f"  ✓ Order screenshot")
        if results_dict.get('tracking') and not isinstance(results_dict['tracking'], Exception):
            tracking = results_dict['tracking']
            if tracking and tracking.get('screenshot_path'):
                screenshots['tracking_screenshot'] = tracking['screenshot_path']
                screenshots['tracking_url'] = tracking.get('tracking_url')
                print(f"  ✓ Tracking screenshot")
        if results_dict.get('card_details') and not isinstance(results_dict['card_details'], Exception):
            if results_dict['card_details'].get('screenshot_path'):
                screenshots['card_details_screenshot'] = results_dict['card_details']['screenshot_path']
                print(f"  ✓ Card details")

        output_path = f"bulk_responses/chargeback_pnr_{reference}.pdf"
        os.makedirs("bulk_responses", exist_ok=True)
        generate_pnr_pdf(data, output_path, tenant, screenshots)

    elif reason_type == "pna":
        print("Running parallel tasks for PNA case...")

        tasks = {
            'order': async_screenshot_order(shop_name or tenant, external_reference, clean_reference),
            'tracking': async_screenshot_tracking(tenant_id, tenant, clean_reference),
            'card_details': async_get_card_details(tenant_id, external_reference, reference),
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        results_dict = dict(zip(tasks.keys(), results))

        if results_dict.get('order') and not isinstance(results_dict['order'], Exception):
            screenshots['order_screenshot'] = results_dict['order']
            print(f"  ✓ Order screenshot")
        if results_dict.get('tracking') and not isinstance(results_dict['tracking'], Exception):
            tracking = results_dict['tracking']
            if tracking and tracking.get('screenshot_path'):
                screenshots['tracking_screenshot'] = tracking['screenshot_path']
                screenshots['tracking_url'] = tracking.get('tracking_url')
                print(f"  ✓ Tracking screenshot")
        if results_dict.get('card_details') and not isinstance(results_dict['card_details'], Exception):
            if results_dict['card_details'].get('screenshot_path'):
                screenshots['card_details_screenshot'] = results_dict['card_details']['screenshot_path']
                print(f"  ✓ Card details")

        output_path = f"bulk_responses/chargeback_pna_{reference}.pdf"
        os.makedirs("bulk_responses", exist_ok=True)
        generate_pna_pdf(data, output_path, tenant, screenshots)

    elif reason_type == "cnp":
        print("Running parallel tasks for CNP case...")

        tasks = {
            'order': async_screenshot_order(shop_name or tenant, external_reference, clean_reference),
            'tracking': async_screenshot_tracking(tenant_id, tenant, clean_reference),
            'card_details': async_get_card_details(tenant_id, external_reference, reference),
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        results_dict = dict(zip(tasks.keys(), results))

        if results_dict.get('order') and not isinstance(results_dict['order'], Exception):
            screenshots['order_screenshot'] = results_dict['order']
            print(f"  ✓ Order screenshot")
        if results_dict.get('tracking') and not isinstance(results_dict['tracking'], Exception):
            tracking = results_dict['tracking']
            if tracking and tracking.get('screenshot_path'):
                screenshots['tracking_screenshot'] = tracking['screenshot_path']
                screenshots['tracking_url'] = tracking.get('tracking_url')
                print(f"  ✓ Tracking screenshot")
        if results_dict.get('card_details') and not isinstance(results_dict['card_details'], Exception):
            if results_dict['card_details'].get('screenshot_path'):
                screenshots['card_details_screenshot'] = results_dict['card_details']['screenshot_path']
                print(f"  ✓ Card details")

        output_path = f"bulk_responses/chargeback_cnp_{reference}.pdf"
        os.makedirs("bulk_responses", exist_ok=True)
        generate_cnp_pdf(data, output_path, tenant, screenshots)

    print(f"\nPDF created: {output_path}")
    return output_path


def process_chargeback(paymentid):
    """Sync wrapper for web_app.py"""
    return asyncio.run(process_chargeback_async(paymentid))


if __name__ == "__main__":
    paymentid = sys.argv[1] if len(sys.argv) > 1 else input("Payment ID: ").strip()
    result = process_chargeback(paymentid)
    if result:
        print(f"\nSUCCESS: {result}")
    else:
        print("\nFAILED")
        sys.exit(1)
