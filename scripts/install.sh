#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

echo "MD Smart Hub OS v4.0 Alpha App Edition"
echo "Instaluję podstawowe zależności aplikacji..."

sudo apt update
sudo apt install -y python3 python3-tk git

chmod +x scripts/*.sh

echo ""
echo "Gotowe."
echo "Uruchom aplikację:"
echo "./scripts/start-app.sh"
