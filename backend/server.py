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
SCOPES = "user-read-playback-state user-read-currently-playing user-modify-playback-state playlist-read-private playlist-read-collaborative"

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

def http_json(url, method="GET", headers=None, data=None):
    headers = headers or {}
    body = None
    if data is not None:
        if isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=12) as res:
        raw = res.read()
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

def spotify_exchange_code(code, verifier):
    return http_json("https://accounts.spotify.com/api/token", method="POST", data={
        "client_id": CLIENT_ID,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    })

def spotify_refresh(tokens):
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return None
    new_tokens = http_json("https://accounts.spotify.com/api/token", method="POST", data={
        "client_id": CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    })
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
        data = http_json(url, method=method, headers=headers, data=payload)
        return data, 200
    except urllib.error.HTTPError as e:
        if e.code == 204:
            return {}, 204
        try:
            return json.loads(e.read().decode("utf-8")), e.code
        except Exception:
            return {"error": str(e)}, e.code
    except Exception as e:
        return {"error": str(e)}, 500

def friendly_spotify_error(code, data):
    if code == 401:
        return "Spotify wymaga ponownego połączenia. Kliknij Reset Spotify, potem Połącz Spotify."
    if code == 403:
        return "Spotify odmówił dostępu. Połącz Spotify ponownie i zaakceptuj nowe uprawnienia."
    if code == 404:
        return "Brak aktywnego urządzenia Spotify. Włącz muzykę na telefonie lub komputerze."
    if code == 429:
        return "Spotify chwilowo ograniczył zapytania. Spróbuj za moment."
    if isinstance(data, dict):
        msg = data.get("error", {})
        if isinstance(msg, dict):
            return msg.get("message") or str(msg)
        return str(msg)
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
    return {
        "connected": True,
        "playing_track": bool(item),
        "is_playing": data.get("is_playing", False),
        "track_name": item.get("name", "Brak tytułu"),
        "artist_name": ", ".join(a.get("name", "") for a in artists).strip() or "Nieznany wykonawca",
        "album_name": album.get("name", ""),
        "album_image": images[0]["url"] if images else None,
        "progress_ms": data.get("progress_ms", 0),
        "duration_ms": item.get("duration_ms", 0),
        "volume_percent": device.get("volume_percent"),
    }

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

    def read_body_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        if self.path == "/api/system":
            return self.json_response({
                "cpu_temp": cpu_temp(),
                "cpu_percent": cpu_percent(),
                "ram_percent": ram_percent(),
                "uptime_seconds": int(time.time() - BOOT_TIME),
                "online": is_online()
            })

        if self.path == "/api/spotify/status":
            return self.json_response(spotify_status())

        if self.path.startswith("/api/spotify/search"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("q", [""])[0]
            if not q.strip():
                return self.json_response({"items": []})
            data, code = spotify_api("/search?" + urllib.parse.urlencode({"q": q, "type": "track", "limit": "12"}))
            if code != 200:
                return self.json_response({"items": [], "error": friendly_spotify_error(code, data)})
            items = []
            for t in (data or {}).get("tracks", {}).get("items", []):
                album = t.get("album") or {}
                images = album.get("images") or []
                artists = t.get("artists") or []
                items.append({
                    "name": t.get("name"),
                    "subtitle": ", ".join(a.get("name","") for a in artists),
                    "uri": t.get("uri"),
                    "image": images[0]["url"] if images else None
                })
            return self.json_response({"items": items})

        if self.path == "/api/spotify/playlists":
            data, code = spotify_api("/me/playlists?limit=30")
            if code != 200:
                return self.json_response({"items": [], "error": friendly_spotify_error(code, data)})
            items = []
            for p in (data or {}).get("items", []):
                images = p.get("images") or []
                items.append({
                    "name": p.get("name"),
                    "subtitle": f"{p.get('tracks',{}).get('total',0)} utworów",
                    "uri": p.get("uri"),
                    "image": images[0]["url"] if images else None
                })
            return self.json_response({"items": items})

        if self.path == "/api/spotify/devices":
            data, code = spotify_api("/me/player/devices")
            if code != 200:
                return self.json_response({"items": [], "error": friendly_spotify_error(code, data)})
            items = []
            for d in (data or {}).get("devices", []):
                items.append({
                    "id": d.get("id"),
                    "name": d.get("name") + (" ✓" if d.get("is_active") else ""),
                    "subtitle": f"{d.get('type','device')} • {d.get('volume_percent','--')}%",
                    "image": None
                })
            return self.json_response({"items": items})

        if self.path == "/spotify/login":
            verifier, challenge = create_pkce_pair()
            state = secrets.token_urlsafe(24)
            write_json(SESSION_FILE, {"code_verifier": verifier, "state": state})
            params = {
                "client_id": CLIENT_ID,
                "response_type": "code",
                "redirect_uri": REDIRECT_URI,
                "code_challenge_method": "S256",
                "code_challenge": challenge,
                "state": state,
                "scope": SCOPES,
                "show_dialog": "true"
            }
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
                return self.json_response({"ok": code in (200, 204), "error": None if code in (200,204) else friendly_spotify_error(code, data)})
            if action == "previous":
                data, code = spotify_api("/me/player/previous", method="POST")
                return self.json_response({"ok": code in (200, 204), "error": None if code in (200,204) else friendly_spotify_error(code, data)})
            if action == "playpause":
                status = spotify_status()
                if not status.get("connected"):
                    return self.json_response({"ok": False, "error": "Spotify niepołączony"})
                if status.get("is_playing"):
                    data, code = spotify_api("/me/player/pause", method="PUT")
                else:
                    data, code = spotify_api("/me/player/play", method="PUT")
                return self.json_response({"ok": code in (200, 204), "error": None if code in (200,204) else friendly_spotify_error(code, data)})

        if self.path.startswith("/api/spotify/volume"):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            value = int(params.get("value", [50])[0])
            value = max(0, min(100, value))
            data, code = spotify_api(f"/me/player/volume?volume_percent={value}", method="PUT")
            return self.json_response({"ok": code in (200, 204), "error": None if code in (200,204) else friendly_spotify_error(code, data)})

        if self.path == "/api/spotify/play-track":
            body = self.read_body_json()
            uri = body.get("uri")
            data, code = spotify_api("/me/player/play", method="PUT", payload={"uris": [uri]})
            return self.json_response({"ok": code in (200, 204), "error": None if code in (200,204) else friendly_spotify_error(code, data)})

        if self.path == "/api/spotify/play-context":
            body = self.read_body_json()
            uri = body.get("uri")
            data, code = spotify_api("/me/player/play", method="PUT", payload={"context_uri": uri})
            return self.json_response({"ok": code in (200, 204), "error": None if code in (200,204) else friendly_spotify_error(code, data)})

        if self.path == "/api/spotify/transfer":
            body = self.read_body_json()
            device_id = body.get("id")
            data, code = spotify_api("/me/player", method="PUT", payload={"device_ids": [device_id], "play": False})
            return self.json_response({"ok": code in (200, 204), "error": None if code in (200,204) else friendly_spotify_error(code, data)})

        return self.json_response({"error": "Not found"}, 404)

if __name__ == "__main__":
    os.chdir(FRONTEND_ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("MD Smart Hub OS running at http://127.0.0.1:8765")
    server.serve_forever()
