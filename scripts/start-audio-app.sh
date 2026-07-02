#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

if [ -f data/soundbar_mac.txt ]; then
  ./scripts/bluetooth-connect-soundbar.sh || true
fi

systemctl --user restart librespot-md-smart-hub.service || true

./scripts/start-app.sh
