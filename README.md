# MD Smart Hub OS v4.0 Alpha App Edition

To jest pierwsza wersja aplikacji pełnoekranowej, bez Chromium i bez serwera strony internetowej.

## Co zawiera

- natywna aplikacja Python/Tkinter,
- pełny ekran 1024x600,
- dashboard,
- zegar,
- pogoda,
- CPU/RAM/temp,
- ekran ustawień,
- przygotowanie pod Spotify Native w v4.1.

## Uruchomienie na Raspberry

Po wrzuceniu paczki do repozytorium i `git pull`:

```bash
cd ~/md-smart-hub
chmod +x scripts/*.sh
./scripts/install.sh
./scripts/start-app.sh
```

## Wyjście z pełnego ekranu

- `ESC` wyłącza pełny ekran,
- `F11` przełącza pełny ekran,
- w ustawieniach jest przycisk zamykania aplikacji.

## Autostart

Po przetestowaniu możesz włączyć autostart:

```bash
./scripts/install-autostart.sh
```

## Ważne

To jest wersja Alpha. Spotify jeszcze nie jest przeniesione. Wróci w v4.1 jako natywny moduł aplikacji.
