#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

MAC="$1"

if [ -z "$MAC" ]; then
  echo "Podaj MAC soundbara."
  echo "Przykład:"
  echo "./scripts/bluetooth-pair-connect.sh AA:BB:CC:DD:EE:FF"
  exit 1
fi

mkdir -p data

echo "$MAC" > data/soundbar_mac.txt

bluetoothctl power on
bluetoothctl agent on
bluetoothctl default-agent

echo "Paruję $MAC..."
bluetoothctl pair "$MAC" || true
bluetoothctl trust "$MAC" || true
bluetoothctl connect "$MAC" || true

echo ""
echo "Status:"
bluetoothctl info "$MAC" || true

echo ""
echo "MAC zapisany w data/soundbar_mac.txt"
echo "Aplikacja pokaże status w ekranie Audio."
