# MD Smart Hub OS v4.2 Big Spotify Update

To jest większa aktualizacja aplikacyjnej wersji MD Smart Hub.

## Co zawiera

- aplikacja pełnoekranowa bez Chromium jako głównego interfejsu,
- dashboard,
- pogoda,
- system CPU/RAM/temp,
- Spotify logowanie,
- Spotify teraz gra,
- play/pauza,
- następny/poprzedni,
- przewijanie utworu przyciskami -15s / +15s,
- przebudowana wyszukiwarka,
- większa klawiatura ekranowa,
- pełne playlisty,
- otwieranie playlist,
- odtwarzanie playlisty,
- odtwarzanie utworu z playlisty,
- Spotify Debug.

## Uruchomienie na Raspberry

```bash
cd ~/md-smart-hub
git pull
chmod +x scripts/*.sh
./scripts/install.sh
./scripts/start-app.sh
```

## Ważne

Spotify Connect jako urządzenie Raspberry + Bluetooth soundbar będzie w kolejnym etapie.
