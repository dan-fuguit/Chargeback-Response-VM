"""
Sends a generated Word response to the Google Apps Script web app bound to the
"Chargeback response" sheet. The script converts it to a Google Doc in the
evidence folder and writes the link in the "Evidence URL" column of the row
whose "Order Number" matches.

Config (not in git): gdrive_config.json next to this file, e.g.
  {"apps_script_url": "https://script.google.com/macros/s/XXXX/exec", "secret": "..."}
"""
import base64
import json
import os
import requests

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gdrive_config.json')


def _config():
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        return cfg if cfg.get('apps_script_url') else None
    except Exception:
        return None


def is_enabled():
    return _config() is not None


def reference_from_path(path):
    """bulk_responses/chargeback_fraud_4201805664.docx -> 4201805664"""
    name = os.path.splitext(os.path.basename(path))[0]
    return name.rsplit('_', 1)[-1].replace('#', '').strip()


def upload(path, reference=None):
    """Returns {'ok': True, 'url': ..., 'sheet': {'tab':..,'row':..} or None} or {'ok': False, 'error': ...}."""
    cfg = _config()
    if not cfg:
        return {'ok': False, 'error': 'Google Drive upload not configured (gdrive_config.json missing)'}
    reference = reference or reference_from_path(path)
    with open(path, 'rb') as f:
        data = base64.b64encode(f.read()).decode()
    payload = {
        'secret': cfg.get('secret', ''),
        'order_number': reference,
        'title': f"{reference} - Chargeback Response",
        'filename': os.path.basename(path),
        'file_b64': data,
    }
    try:
        r = requests.post(cfg['apps_script_url'], data=json.dumps(payload),
                          headers={'Content-Type': 'text/plain'}, timeout=180)
        res = r.json()
    except Exception as e:
        return {'ok': False, 'error': f'Upload failed: {e}'}
    print(f"[gdrive] {res}")
    return res
