# MD Smart Hub OS v4.3 Devices + Bluetooth

To jest aktualizacja pod Raspberry jako centrum audio.

## Co zawiera aplikacja

- ekran Audio,
- lista urządzeń Spotify,
- wybór urządzenia Spotify,
- regulacja głośności Spotify,
- status Librespot,
- status Bluetooth soundbara,
- przygotowanie do Spotify Connect,
- skrypty Bluetooth.

## Standardowa aktualizacja

```bash
cd ~/md-smart-hub
git reset --hard
git pull
chmod +x scripts/*.sh
./scripts/install.sh
./scripts/start-app.sh
```

## Instalacja Spotify Connect na Raspberry

Uruchom raz:

```bash
cd ~/md-smart-hub
./scripts/install-spotify-connect.sh
```

To może potrwać długo, bo Raspberry może budować librespot.

Po zakończeniu w Spotify na telefonie powinno pojawić się urządzenie:

```text
MD Smart Hub
```

## Parowanie soundbara Bluetooth

1. Włącz soundbar w tryb parowania.
2. Na Raspberry:

```bash
cd ~/md-smart-hub
./scripts/bluetooth-scan.sh
```

3. Znajdź MAC soundbara.
4. Połącz:

```bash
./scripts/bluetooth-pair-connect.sh AA:BB:CC:DD:EE:FF
```

## Start z audio

Gdy Spotify Connect i soundbar są już ustawione:

```bash
./scripts/start-audio-app.sh
```

## Cel

Spotify → Raspberry Pi jako Spotify Connect → Bluetooth → Soundbar
