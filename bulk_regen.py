"""
Regenerates chargeback responses in bulk through the running web app, one by one.
Usage on the VM:  nohup venv/bin/python3 -u bulk_regen.py regen_list.txt > /tmp/bulk_regen.log 2>&1 &
The list file holds Shopify order IDs (the number at the end of the "Link" column).
Already-finished IDs (listed in bulk_regen_done.txt) are skipped, so it can be re-run safely.
"""
import os
import re
import sys
import time
import requests
import mysql.connector
from chargeback_main import DB_CONFIG

APP = "http://127.0.0.1:5000/"
DONE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bulk_regen_done.txt")


def payment_for_order(order_id):
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""
        SELECT p.paymentid, (SELECT COUNT(*) FROM chargebacks cb WHERE cb.payment_id = p.paymentid) AS cbs
        FROM payments p WHERE p.externalreference = %s
    """, (str(order_id),))
    rows = cur.fetchall()
    cur.close(); conn.close()
    if not rows:
        return None
    rows.sort(key=lambda r: -r[1])
    return rows[0][0]


def main(list_file):
    ids = [x for x in open(list_file).read().split() if x.strip()]
    done = set(open(DONE_FILE).read().split()) if os.path.exists(DONE_FILE) else set()
    todo = [i for i in ids if i not in done]
    print(f"{len(ids)} orders, {len(todo)} to do")
    ok = fail = 0
    for n, oid in enumerate(todo, 1):
        t0 = time.time()
        try:
            pid = payment_for_order(oid)
            if not pid:
                print(f"[{n}/{len(todo)}] {oid}: payment not found in FUGU"); fail += 1; continue
            r = requests.post(APP, data={"payment_id": pid, "output_format": "docx"}, timeout=900)
            html = r.text
            if "Open Google Doc" in html:
                m = re.search(r'tab <b>([^<]+)</b>, row (\d+)', html)
                where = f"{m.group(1)} row {m.group(2)}" if m else "NOT FOUND IN SHEET"
                print(f"[{n}/{len(todo)}] {oid}: OK ({where}) {int(time.time()-t0)}s"); ok += 1
                with open(DONE_FILE, "a") as f:
                    f.write(oid + "\n")
            else:
                m = re.search(r'(Error:[^<]{0,200}|Failed to generate document|Google Drive upload failed:[^<]{0,200})', html)
                print(f"[{n}/{len(todo)}] {oid}: FAILED - {m.group(1) if m else 'unknown'}"); fail += 1
        except Exception as e:
            print(f"[{n}/{len(todo)}] {oid}: ERROR {e}"); fail += 1
    print(f"FINISHED: {ok} ok, {fail} failed")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "regen_list.txt")
