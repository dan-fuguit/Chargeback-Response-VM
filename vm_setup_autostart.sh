#!/bin/bash
# Run once on the VM: makes Chromium (with CDP :9222) and the web app start
# automatically when the desktop session starts.
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/chromium-cdp.desktop <<EOT
[Desktop Entry]
Type=Application
Name=Chromium (CDP 9222)
Exec=/snap/bin/chromium --remote-debugging-port=9222 --restore-last-session
X-GNOME-Autostart-enabled=true
EOT
cat > ~/.config/autostart/chargeback-webapp.desktop <<EOT
[Desktop Entry]
Type=Application
Name=Chargeback Responder web app
Exec=bash -c "sleep 20; pgrep -f web_app.py || (cd $HOME/chargeback_responder && venv/bin/python3 web_app.py >> /tmp/webapp.log 2>&1)"
X-GNOME-Autostart-enabled=true
EOT
echo "Autostart OK:"; ls ~/.config/autostart
