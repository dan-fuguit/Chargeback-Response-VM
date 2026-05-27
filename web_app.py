from flask import Flask, request, send_file, render_template_string, redirect, url_for, session
import os
import sys
import subprocess
import requests
import time
import uuid
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chargeback_main import process_chargeback

app = Flask(__name__)
app.secret_key = 'fugu-chargeback-secret-key'

# Store completed files temporarily
completed_files = {}

def ensure_chrome_running():
    try:
        requests.get("http://localhost:9222/json", timeout=2)
        print("Chrome already running")
    except:
        print("Starting Chrome...")
        subprocess.Popen(['chromium-browser', '--remote-debugging-port=9222'])
        time.sleep(3)

HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>FUGU Chargeback Responder</title>
    <style>
        * { box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            margin: 0;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            width: 100%;
            max-width: 500px;
            margin: 20px;
        }
        .logo {
            text-align: center;
            margin-bottom: 30px;
        }
        .logo h1 {
            color: #1a1a2e;
            font-size: 28px;
            margin: 0;
        }
        .logo span {
            color: #4facfe;
        }
        .logo p {
            color: #666;
            margin: 5px 0 0 0;
            font-size: 14px;
        }
        input[type="text"] {
            width: 100%;
            padding: 15px;
            font-size: 16px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            margin: 10px 0 20px 0;
            transition: border-color 0.3s;
        }
        input[type="text"]:focus {
            outline: none;
            border-color: #4facfe;
        }
        button, .btn {
            width: 100%;
            padding: 15px;
            font-size: 16px;
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: transform 0.2s, box-shadow 0.2s;
            text-decoration: none;
            display: inline-block;
            text-align: center;
        }
        button:hover, .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(79, 172, 254, 0.4);
        }
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        .btn-success {
            background: linear-gradient(135deg, #00b09b 0%, #96c93d 100%);
        }
        .btn-secondary {
            background: #6c757d;
            margin-top: 10px;
        }
        .message {
            padding: 15px;
            margin: 20px 0 0 0;
            border-radius: 8px;
            text-align: center;
        }
        .error {
            background: #fff0f0;
            color: #cc0000;
            border: 1px solid #ffcccc;
        }
        .success-box {
            background: #f0fff0;
            border: 1px solid #ccffcc;
            border-radius: 8px;
            padding: 25px;
            text-align: center;
            margin-top: 20px;
        }
        .success-box h2 {
            color: #00aa00;
            margin: 0 0 10px 0;
        }
        .success-box p {
            color: #666;
            margin: 0 0 20px 0;
        }
        .checkmark {
            font-size: 50px;
            margin-bottom: 15px;
        }
        .loading {
            display: none;
            text-align: center;
            margin-top: 20px;
        }
        .loading.show {
            display: block;
        }
        .spinner {
            width: 40px;
            height: 40px;
            border: 4px solid #e0e0e0;
            border-top-color: #4facfe;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px auto;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .loading p {
            color: #666;
            margin: 0;
        }
        .loading small {
            color: #999;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <h1><span>FUGU</span> Chargeback Responder</h1>
            <p>Generate dispute response documents</p>
        </div>
        
        {% if success and file_id %}
        <div class="success-box">
            <div class="checkmark">✅</div>
            <h2>Document Ready!</h2>
            <p>Your chargeback response has been generated successfully.</p>
            <a href="/download/{{ file_id }}" class="btn btn-success">Download {{ file_format }}</a>
            <a href="/" class="btn btn-secondary">Generate Another</a>
        </div>
        {% else %}
        <form method="POST" id="form">
            <input type="text" name="payment_id" id="payment_id" placeholder="Enter Payment ID" required>
            <div style="display: flex; gap: 10px; margin: 10px 0 20px 0;">
                <label style="flex: 1; display: flex; align-items: center; padding: 12px; border: 2px solid #e0e0e0; border-radius: 8px; cursor: pointer; transition: border-color 0.3s;">
                    <input type="radio" name="output_format" value="pdf" checked style="margin-right: 8px; accent-color: #4facfe;">
                    <span style="font-size: 14px; color: #2d3748;">PDF Document</span>
                </label>
                <label style="flex: 1; display: flex; align-items: center; padding: 12px; border: 2px solid #e0e0e0; border-radius: 8px; cursor: pointer; transition: border-color 0.3s;">
                    <input type="radio" name="output_format" value="docx" style="margin-right: 8px; accent-color: #4facfe;">
                    <span style="font-size: 14px; color: #2d3748;">Word Document</span>
                </label>
            </div>
            <button type="submit" id="submit_btn">Generate Document</button>
        </form>
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>Generating your document...</p>
            <small>Please wait, this may take a few minutes</small>
        </div>
        {% if message %}
        <div class="message {{ message_type }}">{{ message }}</div>
        {% endif %}
        {% endif %}
    </div>
    <script>
        document.getElementById('form')?.addEventListener('submit', function() {
            document.getElementById('submit_btn').disabled = true;
            document.getElementById('submit_btn').textContent = 'Processing...';
            document.getElementById('loading').classList.add('show');
        });
    </script>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        ensure_chrome_running()
        payment_id = request.form.get('payment_id', '').strip()
        if not payment_id:
            return render_template_string(HTML, message="Please enter a payment ID", message_type="error")
        
        output_format = request.form.get('output_format', 'pdf').strip()
        if output_format not in ('pdf', 'docx'):
            output_format = 'pdf'

        try:
            result = process_chargeback(payment_id, output_format)
            if result and os.path.exists(result):
                file_id = str(uuid.uuid4())
                completed_files[file_id] = result
                file_format = "Word Document" if output_format == "docx" else "PDF"
                return render_template_string(HTML, success=True, file_id=file_id, file_format=file_format)
            else:
                return render_template_string(HTML, message="Failed to generate document", message_type="error")
        except Exception as e:
            return render_template_string(HTML, message=f"Error: {e}", message_type="error")
    
    return render_template_string(HTML)

@app.route('/download/<file_id>')
def download(file_id):
    if file_id in completed_files:
        filepath = completed_files[file_id]
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
    return redirect(url_for('index'))


COOKIES_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Update FUGU Cookies</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            margin: 0;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            width: 100%;
            max-width: 660px;
            margin: 20px;
        }
        h1 { color: #1a1a2e; font-size: 22px; margin: 0 0 6px 0; }
        p { color: #666; font-size: 14px; margin: 0 0 20px 0; }
        ol { color: #444; font-size: 13px; padding-left: 20px; margin: 0 0 20px 0; line-height: 1.8; }
        code { background: #f0f4f8; padding: 2px 6px; border-radius: 4px; font-size: 12px; }
        textarea {
            width: 100%;
            height: 200px;
            padding: 12px;
            font-size: 12px;
            font-family: monospace;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            resize: vertical;
            margin-bottom: 16px;
        }
        textarea:focus { outline: none; border-color: #4facfe; }
        .btn {
            width: 100%;
            padding: 14px;
            font-size: 15px;
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
        }
        .btn-back {
            display: inline-block;
            margin-top: 12px;
            color: #4facfe;
            text-decoration: none;
            font-size: 14px;
        }
        .msg { padding: 12px; border-radius: 8px; margin-bottom: 16px; font-size: 14px; }
        .success { background: #f0fff0; color: #006600; border: 1px solid #ccffcc; }
        .error   { background: #fff0f0; color: #cc0000; border: 1px solid #ffcccc; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Update FUGU Session Cookies</h1>
        <p>Paste fresh cookies here when the session expires — no code editing needed.</p>
        <ol>
            <li>Open <strong>app.fugu-it.com</strong> in Chrome and log in</li>
            <li>Install the <strong>EditThisCookie</strong> browser extension</li>
            <li>Click the extension icon and choose <strong>Export</strong></li>
            <li>Paste the JSON array below and click Save</li>
        </ol>
        {% if message %}
        <div class="msg {{ msg_type }}">{{ message }}</div>
        {% endif %}
        <form method="POST">
            <textarea name="cookies_json" placeholder='[{"name": "session", "value": "...", "domain": ".fugu-it.com", "path": "/"}, ...]'>{{ current_cookies }}</textarea>
            <button type="submit" class="btn">Save Cookies</button>
        </form>
        <a href="/" class="btn-back">← Back to main app</a>
    </div>
</body>
</html>
'''

FUGU_COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fugu_cookies.json")


@app.route('/cookies', methods=['GET', 'POST'])
def update_cookies():
    message = None
    msg_type = None

    current_cookies = ''
    if os.path.exists(FUGU_COOKIES_FILE):
        with open(FUGU_COOKIES_FILE, 'r') as f:
            current_cookies = f.read()

    if request.method == 'POST':
        raw = request.form.get('cookies_json', '').strip()
        try:
            cookies = json.loads(raw)
            if not isinstance(cookies, list):
                raise ValueError("Expected a JSON array")
            # Keep only fields Playwright needs
            cleaned = []
            for c in cookies:
                entry = {
                    'name': c['name'],
                    'value': c['value'],
                    'domain': c['domain'],
                    'path': c.get('path', '/'),
                }
                cleaned.append(entry)
            with open(FUGU_COOKIES_FILE, 'w') as f:
                json.dump(cleaned, f, indent=2)
            current_cookies = json.dumps(cleaned, indent=2)
            message = f"Saved {len(cleaned)} cookies successfully."
            msg_type = 'success'
        except Exception as e:
            message = f"Invalid JSON: {e}"
            msg_type = 'error'

    return render_template_string(COOKIES_HTML, message=message, msg_type=msg_type, current_cookies=current_cookies)


if __name__ == '__main__':
    ensure_chrome_running()
    app.run(host='0.0.0.0', port=5000)
