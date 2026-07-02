#!/usr/bin/env bash
set -e

echo "Włącz soundbar w tryb parowania Bluetooth."
echo "Skanowanie potrwa 20 sekund."
echo ""

bluetoothctl power on
bluetoothctl agent on
bluetoothctl default-agent

timeout 20 bluetoothctl scan on || true

echo ""
echo "Zapamiętaj adres MAC soundbara, np. AA:BB:CC:DD:EE:FF"
echo "Potem użyj:"
echo "./scripts/bluetooth-pair-connect.sh AA:BB:CC:DD:EE:FF"
