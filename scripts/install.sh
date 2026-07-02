#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
echo "MD Smart Hub OS v4.4 Audio Stable"
echo "Instaluję zależności aplikacji i audio..."
sudo apt update
sudo apt install -y python3 python3-tk git xdg-utils chromium-browser bluetooth bluez pulseaudio-utils alsa-utils wireplumber pipewire-pulse || true
chmod +x scripts/*.sh
echo ""
echo "Gotowe."
echo "Uruchom aplikację:"
echo "./scripts/start-audio-app.sh"
