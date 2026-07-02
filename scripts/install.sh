#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

echo "MD Smart Hub OS v4.3 Devices + Bluetooth"
echo "Instaluję podstawowe zależności aplikacji..."

sudo apt update
sudo apt install -y python3 python3-tk git xdg-utils chromium-browser bluetooth bluez pulseaudio-utils || true

chmod +x scripts/*.sh

echo ""
echo "Gotowe."
echo "Uruchom aplikację:"
echo "./scripts/start-app.sh"
echo ""
echo "Spotify Connect / Bluetooth instalujemy osobno:"
echo "./scripts/install-spotify-connect.sh"
