#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

echo "================================================="
echo "MD Smart Hub Spotify Connect installer"
echo "================================================="
echo ""
echo "Ten skrypt zbuduje librespot. Na Raspberry może to potrwać długo."
echo "Jeśli pojawi się błąd, zrób zdjęcie terminala i wyślij."
echo ""

sudo apt update
sudo apt install -y \
  git curl build-essential pkg-config \
  rustc cargo \
  libssl-dev libasound2-dev libpulse-dev libdbus-1-dev \
  bluez bluetooth pulseaudio-utils avahi-daemon

echo ""
echo "Instaluję / aktualizuję librespot przez Cargo..."
echo ""

if command -v librespot >/dev/null 2>&1; then
  LIBRESPOT_BIN="$(command -v librespot)"
else
  if ! "$HOME/.cargo/bin/librespot" --version >/dev/null 2>&1; then
    cargo install librespot --locked --features pulseaudio-backend || cargo install librespot --locked
  fi
  LIBRESPOT_BIN="$HOME/.cargo/bin/librespot"
fi

if [ ! -x "$LIBRESPOT_BIN" ]; then
  echo "Nie znaleziono librespot po instalacji."
  exit 1
fi

mkdir -p "$HOME/.config/systemd/user"

cat > "$HOME/.config/systemd/user/librespot-md-smart-hub.service" <<EOF
[Unit]
Description=MD Smart Hub Spotify Connect
After=default.target sound.target bluetooth.target

[Service]
ExecStart=$LIBRESPOT_BIN --name "MD Smart Hub" --device-type speaker --backend pulseaudio --bitrate 320 --initial-volume 70 --enable-volume-normalisation
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable librespot-md-smart-hub.service
systemctl --user restart librespot-md-smart-hub.service || true

echo ""
echo "Status usługi:"
systemctl --user --no-pager status librespot-md-smart-hub.service || true

echo ""
echo "Gotowe."
echo "W Spotify na telefonie powinno pojawić się urządzenie: MD Smart Hub"
echo ""
echo "Jeśli urządzenie nie pojawi się od razu:"
echo "1. Upewnij się, że telefon i Raspberry są w tej samej sieci Wi‑Fi."
echo "2. Odczekaj 30 sekund."
echo "3. W aplikacji MD Smart Hub otwórz Audio i kliknij Odśwież."
