# CLAUDE.md — Chargeback-Response-VM

This file provides context and conventions for AI assistants working in this repository.

---

## Project Overview

**Chargeback-Response-VM** is a Python-based automation system that generates professional PDF chargeback dispute response documents. It integrates with Shopify, a MySQL database, Redis, and an n8n webhook (LLM pipeline) to gather supporting evidence and produce tailored responses for different chargeback reason codes.

**Primary users:** Internal payment operations/fraud teams at FUGU.

---

## Architecture

### Entry Points

| File | Purpose | How to Run |
|------|---------|------------|
| `web_app.py` | Flask web UI (port 5000) — form input, PDF download | `python web_app.py` |
| `Main.py` | Synchronous CLI processor for a single payment | `python Main.py <payment_id>` |
| `main_async.py` | Async/parallel processor, outputs to `bulk_responses/` | `python main_async.py <payment_id>` |
| `chargeback_main.py` | Alternate sync processor (near-duplicate of `Main.py`) | `python chargeback_main.py` |

### Processing Flow

```
User Input (Payment ID)
    ↓
1. MySQL query — fetch payment info (tenant ID, shop name, payer phone, external ref)
    ↓
2. n8n Webhook — LLM returns: reason code, KYC images, structured analysis
    ↓
3. Route to dispute type:
   - FRAUD     → KYC + session evidence + location map + Fugu screenshot
   - PNR       → Shopify tracking proof + return policy
   - PNA       → Return policy + order screenshot
   - CNP       → Card details visualization
    ↓
4. Collect evidence (parallel in main_async.py)
    ↓
5. Generate PDF via appropriate generator module
    ↓
6. Return file path (CLI) or show download link (web)
```

---

## Module Reference

### PDF Generators

| File | Dispute Type | Key Evidence Included |
|------|-------------|----------------------|
| `chargeback_generator_fraud.py` | Fraud / Unauthorized | KYC images, session history, location map, Fugu screenshot |
| `chargeback_generator_pnr.py` | Product Not Received | Shopify tracking proof |
| `chargeback_generator_pna.py` | Product Not Acceptable | Return policy, order screenshot |
| `chargeback_generator_cnp.py` | Credit Not Processed | Card/transaction details |
| `pdf_footer.py` | Shared | FUGU branding footer used by all generators |

### Evidence Collectors

| File | What It Does |
|------|-------------|
| `session_evidence_extractor.py` | Queries MySQL for device fingerprints and session history |
| `card_details.py` | Builds a styled card/transaction details image via Shopify API |
| `shopify_tracking.py` | Captures shipping/tracking proof from Shopify |
| `shopify_order_screenshot.py` | Takes a Playwright screenshot of the Shopify order page |
| `fugu_screenshot.py` | Takes an authenticated Playwright screenshot of Fugu payment info |
| `map_generator.py` | Generates a map showing IP location vs. billing vs. shipping address |
| `public_records.py` | Redis lookup for public record verification |

### Configuration & Utilities

| File | Purpose |
|------|---------|
| `return_policies.py` | Per-tenant return policy strings used in PNA/PNR PDFs |
| `test.py` | Manual debug script — tests DB connectivity and Shopify API for a specific payment |

---

## Technology Stack

- **Python 3.x** — all application code
- **Flask** — web interface (`web_app.py`)
- **FastAPI + Uvicorn** — declared in `requirements.txt`, not yet fully wired
- **Pydantic** 2.x — data validation
- **ReportLab** 4.0.8 — PDF generation
- **Playwright** 1.41.0 — headless (actually `headless=False`) browser for screenshots
- **MySQL Connector Python** 8.2.0 — direct MySQL access (no ORM)
- **Redis** 5.0.1 — public records store
- **Requests** 2.31.0 — HTTP calls to Shopify API and n8n webhook
- **Pillow** 10.2.0 — image processing

### Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

---

## External Service Dependencies

| Service | Purpose | Config Location |
|---------|---------|----------------|
| MySQL (Azure) | All payment, session, Shopify credentials data | Hardcoded `DB_CONFIG` in each file |
| Redis (RedisLabs) | Public records lookup | `REDIS_CONFIG` in `public_records.py` |
| n8n Webhook | LLM-powered analysis pipeline | Hardcoded URL in `Main.py` / `main_async.py` |
| Shopify API | Order data, tracking, screenshots | Credentials fetched from MySQL `shopifyintegration` table |
| Chromium | Screenshots via Playwright | Must be installed: `playwright install chromium` |

> **Important:** All credentials are currently hardcoded in source files. There is no `.env` file or secrets manager. Playwright's `headless=False` setting means browsers will launch visibly on a desktop environment — change to `headless=True` for headless/server contexts.

---

## Database Schema (Key Tables)

