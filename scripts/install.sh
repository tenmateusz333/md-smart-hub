#!/usr/bin/env bash
set -e
echo "MD Smart Hub OS installer"
echo "RC1 nie instaluje jeszcze Spotify Connect. To będzie w RC2."
sudo apt update
sudo apt install -y python3 git chromium-browser || true
echo "Gotowe."
echo "Uruchom: python3 backend/server.py"
