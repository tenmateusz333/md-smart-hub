# MD Smart Hub OS

## Aktualna wersja

v2.3 Spotify Premium

## Spotify

Redirect URI:

```text
http://127.0.0.1:8765/callback
```

Po aktualizacji v2.3 kliknij ponownie `Połącz Spotify`, żeby zatwierdzić nowe uprawnienia do playlist.

## Test na Raspberry

```bash
cd ~/md-smart-hub
python3 backend/server.py
```

Potem:

```bash
chromium --kiosk http://127.0.0.1:8765
```