| Table | Used For |
|-------|---------|
| `payments` | Payment records, payer info, IP, external reference |
| `paymentsessionevidence` | Links payments to session evidence |
| `session_evidences` | Device fingerprints and browser session history |
| `shopifyintegration` | Per-tenant Shopify API credentials |
| `paymentbeneficiaries` | Shipping address data |
| `ipcache` | IP geolocation coordinates |

---

## Dispute Reason Code Routing

Reason codes come back from the n8n webhook. The system routes based on these values:

| Reason Code Pattern | Generator Used |
|---------------------|---------------|
| Contains `fraud` / `unauthorized` | `chargeback_generator_fraud.py` |
| Contains `not received` / `PNR` | `chargeback_generator_pnr.py` |
| Contains `not acceptable` / `PNA` | `chargeback_generator_pna.py` |
| Contains `credit not processed` / `CNP` | `chargeback_generator_cnp.py` |

---

## Per-Tenant Configuration

Return policies are defined in `return_policies.py` using a dictionary keyed by tenant slug:

```python
RETURN_POLICIES = {
    "edhardyoriginals": "...",
    "e420": "...",
    "tenant2": "...",
}
```

Add new tenants here. A `DEFAULT_RETURN_POLICY` fallback is also defined.

---

## Testing

There is **no automated test suite**. `test.py` is a manual debug script.

To test a specific payment ID:
```bash
python test.py
# Edit the PAYMENT_ID constant inside the file first
```

The script tests: MySQL connectivity, payment record fetch, Shopify transactions API.

---

## Known Issues & Important Caveats

1. **Hardcoded credentials** — DB, Redis, n8n, and cookie tokens are embedded in source. Rotate credentials carefully and update all files.

2. **Expiring Playwright cookies** — `fugu_screenshot.py` has hardcoded JWT session cookies that expire. When screenshots start failing, the cookies in that file need manual refresh.

3. **`headless=False`** — Playwright launches a visible browser. This requires a display (X11 or similar). On a headless server, change to `headless=True` in `shopify_order_screenshot.py`, `shopify_tracking.py`, and `fugu_screenshot.py`.

4. **Duplicate entry points** — `Main.py` and `chargeback_main.py` are nearly identical. `Main.py` is the canonical version; prefer it. `chargeback_main.backup.py` is a historical backup.

5. **No DB connection pooling** — Each query opens and closes its own connection. Under concurrent load this may exhaust MySQL connections.

6. **`/tmp` paths** — Screenshots are saved to `/tmp`. Generated PDFs go to the working directory (or `bulk_responses/`). These are not cleaned up automatically.

7. **n8n webhook is a hard dependency** — If the n8n endpoint is unreachable, the entire pipeline fails. There is no fallback.

---

## Development Conventions

- **Follow existing patterns** within each module — don't introduce new frameworks or ORMs without discussion.
- **Keep credentials out of new code** — use constants at the top of the file matching the existing `DB_CONFIG` / `REDIS_CONFIG` pattern until a proper secrets manager is added.
- **ReportLab PDF layout** — all generators use `SimpleDocTemplate` with `Spacer`, `Table`, `Image`, and `Paragraph` elements. Match the visual style of existing generators when adding a new dispute type.
- **Playwright screenshots** — always use `try/finally` to ensure the browser is closed even on error.
- **Error handling** — log errors and return `None` rather than raising uncaught exceptions in evidence collection functions; the PDF generators handle `None` evidence gracefully.
- **New tenant support** — add return policy to `return_policies.py`; no other file changes required for basic PNA/PNR support.

---

## File Output Locations

| Mode | Output Directory |
|------|-----------------|
| `web_app.py` | Current working directory (served for download) |
| `Main.py` | Current working directory |
| `main_async.py` | `bulk_responses/` subdirectory |
| Screenshots (temp) | `/tmp/` |

---

## Git & Branch Workflow

- **Main branch:** `master`
- **Development branches:** `claude/<description>` for AI-assisted changes
- No CI/CD pipeline is configured.
- Commit messages should be descriptive (e.g., `Add headless mode support for Playwright`, `Fix expired Fugu cookie handling`).

---

## Glossary

| Term | Meaning |
|------|---------|
| **Chargeback** | A payment dispute initiated by a cardholder through their bank |
| **Reason Code** | A standardized code/label classifying the dispute type |
| **FRAUD / Unauthorized** | Cardholder claims they did not make the purchase |
| **PNR** | Product Not Received — item never arrived |
| **PNA** | Product Not Acceptable — item arrived but was wrong/damaged |
| **CNP** | Credit Not Processed — refund was promised but not issued |
| **KYC** | Know Your Customer — identity verification images |
| **Tenant** | A merchant/store using the FUGU payment platform |
| **n8n** | A workflow automation tool hosting the LLM analysis webhook |
| **FUGU** | The payment fraud-prevention platform this system is built for |
