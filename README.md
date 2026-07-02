# MD Smart Hub OS v4.4 Audio Stable

Ta wersja stabilizuje tor audio:

```text
Spotify → Raspberry Pi / MD Smart Hub → Bluetooth → Soundbar
```

## Co dodano

- głośność Spotify,
- głośność systemowa Raspberry,
- przycisk `Soundbar` w aplikacji,
- przycisk `Restart Connect`,
- lepszy ekran Audio,
- status Bluetooth,
- status Librespot,
- autostart audio.

## Aktualizacja

```bash
cd ~/md-smart-hub
git reset --hard
git pull
chmod +x scripts/*.sh
./scripts/install.sh
./scripts/start-audio-app.sh
```

## Autostart audio

Gdy wszystko działa, włącz autostart:

```bash
cd ~/md-smart-hub
./scripts/install-audio-autostart.sh
```

Po restarcie Raspberry powinno automatycznie:

1. połączyć soundbar Bluetooth,
2. uruchomić Spotify Connect,
3. uruchomić aplikację.

## Ważne

W ekranie Audio są teraz dwie głośności:

- `Głośność Spotify` — steruje poziomem Spotify,
- `Głośność systemowa Raspberry` — steruje końcowym wyjściem audio na soundbar.
