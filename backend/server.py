#!/usr/bin/env python3
import base64, hashlib, json, os, secrets, subprocess, time, urllib.parse, urllib.request, urllib.error
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
DATA_ROOT = PROJECT_ROOT / "data"
DATA_ROOT.mkdir(exist_ok=True)

CLIENT_ID = "7671855d0ad548d2bbdb2c49c386fa2b"
REDIRECT_URI = "http://127.0.0.1:8765/callback"
SCOPES = "user-read-private user-read-playback-state user-read-currently-playing user-modify-playback-state playlist-read-private playlist-read-collaborative user-read-recently-played user-library-read"
TOKENS_FILE = DATA_ROOT / "spotify_tokens.json"
SESSION_FILE = DATA_ROOT / "spotify_session.json"
BOOT_TIME = time.time()
_last_cpu = None

def read_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def write_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def b64url(data):
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def create_pkce_pair():
    verifier = b64url(secrets.token_bytes(64))
    challenge = b64url(hashlib.sha256(verifier.encode("utf-8")).digest())
    return verifier, challenge

def http_json(url, method="GET", headers=None, form=None, json_data=None):
    headers = headers or {}
    body = None
    if form is not None:
        body = urllib.parse.urlencode(form).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if json_data is not None:
        body = json.dumps(json_data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=14) as res:
        raw = res.read()
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

