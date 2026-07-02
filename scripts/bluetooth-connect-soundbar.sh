#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

if [ ! -f data/soundbar_mac.txt ]; then
  echo "Brak data/soundbar_mac.txt"
  echo "Najpierw użyj ./scripts/bluetooth-scan.sh i ./scripts/bluetooth-pair-connect.sh MAC"
  exit 1
fi

MAC="$(cat data/soundbar_mac.txt | tr -d '[:space:]')"

bluetoothctl power on
bluetoothctl connect "$MAC" || true
bluetoothctl info "$MAC" || true
