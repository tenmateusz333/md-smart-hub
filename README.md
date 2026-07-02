# MD Smart Hub OS

Własny panel smart home na Raspberry Pi z ekranem dotykowym.

## Aktualna wersja

v2.2 Spotify Integration

## Spotify

Redirect URI w Spotify Developer Dashboard:

```text
http://127.0.0.1:8765/callback
```

Po uruchomieniu panelu kliknij `Połącz Spotify`.

## Test lokalny na Raspberry

```bash
cd ~/md-smart-hub
python3 backend/server.py
```

Potem:

```bash
chromium --kiosk http://127.0.0.1:8765
```
