#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

mkdir -p "$HOME/.config/autostart"

cat > "$HOME/.config/autostart/md-smart-hub-app.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=MD Smart Hub App
Comment=Start MD Smart Hub OS App Edition
Exec=$PWD/scripts/start-app.sh
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

echo "Autostart aplikacji dodany."
