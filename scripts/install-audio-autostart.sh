#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

mkdir -p "$HOME/.config/autostart"

cat > "$HOME/.config/autostart/md-smart-hub-audio.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=MD Smart Hub Audio
Comment=Start MD Smart Hub with Bluetooth and Spotify Connect
Exec=$PWD/scripts/start-audio-app.sh
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

echo "Autostart MD Smart Hub Audio dodany."
echo "Po restarcie Raspberry powinno połączyć soundbar, uruchomić Spotify Connect i aplikację."
