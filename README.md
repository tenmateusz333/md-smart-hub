# MD Smart Hub OS

## Aktualna wersja

v3.0 RC1.1 Fix

To jest kandydat testowy. RC1 skupia się na stabilnym froncie i Spotify API. Spotify Connect na Raspberry + Bluetooth soundbar będzie w RC2.

## Co zawiera RC1

- nowy układ 1024x600
- boczne menu
- nowy odtwarzacz Spotify
- przewijanie utworu
- wyszukiwarka Spotify
- otwieranie playlist
- lista utworów w playliście
- odtwarzanie utworu z playlisty
- wybór urządzenia Spotify
- nowa czytelna klawiatura ekranowa
- lepsze komunikaty błędów

## Po aktualizacji

```bash
cd ~/md-smart-hub
git pull
pkill -f server.py
python3 backend/server.py
```

Jeżeli Spotify działa dziwnie po aktualizacji:

1. W panelu kliknij `Reset`.
2. Kliknij `Autoryzuj`.
3. Zaakceptuj zgody Spotify.
4. Włącz muzykę na telefonie/komputerze.
5. W panelu wejdź w `Urządzenia` i odśwież.

## Spotify Redirect URI

W Spotify Developer Dashboard musi być:

```text
http://127.0.0.1:8765/callback
```


## Ważne po RC1.1

Po tej aktualizacji trzeba ponownie połączyć Spotify:

1. Otwórz panel.
2. Kliknij `Reset`.
3. Kliknij `Autoryzuj`.
4. Zaakceptuj zgody.
5. Sprawdź playlisty ponownie.

To jest potrzebne, bo playlisty wymagają nowych uprawnień Spotify.