def spotify_exchange_code(code, verifier):
    return http_json("https://accounts.spotify.com/api/token", method="POST", form={"client_id": CLIENT_ID, "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI, "code_verifier": verifier})

def spotify_refresh(tokens):
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return None
    new_tokens = http_json("https://accounts.spotify.com/api/token", method="POST", form={"client_id": CLIENT_ID, "grant_type": "refresh_token", "refresh_token": refresh_token})
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = refresh_token
    new_tokens["expires_at"] = time.time() + int(new_tokens.get("expires_in", 3600)) - 60
    write_json(TOKENS_FILE, new_tokens)
    return new_tokens

def spotify_tokens():
    tokens = read_json(TOKENS_FILE, None)
    if not tokens:
        return None
    if time.time() > tokens.get("expires_at", 0):
        try:
            return spotify_refresh(tokens)
        except Exception:
            return None
    return tokens

def spotify_api(path, method="GET", payload=None):
    tokens = spotify_tokens()
    if not tokens:
        return None, 401
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    url = f"https://api.spotify.com/v1{path}"
    try:
        data = http_json(url, method=method, headers=headers, json_data=payload)
        return data, 200
    except urllib.error.HTTPError as e:
        if e.code == 204:
            return {}, 204
        try:
            raw = e.read().decode("utf-8")
            return json.loads(raw) if raw else {}, e.code
        except Exception:
            return {"error": str(e)}, e.code
    except Exception as e:
        return {"error": str(e)}, 500

def friendly_spotify_error(code, data):
    if code == 401:
        return "Spotify wymaga ponownego połączenia. Kliknij Reset, potem Autoryzuj."
    if code == 403:
        return "Spotify odmówił dostępu do tej funkcji. Kliknij Reset, potem Autoryzuj i zaakceptuj nowe uprawnienia."
    if code == 404:
        return "Brak aktywnego urządzenia Spotify. Włącz Spotify na telefonie lub komputerze."
    if code == 429:
        return "Spotify ograniczył zapytania. Spróbuj za chwilę."
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            return err.get("message", str(err))
        if isinstance(err, str):
            return err
    return "Nieznany błąd Spotify."

def spotify_status():
    tokens = spotify_tokens()
    if not tokens:
        return {"connected": False}
    data, code = spotify_api("/me/player", "GET")
    if code == 204 or not data:
        return {"connected": True, "playing_track": False, "message": "Brak aktywnego urządzenia. Włącz muzykę w Spotify."}
    if code != 200:
        return {"connected": True, "playing_track": False, "message": friendly_spotify_error(code, data)}
    item = data.get("item") or {}
    album = item.get("album") or {}
    images = album.get("images") or []
    artists = item.get("artists") or []
    device = data.get("device") or {}
    return {"connected": True, "playing_track": bool(item), "is_playing": data.get("is_playing", False), "track_name": item.get("name", "Brak tytułu"), "artist_name": ", ".join(a.get("name", "") for a in artists).strip() or "Nieznany wykonawca", "album_image": images[0]["url"] if images else None, "progress_ms": data.get("progress_ms", 0), "duration_ms": item.get("duration_ms", 0), "volume_percent": device.get("volume_percent")}

def run_cmd(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""

def cpu_temp():
    out = run_cmd("vcgencmd measure_temp")
    if out.startswith("temp="):
        return float(out.replace("temp=", "").replace("'C", ""))
    p = Path("/sys/class/thermal/thermal_zone0/temp")
    if p.exists():
        return round(int(p.read_text().strip()) / 1000, 1)
    return 0.0

def ram_percent():
    meminfo = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, val = line.split(":", 1)
        meminfo[key] = int(val.strip().split()[0])
    total = meminfo.get("MemTotal", 1)
    available = meminfo.get("MemAvailable", 0)
    return round(((total - available) / total) * 100, 1)

def read_cpu_times():
    line = Path("/proc/stat").read_text().splitlines()[0]
    parts = [int(x) for x in line.split()[1:]]
    idle = parts[3] + parts[4]
    total = sum(parts)
    return idle, total

def cpu_percent():
    global _last_cpu
    now = read_cpu_times()
    if _last_cpu is None:
        _last_cpu = now
        time.sleep(0.1)
        now = read_cpu_times()
    idle_delta = now[0] - _last_cpu[0]
    total_delta = now[1] - _last_cpu[1]
    _last_cpu = now
    if total_delta <= 0:
        return 0.0
    return round((1 - idle_delta / total_delta) * 100, 1)

def is_online():
    return os.system("ping -c 1 -W 1 1.1.1.1 > /dev/null 2>&1") == 0

def read_body(handler):
    length = int(handler.headers.get("Content-Length", 0))
    if length <= 0:
        return {}
    try:
        return json.loads(handler.rfile.read(length).decode("utf-8"))
    except Exception:
        return {}

class Handler(SimpleHTTPRequestHandler):
    def json_response(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, url):
        self.send_response(302)
        self.send_header("Location", url)
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/system":
            return self.json_response({"cpu_temp": cpu_temp(), "cpu_percent": cpu_percent(), "ram_percent": ram_percent(), "uptime_seconds": int(time.time() - BOOT_TIME), "online": is_online()})
        if self.path == "/api/spotify/status":
            return self.json_response(spotify_status())

        if self.path.startswith("/api/spotify/search"):
            parsed = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(parsed.query).get("q", [""])[0].strip()
            if not q:
                return self.json_response({"items": []})
            query = urllib.parse.urlencode({"q": q, "type": "track", "limit": 10})
            data, code = spotify_api(f"/search?{query}")
            if code != 200:
                return self.json_response({"items": [], "error": friendly_spotify_error(code, data)})
            items = []
            for track in (data or {}).get("tracks", {}).get("items", []):
                album = track.get("album") or {}
                images = album.get("images") or []
                artists = track.get("artists") or []
                items.append({"name": track.get("name"), "subtitle": ", ".join(a.get("name", "") for a in artists), "uri": track.get("uri"), "image": images[0]["url"] if images else None})
            return self.json_response({"items": items})

        if self.path == "/api/spotify/playlists":
            data, code = spotify_api("/me/playlists?limit=30")
            if code != 200:
                return self.json_response({"items": [], "error": friendly_spotify_error(code, data)})
            items = []
            for playlist in (data or {}).get("items", []):
                images = playlist.get("images") or []
                tracks = playlist.get("tracks") or {}
                items.append({"id": playlist.get("id"), "name": playlist.get("name"), "subtitle": f"{tracks.get('total', 0)} utworów", "uri": playlist.get("uri"), "image": images[0]["url"] if images else None})
            return self.json_response({"items": items})

        if self.path.startswith("/api/spotify/playlist/") and self.path.endswith("/tracks"):
            playlist_id = playlist_id_from_path(self.path)

            if not playlist_id:
                return self.json_response({"items": [], "error": "Brak ID playlisty"})

            # RC1.3: use the simplest endpoint first. If Spotify refuses, return a diagnostic code.
            query = urllib.parse.urlencode({"limit": 50})
            data, code = spotify_api(f"/playlists/{playlist_id}/tracks?{query}")

            # Some Spotify playlist items can fail when a track is unavailable. Keep the API call simple.
            if code != 200:
                try:
                    raw = json.dumps(data, ensure_ascii=False)[:320]
                except Exception:
                    raw = str(data)[:320]

                return self.json_response({
                    "items": [],
                    "error": f"{friendly_spotify_error(code, data)} Kod: {code}. Szczegóły: {raw}"
                })

            items = []
            for entry in (data or {}).get("items", []):
                track = entry.get("track") or {}

                if not track or track.get("type") != "track":
                    continue

                album = track.get("album") or {}
                images = album.get("images") or []
                artists = track.get("artists") or []

                if not track.get("uri"):
                    continue

                items.append({
                    "name": track.get("name"),
                    "subtitle": ", ".join(a.get("name", "") for a in artists),
                    "uri": track.get("uri"),
                    "image": images[0]["url"] if images else None
                })

            return self.json_response({"items": items})

        if self.path == "/api/spotify/devices":
            data, code = spotify_api("/me/player/devices")
            if code != 200:
                return self.json_response({"items": [], "error": friendly_spotify_error(code, data)})
            items = []
            for d in (data or {}).get("devices", []):
                items.append({"id": d.get("id"), "name": d.get("name") + (" ✓" if d.get("is_active") else ""), "subtitle": f"{d.get('type', 'device')} • {d.get('volume_percent', '--')}%", "image": None})
            return self.json_response({"items": items})


        if self.path == "/api/debug/version":
            tokens = read_json(TOKENS_FILE, {})
            return self.json_response({
                "version": "v3.0 RC1.3",
                "scope": tokens.get("scope", ""),
                "playlist_route": "diagnostic-v2"
            })

        if self.path == "/spotify/login":
            verifier, challenge = create_pkce_pair()
            state = secrets.token_urlsafe(24)
            write_json(SESSION_FILE, {"code_verifier": verifier, "state": state})
            params = {"client_id": CLIENT_ID, "response_type": "code", "redirect_uri": REDIRECT_URI, "code_challenge_method": "S256", "code_challenge": challenge, "state": state, "scope": SCOPES, "show_dialog": "true"}
            return self.redirect("https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params))

        if self.path.startswith("/callback"):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code = params.get("code", [None])[0]
            state = params.get("state", [None])[0]
            session = read_json(SESSION_FILE, {})
            if not code or state != session.get("state"):
                return self.json_response({"error": "Invalid Spotify callback"}, 400)
            try:
                tokens = spotify_exchange_code(code, session["code_verifier"])
                tokens["expires_at"] = time.time() + int(tokens.get("expires_in", 3600)) - 60
                write_json(TOKENS_FILE, tokens)
                return self.redirect("/")
            except Exception as e:
                return self.json_response({"error": str(e)}, 500)
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/spotify/logout":
            if TOKENS_FILE.exists():
                TOKENS_FILE.unlink()
            if SESSION_FILE.exists():
                SESSION_FILE.unlink()
            return self.json_response({"ok": True})

        if self.path.startswith("/api/spotify/control/"):
            action = self.path.split("/")[-1]
            if action == "next":
                data, code = spotify_api("/me/player/next", method="POST")
            elif action == "previous":
                data, code = spotify_api("/me/player/previous", method="POST")
            elif action == "playpause":
                status = spotify_status()
                if not status.get("connected"):
                    return self.json_response({"ok": False, "error": "Spotify niepołączony"})
                if status.get("is_playing"):
                    data, code = spotify_api("/me/player/pause", method="PUT")
                else:
                    data, code = spotify_api("/me/player/play", method="PUT")
            else:
                return self.json_response({"ok": False, "error": "Nieznana akcja"})
            return self.json_response({"ok": code in (200, 204), "error": None if code in (200, 204) else friendly_spotify_error(code, data)})

        if self.path.startswith("/api/spotify/volume"):
            value = int(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("value", [50])[0])
            value = max(0, min(100, value))
            data, code = spotify_api(f"/me/player/volume?volume_percent={value}", method="PUT")
            return self.json_response({"ok": code in (200, 204), "error": None if code in (200, 204) else friendly_spotify_error(code, data)})

        if self.path.startswith("/api/spotify/seek"):
            position_ms = int(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("position_ms", [0])[0])
            position_ms = max(0, position_ms)
            data, code = spotify_api(f"/me/player/seek?position_ms={position_ms}", method="PUT")
            return self.json_response({"ok": code in (200, 204), "error": None if code in (200, 204) else friendly_spotify_error(code, data)})

        if self.path == "/api/spotify/play-track":
            body = read_body(self)
            data, code = spotify_api("/me/player/play", method="PUT", payload={"uris": [body.get("uri")]})
            return self.json_response({"ok": code in (200, 204), "error": None if code in (200, 204) else friendly_spotify_error(code, data)})

        if self.path == "/api/spotify/play-context":
            body = read_body(self)
            data, code = spotify_api("/me/player/play", method="PUT", payload={"context_uri": body.get("uri")})
            return self.json_response({"ok": code in (200, 204), "error": None if code in (200, 204) else friendly_spotify_error(code, data)})

        if self.path == "/api/spotify/play-from-context":
            body = read_body(self)
            data, code = spotify_api("/me/player/play", method="PUT", payload={"context_uri": body.get("context_uri"), "offset": {"uri": body.get("track_uri")}})
            return self.json_response({"ok": code in (200, 204), "error": None if code in (200, 204) else friendly_spotify_error(code, data)})

        if self.path == "/api/spotify/transfer":
            body = read_body(self)
            data, code = spotify_api("/me/player", method="PUT", payload={"device_ids": [body.get("id")], "play": False})
            return self.json_response({"ok": code in (200, 204), "error": None if code in (200, 204) else friendly_spotify_error(code, data)})

        return self.json_response({"error": "Not found"}, 404)

if __name__ == "__main__":
    os.chdir(FRONTEND_ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("MD Smart Hub OS v3.0 RC1.3 running at http://127.0.0.1:8765")
    server.serve_forever()
