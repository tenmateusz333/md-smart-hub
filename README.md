# MD Smart Hub OS v4.1 Spotify Native

To jest wersja aplikacyjna z pierwszym natywnym modułem Spotify.

## Co zawiera

- aplikacja pełnoekranowa bez Chromium jako głównego interfejsu,
- dashboard,
- pogoda,
- system CPU/RAM/temp,
- Spotify logowanie PKCE,
- Spotify teraz gra,
- play/pauza,
- następny/poprzedni,
- wyszukiwarka Spotify,
- własna klawiatura ekranowa w aplikacji,
- ekran Spotify Debug.

## Uruchomienie na Raspberry

```bash
cd ~/md-smart-hub
git pull
chmod +x scripts/*.sh
./scripts/install.sh
./scripts/start-app.sh
```

## Logowanie Spotify

1. Otwórz aplikację.
2. Kliknij `Spotify`.
3. Kliknij `Autoryzuj`.
4. Otworzy się przeglądarka tylko do logowania.
5. Zaloguj się.
6. Po komunikacie `Spotify połączone` wróć do aplikacji.

## Ważne

W Spotify Developer Dashboard musi być ustawiony Redirect URI:

```text
http://127.0.0.1:8765/callback
```

## Kolejny etap

v4.2:
- playlisty,
- urządzenia Spotify,
- głośność,
- przewijanie utworu,
- lepszy ekran odtwarzacza.
