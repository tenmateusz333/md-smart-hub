# MD Smart Hub OS

Własny panel smart home na Raspberry Pi z ekranem dotykowym.

## Aktualna wersja

v2.1 Premium UI

## Struktura

- `frontend/` – interfejs użytkownika
- `backend/` – lokalny serwer i API Raspberry
- `docs/` – dokumentacja

## Test lokalny na Raspberry

```bash
cd ~/md-smart-hub
python3 backend/server.py
```

Potem otwórz:

```bash
chromium --kiosk http://127.0.0.1:8765
```
