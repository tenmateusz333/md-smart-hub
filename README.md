# MD Smart Hub OS

## Aktualna wersja

v2.4 Spotify Complete

## Ważne po aktualizacji

Po wgraniu v2.4 kliknij w panelu:

```text
Reset Spotify
```

Potem:

```text
Połącz Spotify / Autoryzuj
```

Spotify musi pokazać ekran zgody z nowymi uprawnieniami.

## Spotify Redirect URI

W Spotify Developer Dashboard musi być:

```text
http://127.0.0.1:8765/callback
```

## Test na Raspberry

```bash
cd ~/md-smart-hub
pkill -f server.py
python3 backend/server.py
```

Potem:

```bash
chromium --kiosk http://127.0.0.1:8765
```
