#!/usr/bin/env python3
import base64
import hashlib
import json
import os
import re
import secrets
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tkinter as tk
from tkinter import font as tkfont

APP_VERSION = "v4.4 Audio Stable"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data"
CONFIG_PATH = DATA_ROOT / "config.json"
TOKENS_PATH = DATA_ROOT / "spotify_tokens.json"
SESSION_PATH = DATA_ROOT / "spotify_session.json"

CLIENT_ID = "7671855d0ad548d2bbdb2c49c386fa2b"
REDIRECT_URI = "http://127.0.0.1:8765/callback"
SCOPES = (
    "user-read-private "
    "user-read-playback-state "
    "user-read-currently-playing "
    "user-modify-playback-state "
    "playlist-read-private "
    "playlist-read-collaborative "
    "user-read-recently-played "
    "user-library-read"
)

DEFAULT_CONFIG = {
    "city": "Warszawa",
    "latitude": 52.2297,
    "longitude": 21.0122,
    "fullscreen": True
}

BOOT_TIME = time.time()


def load_config():
    DATA_ROOT.mkdir(exist_ok=True)

    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
        return DEFAULT_CONFIG.copy()

    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        merged = DEFAULT_CONFIG.copy()
        merged.update(data)
        return merged
    except Exception:
        return DEFAULT_CONFIG.copy()


CONFIG = load_config()


def read_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def write_json(path, data):
    DATA_ROOT.mkdir(exist_ok=True)
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
    return http_json(
        "https://accounts.spotify.com/api/token",
        method="POST",
        form={
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        },
    )


def spotify_refresh(tokens):
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return None

    new_tokens = http_json(
        "https://accounts.spotify.com/api/token",
        method="POST",
        form={
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )

    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = refresh_token

    new_tokens["expires_at"] = time.time() + int(new_tokens.get("expires_in", 3600)) - 60
    write_json(TOKENS_PATH, new_tokens)
    return new_tokens


def spotify_tokens():
    tokens = read_json(TOKENS_PATH, None)

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
        return "Spotify wymaga ponownego logowania."
    if code == 403:
        return "Spotify odmówił dostępu. Zrób Reset i Autoryzuj."
    if code == 404:
        return "Brak aktywnego urządzenia Spotify. Włącz Spotify na telefonie lub komputerze."
    if code == 429:
        return "Spotify ograniczył zapytania. Spróbuj za chwilę."

    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            return error.get("message", str(error))
        if isinstance(error, str):
            return error

    return f"Błąd Spotify {code}"


def spotify_status():
    tokens = spotify_tokens()

    if not tokens:
        return {
            "connected": False,
            "playing_track": False,
            "message": "Nie połączono Spotify."
        }

    data, code = spotify_api("/me/player", "GET")

    if code == 204 or not data:
        return {
            "connected": True,
            "playing_track": False,
            "message": "Brak aktywnego urządzenia. Włącz muzykę w Spotify."
        }

    if code != 200:
        return {
            "connected": True,
            "playing_track": False,
            "message": friendly_spotify_error(code, data)
        }

    item = data.get("item") or {}
    album = item.get("album") or {}
    artists = item.get("artists") or []
    device = data.get("device") or {}

    return {
        "connected": True,
        "playing_track": bool(item),
        "is_playing": data.get("is_playing", False),
        "track_name": item.get("name", "Brak tytułu"),
        "artist_name": ", ".join(a.get("name", "") for a in artists).strip() or "Nieznany wykonawca",
        "progress_ms": data.get("progress_ms", 0),
        "duration_ms": item.get("duration_ms", 0),
        "volume_percent": device.get("volume_percent"),
        "device_name": device.get("name", "Brak urządzenia"),
        "message": ""
    }


class SpotifyCallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]
        session = read_json(SESSION_PATH, {})

        html_ok = """
        <html><body style="font-family:Arial;background:#05070d;color:white;text-align:center;padding-top:80px">
        <h1>Spotify połączone</h1>
        <p>Możesz wrócić do MD Smart Hub.</p>
        </body></html>
        """

        html_error = """
        <html><body style="font-family:Arial;background:#05070d;color:white;text-align:center;padding-top:80px">
        <h1>Błąd Spotify</h1>
        <p>Wróć do MD Smart Hub i spróbuj ponownie.</p>
        </body></html>
        """

        try:
            if not code or state != session.get("state"):
                raise RuntimeError("Nieprawidłowy callback Spotify")

            tokens = spotify_exchange_code(code, session["code_verifier"])
            tokens["expires_at"] = time.time() + int(tokens.get("expires_in", 3600)) - 60
            write_json(TOKENS_PATH, tokens)

            body = html_ok.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            body = html_error.encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


_callback_server = None


def ensure_callback_server():
    global _callback_server

    if _callback_server is not None:
        return

    _callback_server = ThreadingHTTPServer(("127.0.0.1", 8765), SpotifyCallbackHandler)
    threading.Thread(target=_callback_server.serve_forever, daemon=True).start()


def run_cmd(cmd):
    try:
        return subprocess.check_output(
            cmd,
            shell=True,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2
        ).strip()
    except Exception:
        return ""


def cpu_temp():
    out = run_cmd("vcgencmd measure_temp")
    if out.startswith("temp="):
        try:
            return float(out.replace("temp=", "").replace("'C", ""))
        except Exception:
            pass

    p = Path("/sys/class/thermal/thermal_zone0/temp")
    if p.exists():
        try:
            return round(int(p.read_text().strip()) / 1000, 1)
        except Exception:
            pass

    return 0.0


def ram_percent():
    try:
        meminfo = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, val = line.split(":", 1)
            meminfo[key] = int(val.strip().split()[0])

        total = meminfo.get("MemTotal", 1)
        available = meminfo.get("MemAvailable", 0)
        return round(((total - available) / total) * 100, 1)
    except Exception:
        return 0.0


class CpuSampler:
    def __init__(self):
        self.last = None

    def read(self):
        try:
            line = Path("/proc/stat").read_text().splitlines()[0]
            parts = [int(x) for x in line.split()[1:]]
            idle = parts[3] + parts[4]
            total = sum(parts)
            return idle, total
        except Exception:
            return 0, 0

    def percent(self):
        now = self.read()

        if self.last is None:
            self.last = now
            return 0.0

        idle_delta = now[0] - self.last[0]
        total_delta = now[1] - self.last[1]
        self.last = now

        if total_delta <= 0:
            return 0.0

        return round((1 - idle_delta / total_delta) * 100, 1)


CPU = CpuSampler()


def is_online():
    return os.system("ping -c 1 -W 1 1.1.1.1 > /dev/null 2>&1") == 0


def weather_icon(code):
    if code == 0:
        return "☀"
    if code in (1, 2):
        return "◐"
    if code == 3:
        return "☁"
    if code in (45, 48):
        return "≋"
    if code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        return "☂"
    if code in (71, 73, 75, 77, 85, 86):
        return "❄"
    if code in (95, 96, 99):
        return "⚡"
    return "◐"


def weather_text(code):
    if code == 0:
        return "Bezchmurnie"
    if code in (1, 2):
        return "Częściowe zachmurzenie"
    if code == 3:
        return "Pochmurno"
    if code in (45, 48):
        return "Mgła"
    if code in (51, 53, 55):
        return "Mżawka"
    if code in (61, 63, 65, 80, 81, 82):
        return "Deszcz"
    if code in (71, 73, 75, 77, 85, 86):
        return "Śnieg"
    if code in (95, 96, 99):
        return "Burza"
    return "Pogoda"


def fetch_weather():
    lat = CONFIG["latitude"]
    lon = CONFIG["longitude"]
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,weather_code,wind_speed_10m"
        "&timezone=auto"
    )

    with urllib.request.urlopen(url, timeout=7) as response:
        data = json.loads(response.read().decode("utf-8"))

    current = data.get("current", {})
    temp = round(float(current.get("temperature_2m", 0)))
    code = int(current.get("weather_code", 0))
    wind = round(float(current.get("wind_speed_10m", 0)))

    return {
        "temp": temp,
        "code": code,
        "icon": weather_icon(code),
        "text": weather_text(code),
        "wind": wind
    }


def fmt_ms(ms):
    try:
        ms = int(ms or 0)
    except Exception:
        ms = 0

    total = max(0, ms // 1000)
    minutes = total // 60
    seconds = total % 60
    return f"{minutes}:{seconds:02d}"



def spotify_search_tracks(query, limit=8):
    q = urllib.parse.urlencode({"q": query, "type": "track", "limit": limit})
    data, code = spotify_api(f"/search?{q}")

    if code != 200:
        return [], friendly_spotify_error(code, data)

    items = []
    for track in (data or {}).get("tracks", {}).get("items", []):
        artists = track.get("artists") or []
        items.append({
            "name": track.get("name", "Bez tytułu"),
            "artist": ", ".join(a.get("name", "") for a in artists),
            "uri": track.get("uri")
        })

    return items, None


def spotify_get_playlists(limit=30):
    data, code = spotify_api(f"/me/playlists?limit={limit}")

    if code != 200:
        return [], friendly_spotify_error(code, data)

    playlists = []
    for playlist in (data or {}).get("items", []):
        tracks = playlist.get("tracks") or {}
        playlists.append({
            "id": playlist.get("id"),
            "name": playlist.get("name") or "Bez nazwy",
            "uri": playlist.get("uri"),
            "total": tracks.get("total", 0)
        })

    return playlists, None


def spotify_get_playlist_tracks(playlist_id, limit=50):
    attempts = [
        f"/playlists/{playlist_id}/tracks?" + urllib.parse.urlencode({"limit": limit}),
        f"/playlists/{playlist_id}/tracks?" + urllib.parse.urlencode({"limit": limit, "market": "from_token"}),
        f"/playlists/{playlist_id}/tracks?" + urllib.parse.urlencode({
            "limit": limit,
            "market": "from_token",
            "additional_types": "track,episode"
        }),
        f"/playlists/{playlist_id}?"
        + urllib.parse.urlencode({
            "fields": "tracks(total,items(track(name,uri,type,artists(name),album(name))))"
        }),
    ]

    last_code = None
    last_data = None
    empty_successes = 0

    for path in attempts:
        data, code = spotify_api(path)
        last_code = code
        last_data = data

        if code != 200:
            continue

        if "tracks" in (data or {}) and isinstance((data or {}).get("tracks"), dict):
            entries = ((data or {}).get("tracks") or {}).get("items", [])
        else:
            entries = (data or {}).get("items", [])

        if not entries:
            empty_successes += 1
            continue

        tracks = []

        for entry in entries:
            track = (entry or {}).get("track") or {}

            if not track:
                continue

            uri = track.get("uri")
            name = track.get("name")

            if not uri and not name:
                continue

            artists = track.get("artists") or []

            tracks.append({
                "name": name or "Bez tytułu",
                "artist": ", ".join(a.get("name", "") for a in artists if a.get("name")),
                "uri": uri
            })

        if tracks:
            return tracks, None

        empty_successes += 1

    if empty_successes > 0:
        return [], (
            "Spotify zwrócił pustą listę utworów dla tej playlisty, mimo że odtwarzanie może działać. "
            "Aplikacja próbowała kilku metod pobierania. Użyj przycisku Play u góry, żeby odtworzyć całą playlistę."
        )

    message = friendly_spotify_error(last_code, last_data)
    return [], (
        f"{message}\n\n"
        "Spotify pozwala odtworzyć tę playlistę, ale nie pozwala aplikacji odczytać listy utworów przez API. "
        "Użyj przycisku Play u góry — odtwarzanie playlisty powinno działać."
    )


def spotify_get_devices():
    data, code = spotify_api("/me/player/devices")

    if code != 200:
        return [], friendly_spotify_error(code, data)

    devices = []
    for device in (data or {}).get("devices", []):
        devices.append({
            "id": device.get("id"),
            "name": device.get("name") or "Urządzenie",
            "type": device.get("type") or "device",
            "is_active": bool(device.get("is_active")),
            "volume_percent": device.get("volume_percent")
        })

    return devices, None


def spotify_set_volume(value):
    value = max(0, min(100, int(value)))
    data, code = spotify_api(f"/me/player/volume?volume_percent={value}", method="PUT")
    if code in (200, 204):
        return True, None
    return False, friendly_spotify_error(code, data)


def spotify_transfer_device(device_id, play=False):
    data, code = spotify_api("/me/player", method="PUT", payload={
        "device_ids": [device_id],
        "play": bool(play)
    })

    if code in (200, 204):
        return True, None

    return False, friendly_spotify_error(code, data)


def service_status(service_name):
    out = run_cmd(f"systemctl --user is-active {service_name}")
    return out or "unknown"


def command_exists(name):
    return bool(run_cmd(f"command -v {name}"))


def bluetooth_saved_mac():
    p = DATA_ROOT / "soundbar_mac.txt"
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return ""


def bluetooth_status():
    mac = bluetooth_saved_mac()
    if not mac:
        return "Brak zapisanego soundbara"

    info = run_cmd(f"bluetoothctl info {mac}")
    if "Connected: yes" in info:
        return f"Połączony: {mac}"
    if "Paired: yes" in info:
        return f"Zapamiętany, niepołączony: {mac}"
    return f"Zapisany MAC: {mac}"

def system_volume_get():
    out = run_cmd("pactl get-sink-volume @DEFAULT_SINK@")
    if out:
        m = re.search(r"(\d+)%", out)
        if m:
            return int(m.group(1))
    out = run_cmd("wpctl get-volume @DEFAULT_AUDIO_SINK@")
    if out:
        m = re.search(r"Volume:\s*([0-9.]+)", out)
        if m:
            return int(float(m.group(1)) * 100)
    out = run_cmd("amixer get Master")
    if out:
        m = re.search(r"\[(\d+)%\]", out)
        if m:
            return int(m.group(1))
    return None

def system_volume_set(value):
    value = max(0, min(100, int(value)))
    if command_exists("pactl"):
        if os.system(f"pactl set-sink-volume @DEFAULT_SINK@ {value}% >/dev/null 2>&1") == 0:
            return True
    if command_exists("wpctl"):
        if os.system(f"wpctl set-volume @DEFAULT_AUDIO_SINK@ {value/100:.2f} >/dev/null 2>&1") == 0:
            return True
    if command_exists("amixer"):
        if os.system(f"amixer set Master {value}% >/dev/null 2>&1") == 0:
            return True
    return False

def restart_user_service(service_name):
    return os.system(f"systemctl --user restart {service_name} >/dev/null 2>&1") == 0

def connect_saved_soundbar():
    mac = bluetooth_saved_mac()
    if not mac:
        return False, "Brak zapisanego MAC soundbara."
    os.system("bluetoothctl power on >/dev/null 2>&1")
    os.system(f"bluetoothctl trust {mac} >/dev/null 2>&1")
    rc = os.system(f"bluetoothctl connect {mac} >/dev/null 2>&1")
    if rc == 0:
        return True, f"Połączono soundbar {mac}"
    return False, f"Nie udało się połączyć soundbara {mac}"



class SmartHubApp:
    def __init__(self, root):
        self.root = root
        self.screen = "home"
        self.weather_data = {
            "temp": "--",
            "icon": "◐",
            "text": "Ładowanie...",
            "wind": "--"
        }

        self.spotify_last = spotify_status()
        self.search_query = ""
        self.search_results = []
        self.playlists = []
        self.playlist_tracks = []
        self.current_playlist_uri = None
        self.current_playlist_name = ""

        self.colors = {
            "bg": "#05070d",
            "panel": "#101827",
            "panel2": "#172033",
            "card": "#121d30",
            "text": "#f7fbff",
            "muted": "#94a3b8",
            "green": "#1ed760",
            "blue": "#62d5ff",
            "red": "#ff5c7a",
            "warn": "#ffb020"
        }

        self.root.title("MD Smart Hub OS")
        self.root.geometry("1024x600")
        self.root.configure(bg=self.colors["bg"])
        self.root.attributes("-fullscreen", bool(CONFIG.get("fullscreen", True)))
        self.root.bind("<Escape>", lambda event: self.root.attributes("-fullscreen", False))
        self.root.bind("<F11>", lambda event: self.toggle_fullscreen())

        self.font_big = tkfont.Font(family="Arial", size=34, weight="bold")
        self.font_h1 = tkfont.Font(family="Arial", size=28, weight="bold")
        self.font_h2 = tkfont.Font(family="Arial", size=20, weight="bold")
        self.font_body = tkfont.Font(family="Arial", size=14)
        self.font_small = tkfont.Font(family="Arial", size=11)
        self.font_tiny = tkfont.Font(family="Arial", size=9)
        self.font_tile_icon = tkfont.Font(family="Arial", size=28, weight="bold")

        self.build_layout()
        self.show_home()
        self.tick_clock()
        self.tick_system()
        self.tick_spotify()
        self.start_weather_loop()

    def toggle_fullscreen(self):
        current = bool(self.root.attributes("-fullscreen"))
        self.root.attributes("-fullscreen", not current)

    def build_layout(self):
        self.sidebar = tk.Frame(self.root, bg=self.colors["panel"], width=76)
        self.sidebar.pack(side="left", fill="y", padx=(10, 6), pady=10)
        self.sidebar.pack_propagate(False)

        self.main = tk.Frame(self.root, bg=self.colors["bg"])
        self.main.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=10)

        self.topbar = tk.Frame(self.main, bg=self.colors["bg"], height=64)
        self.topbar.pack(fill="x")
        self.topbar.pack_propagate(False)

        self.time_label = tk.Label(
            self.topbar,
            text="--:--",
            font=self.font_big,
            bg=self.colors["bg"],
            fg=self.colors["text"]
        )
        self.time_label.pack(side="left", anchor="w")

        self.date_label = tk.Label(
            self.topbar,
            text="Ładowanie...",
            font=self.font_small,
            bg=self.colors["bg"],
            fg=self.colors["muted"]
        )
        self.date_label.pack(side="left", anchor="s", padx=12, pady=12)

        self.status_label = tk.Label(
            self.topbar,
            text="Wi‑Fi • Spotify • CPU --°C • MD",
            font=self.font_small,
            bg=self.colors["panel"],
            fg=self.colors["text"],
            padx=14,
            pady=8
        )
        self.status_label.pack(side="right", anchor="e", pady=12)

        self.content = tk.Frame(self.main, bg=self.colors["bg"])
        self.content.pack(fill="both", expand=True)

        self.footer = tk.Frame(self.main, bg=self.colors["panel"], height=42)
        self.footer.pack(fill="x", pady=(8, 0))
        self.footer.pack_propagate(False)

        self.version_label = tk.Label(
            self.footer,
            text=f"MD Smart Hub OS {APP_VERSION}",
            font=self.font_small,
            bg=self.colors["panel"],
            fg=self.colors["text"]
        )
        self.version_label.pack(side="left", padx=12)

        self.toast_label = tk.Label(
            self.footer,
            text="Aplikacja gotowa",
            font=self.font_small,
            bg=self.colors["panel"],
            fg=self.colors["muted"]
        )
        self.toast_label.pack(side="left", padx=16)

        self.build_nav()

    def build_nav(self):
        buttons = [
            ("⌂", "home", self.show_home),
            ("♫", "spotify", self.show_spotify),
            ("⌕", "search", self.show_spotify_search),
            ("☷", "playlists", self.show_playlists),
            ("🔊", "audio", self.show_audio),
            ("▣", "system", self.show_system),
            ("⚙", "settings", self.show_settings),
        ]

        for icon, name, command in buttons:
            btn = tk.Button(
                self.sidebar,
                text=icon,
                font=self.font_tile_icon,
                bg=self.colors["panel2"],
                fg=self.colors["text"],
                activebackground=self.colors["green"],
                activeforeground="#041107",
                relief="flat",
                command=command
            )
            btn.pack(fill="both", expand=True, padx=8, pady=4)
            btn.name = name

    def clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()

    def toast(self, text):
        self.toast_label.configure(text=text)
        self.root.after(3500, lambda: self.toast_label.configure(text="Aplikacja gotowa"))

    def card(self, parent, **grid):
        frame = tk.Frame(parent, bg=self.colors["panel"], highlightthickness=1, highlightbackground="#243244")
        frame.grid(**grid)
        return frame

    def button(self, parent, text, command, bg=None, fg=None, **pack):
        btn = tk.Button(
            parent,
            text=text,
            font=self.font_body,
            bg=bg or self.colors["green"],
            fg=fg or "#041107",
            activebackground=self.colors["blue"],
            relief="flat",
            command=command
        )
        btn.pack(**pack)
        return btn

    def show_home(self):
        self.screen = "home"
        self.clear_content()

        grid = tk.Frame(self.content, bg=self.colors["bg"])
        grid.pack(fill="both", expand=True)
        grid.columnconfigure(0, weight=3)
        grid.columnconfigure(1, weight=2)
        grid.rowconfigure(0, weight=3)
        grid.rowconfigure(1, weight=2)

        hero = self.card(grid, row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        tk.Label(hero, text="Dashboard", font=self.font_small, bg=self.colors["panel"], fg=self.colors["green"]).pack(anchor="w", padx=18, pady=(18, 0))
        tk.Label(hero, text="MD Smart Hub", font=self.font_h1, bg=self.colors["panel"], fg=self.colors["text"]).pack(anchor="w", padx=18, pady=(12, 0))
        tk.Label(
            hero,
            text="App Edition działa bez Chromium.\nSpotify wrócił jako moduł aplikacji.",
            font=self.font_body,
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            justify="left"
        ).pack(anchor="w", padx=18, pady=10)

        self.button(hero, "Otwórz Spotify", self.show_spotify, anchor="w", padx=18, pady=12, ipadx=18, ipady=8)

        weather = self.card(grid, row=0, column=1, sticky="nsew", pady=(0, 8))
        tk.Label(weather, text=self.weather_data["icon"], font=tkfont.Font(family="Arial", size=70, weight="bold"), bg=self.colors["panel"], fg=self.colors["blue"]).pack(pady=(20, 0))
        tk.Label(weather, text=f'{self.weather_data["temp"]}°C', font=self.font_h1, bg=self.colors["panel"], fg=self.colors["text"]).pack()
        tk.Label(weather, text=self.weather_data["text"], font=self.font_body, bg=self.colors["panel"], fg=self.colors["muted"]).pack()
        tk.Label(weather, text=CONFIG["city"], font=self.font_small, bg=self.colors["panel"], fg=self.colors["green"]).pack(pady=(8, 0))

        spotify = self.card(grid, row=1, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(spotify, text="♫", font=self.font_tile_icon, bg=self.colors["panel"], fg=self.colors["green"]).pack(side="left", padx=18)

        txt = tk.Frame(spotify, bg=self.colors["panel"])
        txt.pack(side="left", fill="both", expand=True, pady=18)

        sp = self.spotify_last
        track = sp.get("track_name") if sp.get("playing_track") else "Spotify"
        artist = sp.get("artist_name") if sp.get("playing_track") else sp.get("message", "Połącz Spotify w aplikacji.")

        tk.Label(txt, text=track, font=self.font_h2, bg=self.colors["panel"], fg=self.colors["text"]).pack(anchor="w")
        tk.Label(txt, text=artist, font=self.font_small, bg=self.colors["panel"], fg=self.colors["muted"]).pack(anchor="w")

        system = self.card(grid, row=1, column=1, sticky="nsew")
        temp = cpu_temp()
        tk.Label(system, text="Raspberry", font=self.font_small, bg=self.colors["panel"], fg=self.colors["green"]).pack(anchor="w", padx=16, pady=(16, 0))
        tk.Label(system, text=f"CPU {temp:.1f}°C", font=self.font_h2, bg=self.colors["panel"], fg=self.colors["text"]).pack(anchor="w", padx=16, pady=(8, 0))
        tk.Label(system, text=f"RAM {ram_percent():.0f}%", font=self.font_body, bg=self.colors["panel"], fg=self.colors["muted"]).pack(anchor="w", padx=16, pady=(8, 0))

        self.toast("Dashboard")

    def show_spotify(self):
        self.screen = "spotify"
        self.clear_content()

        page = tk.Frame(self.content, bg=self.colors["panel"], highlightthickness=1, highlightbackground="#243244")
        page.pack(fill="both", expand=True)

        top = tk.Frame(page, bg=self.colors["panel"])
        top.pack(fill="x", padx=22, pady=(14, 8))

        left = tk.Frame(top, bg=self.colors["panel"])
        left.pack(side="left", fill="x", expand=True)

        tk.Label(left, text="Spotify Native", font=self.font_small, bg=self.colors["panel"], fg=self.colors["green"]).pack(anchor="w")
        tk.Label(left, text="Odtwarzacz", font=self.font_h1, bg=self.colors["panel"], fg=self.colors["text"]).pack(anchor="w", pady=(4, 0))

        actions = tk.Frame(top, bg=self.colors["panel"])
        actions.pack(side="right")

        self.button(actions, "Autoryzuj", self.spotify_login, side="left", padx=3, ipadx=6, ipady=5)
        self.button(actions, "Reset", self.spotify_logout, side="left", padx=3, ipadx=6, ipady=5, bg=self.colors["red"], fg="white")
        self.button(actions, "Debug", self.show_spotify_debug, side="left", padx=3, ipadx=6, ipady=5, bg=self.colors["panel2"], fg=self.colors["text"])

        body = tk.Frame(page, bg=self.colors["panel"])
        body.pack(fill="both", expand=True, padx=22, pady=(0, 10))

        album = tk.Frame(body, bg=self.colors["card"], width=190, height=190, highlightthickness=1, highlightbackground="#243244")
        album.pack(side="left", padx=(0, 18), pady=8)
        album.pack_propagate(False)
        tk.Label(album, text="♫", font=tkfont.Font(family="Arial", size=78, weight="bold"), bg=self.colors["card"], fg=self.colors["green"]).pack(expand=True)

        info = tk.Frame(body, bg=self.colors["panel"])
        info.pack(side="left", fill="both", expand=True)

        sp = spotify_status()
        self.spotify_last = sp

        if not sp.get("connected"):
            title = "Spotify niepołączony"
            artist = "Kliknij Autoryzuj. Po logowaniu wróć do aplikacji."
        elif not sp.get("playing_track"):
            title = "Brak aktywnego utworu"
            artist = sp.get("message", "Włącz Spotify na telefonie lub komputerze.")
        else:
            title = sp.get("track_name", "Spotify")
            artist = sp.get("artist_name", "")

        tk.Label(info, text=title, font=self.font_h1, bg=self.colors["panel"], fg=self.colors["text"], wraplength=560, justify="left").pack(anchor="w", pady=(8, 0))
        tk.Label(info, text=artist, font=self.font_body, bg=self.colors["panel"], fg=self.colors["muted"], wraplength=560, justify="left").pack(anchor="w", pady=(6, 0))

        duration = sp.get("duration_ms", 0) or 1
        progress = sp.get("progress_ms", 0) or 0
        progress_text = f'{fmt_ms(progress)} / {fmt_ms(duration)}'
        tk.Label(info, text=progress_text, font=self.font_small, bg=self.colors["panel"], fg=self.colors["green"]).pack(anchor="w", pady=(12, 4))

        bar_bg = tk.Frame(info, bg="#263449", height=12)
        bar_bg.pack(fill="x", pady=(0, 8))
        bar_bg.pack_propagate(False)

        percent = max(1, min(100, int(progress / duration * 100)))
        bar = tk.Frame(bar_bg, bg=self.colors["green"], width=max(8, int(560 * percent / 100)))
        bar.pack(side="left", fill="y")

        controls = tk.Frame(info, bg=self.colors["panel"])
        controls.pack(anchor="w", pady=(4, 0))

        self.button(controls, "⏮", lambda: self.spotify_control("previous"), side="left", padx=3, ipadx=10, ipady=7, bg=self.colors["panel2"], fg=self.colors["text"])
        self.button(controls, "⏸" if sp.get("is_playing") else "▶", lambda: self.spotify_control("playpause"), side="left", padx=3, ipadx=17, ipady=7)
        self.button(controls, "⏭", lambda: self.spotify_control("next"), side="left", padx=3, ipadx=10, ipady=7, bg=self.colors["panel2"], fg=self.colors["text"])
        self.button(controls, "-15s", lambda: self.spotify_seek_relative(-15000), side="left", padx=8, ipadx=9, ipady=7, bg=self.colors["panel2"], fg=self.colors["text"])
        self.button(controls, "+15s", lambda: self.spotify_seek_relative(15000), side="left", padx=3, ipadx=9, ipady=7, bg=self.colors["panel2"], fg=self.colors["text"])

        row2 = tk.Frame(info, bg=self.colors["panel"])
        row2.pack(anchor="w", pady=(10, 0))
        self.button(row2, "Szukaj", self.show_spotify_search, side="left", padx=3, ipadx=12, ipady=7)
        self.button(row2, "Playlisty", self.show_playlists, side="left", padx=6, ipadx=12, ipady=7)
        self.button(row2, "Audio", self.show_audio, side="left", padx=6, ipadx=12, ipady=7)
        self.button(row2, "Odśwież", self.show_spotify, side="left", padx=3, ipadx=12, ipady=7, bg=self.colors["panel2"], fg=self.colors["text"])

        device = sp.get("device_name", "Brak urządzenia")
        tk.Label(info, text=f"Urządzenie: {device}", font=self.font_small, bg=self.colors["panel"], fg=self.colors["muted"]).pack(anchor="w", pady=(14, 0))

        self.toast("Spotify")

    def spotify_login(self):
        try:
            ensure_callback_server()
            verifier, challenge = create_pkce_pair()
            state = secrets.token_urlsafe(24)

            write_json(SESSION_PATH, {
                "code_verifier": verifier,
                "state": state
            })

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

            url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)

            # Open login in the default browser. The app itself remains native.
            webbrowser.open(url)
            self.toast("Otworzyłem logowanie Spotify. Po zalogowaniu wróć do aplikacji.")
        except Exception as e:
            self.toast(f"Błąd logowania: {e}")

    def spotify_logout(self):
        try:
            if TOKENS_PATH.exists():
                TOKENS_PATH.unlink()
            if SESSION_PATH.exists():
                SESSION_PATH.unlink()
            self.spotify_last = spotify_status()
            self.toast("Spotify zresetowane")
            self.show_spotify()
        except Exception as e:
            self.toast(f"Błąd resetu: {e}")

    def spotify_control(self, action):
        def worker():
            if action == "next":
                data, code = spotify_api("/me/player/next", method="POST")
            elif action == "previous":
                data, code = spotify_api("/me/player/previous", method="POST")
            elif action == "playpause":
                status = spotify_status()
                if status.get("is_playing"):
                    data, code = spotify_api("/me/player/pause", method="PUT")
                else:
                    data, code = spotify_api("/me/player/play", method="PUT")
            else:
                data, code = {"error": "unknown action"}, 400

            if code in (200, 204):
                self.root.after(0, lambda: self.toast("Spotify: OK"))
            else:
                self.root.after(0, lambda: self.toast(friendly_spotify_error(code, data)))

            self.root.after(700, self.show_spotify)

        threading.Thread(target=worker, daemon=True).start()

    def spotify_seek_relative(self, delta_ms):
        status = spotify_status()

        if not status.get("playing_track"):
            self.toast("Brak utworu do przewijania")
            return

        new_pos = int(status.get("progress_ms", 0) or 0) + int(delta_ms)
        duration = int(status.get("duration_ms", 0) or 0)
        new_pos = max(0, min(new_pos, max(0, duration - 1000)))

        def worker():
            data, code = spotify_api(f"/me/player/seek?position_ms={new_pos}", method="PUT")

            if code in (200, 204):
                self.root.after(0, lambda: self.toast("Przewinięto"))
            else:
                self.root.after(0, lambda: self.toast(friendly_spotify_error(code, data)))

            self.root.after(600, self.show_spotify)

        threading.Thread(target=worker, daemon=True).start()


    def show_spotify_debug(self):
        self.screen = "debug"
        self.clear_content()

        page = tk.Frame(self.content, bg=self.colors["panel"], highlightthickness=1, highlightbackground="#243244")
        page.pack(fill="both", expand=True)

        tk.Label(page, text="Spotify Debug", font=self.font_small, bg=self.colors["panel"], fg=self.colors["green"]).pack(anchor="w", padx=22, pady=(20, 0))
        tk.Label(page, text="Diagnostyka", font=self.font_h1, bg=self.colors["panel"], fg=self.colors["text"]).pack(anchor="w", padx=22, pady=(5, 0))

        tokens = read_json(TOKENS_PATH, {})
        scope = tokens.get("scope", "BRAK TOKENU")
        connected = "TAK" if spotify_tokens() else "NIE"

        text = (
            f"Wersja: {APP_VERSION}\n"
            f"Spotify token: {connected}\n"
            f"Callback: {REDIRECT_URI}\n\n"
            f"Scope:\n{scope}\n\n"
            "Nie pokazuję access_token ani refresh_token."
        )

        tk.Label(
            page,
            text=text,
            font=self.font_small,
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            justify="left",
            wraplength=820
        ).pack(anchor="w", padx=22, pady=18)

        self.button(page, "Wróć do Spotify", self.show_spotify, anchor="w", padx=22, pady=8, ipadx=16, ipady=8)

    def show_spotify_search(self):
        self.screen = "search"
        self.clear_content()

        page = tk.Frame(self.content, bg=self.colors["panel"], highlightthickness=1, highlightbackground="#243244")
        page.pack(fill="both", expand=True)

        head = tk.Frame(page, bg=self.colors["panel"])
        head.pack(fill="x", padx=16, pady=(10, 5))

        left = tk.Frame(head, bg=self.colors["panel"])
        left.pack(side="left", fill="x", expand=True)

        tk.Label(left, text="Spotify", font=self.font_small, bg=self.colors["panel"], fg=self.colors["green"]).pack(anchor="w")
        tk.Label(left, text="Wyszukiwarka", font=self.font_h2, bg=self.colors["panel"], fg=self.colors["text"]).pack(anchor="w")

        self.button(head, "Wróć", self.show_spotify, side="right", padx=3, ipadx=10, ipady=6, bg=self.colors["panel2"], fg=self.colors["text"])
        self.button(head, "Szukaj", self.spotify_search, side="right", padx=3, ipadx=10, ipady=6)
        self.button(head, "Wyczyść", self.clear_search, side="right", padx=3, ipadx=10, ipady=6, bg=self.colors["panel2"], fg=self.colors["text"])

        self.search_label = tk.Label(
            page,
            text=self.search_query or "Dotknij klawiszy poniżej",
            font=self.font_body,
            bg=self.colors["card"],
            fg=self.colors["text"],
            anchor="w",
            padx=14,
            pady=7
        )
        self.search_label.pack(fill="x", padx=16, pady=(0, 6))

        self.results_frame = tk.Frame(page, bg=self.colors["panel"], height=190)
        self.results_frame.pack(fill="both", expand=True, padx=16, pady=(0, 6))
        self.results_frame.pack_propagate(False)

        self.keyboard_frame = tk.Frame(page, bg=self.colors["card"], height=206, highlightthickness=1, highlightbackground="#243244")
        self.keyboard_frame.pack(fill="x", padx=16, pady=(0, 10))
        self.keyboard_frame.pack_propagate(False)

        self.render_search_results()
        self.render_keyboard()

        self.toast("Wyszukiwarka Spotify")

    def render_keyboard(self):
        for child in self.keyboard_frame.winfo_children():
            child.destroy()

        rows = [
            list("QWERTYUIOP"),
            list("ASDFGHJKL"),
            list("ZXCVBNM"),
            list("1234567890"),
            ["SPACJA", "⌫", "ENTER"]
        ]

        for r, row in enumerate(rows):
            row_frame = tk.Frame(self.keyboard_frame, bg=self.colors["card"])
            row_frame.pack(fill="x", padx=8, pady=3)

            for c, key in enumerate(row):
                if key == "SPACJA":
                    width = 20
                elif key == "ENTER":
                    width = 10
                elif key == "⌫":
                    width = 7
                else:
                    width = 4

                btn = tk.Button(
                    row_frame,
                    text=key,
                    font=self.font_small,
                    width=width,
                    bg=self.colors["green"] if key == "ENTER" else self.colors["panel2"],
                    fg="#041107" if key == "ENTER" else self.colors["text"],
                    relief="flat",
                    command=lambda k=key: self.keyboard_press(k)
                )
                btn.pack(side="left", padx=3, ipady=5)

    def keyboard_press(self, key):
        if key == "⌫":
            self.search_query = self.search_query[:-1]
        elif key == "SPACJA":
            self.search_query += " "
        elif key == "ENTER":
            self.spotify_search()
            return
        else:
            self.search_query += key.lower()

        self.search_label.configure(text=self.search_query or "Dotknij klawiszy poniżej")

    def clear_search(self):
        self.search_query = ""
        self.search_results = []
        self.show_spotify_search()

    def spotify_search(self):
        query = self.search_query.strip()

        if not query:
            self.toast("Wpisz nazwę utworu")
            return

        self.toast("Szukam...")

        def worker():
            items, error = spotify_search_tracks(query, limit=6)

            if error:
                self.search_results = [{
                    "name": error,
                    "artist": "Błąd wyszukiwania",
                    "uri": None
                }]
            else:
                self.search_results = items

            self.root.after(0, self.show_spotify_search)

        threading.Thread(target=worker, daemon=True).start()

    def render_search_results(self):
        for child in self.results_frame.winfo_children():
            child.destroy()

        if not self.search_results:
            tk.Label(
                self.results_frame,
                text="Wpisz utwór i kliknij Szukaj.",
                font=self.font_body,
                bg=self.colors["panel"],
                fg=self.colors["muted"]
            ).pack(anchor="w", pady=8)
            return

        for item in self.search_results[:6]:
            row = tk.Frame(self.results_frame, bg=self.colors["card"], highlightthickness=1, highlightbackground="#243244")
            row.pack(fill="x", pady=3)

            tk.Label(row, text="♫", font=self.font_h2, bg=self.colors["card"], fg=self.colors["green"]).pack(side="left", padx=10)

            txt = tk.Frame(row, bg=self.colors["card"])
            txt.pack(side="left", fill="x", expand=True, pady=6)

            tk.Label(txt, text=item["name"], font=self.font_small, bg=self.colors["card"], fg=self.colors["text"], anchor="w").pack(anchor="w")
            tk.Label(txt, text=item["artist"], font=self.font_tiny, bg=self.colors["card"], fg=self.colors["muted"], anchor="w").pack(anchor="w")

            if item.get("uri"):
                tk.Button(
                    row,
                    text="Play",
                    font=self.font_small,
                    bg=self.colors["green"],
                    fg="#041107",
                    relief="flat",
                    command=lambda uri=item["uri"]: self.spotify_play_track(uri)
                ).pack(side="right", padx=8, ipadx=8, ipady=4)


    def spotify_play_track(self, uri):
        def worker():
            data, code = spotify_api("/me/player/play", method="PUT", payload={"uris": [uri]})

            if code in (200, 204):
                self.root.after(0, lambda: self.toast("Odtwarzam utwór"))
                self.root.after(800, self.show_spotify)
            else:
                self.root.after(0, lambda: self.toast(friendly_spotify_error(code, data)))

        threading.Thread(target=worker, daemon=True).start()

    def show_playlists(self):
        self.screen = "playlists"
        self.clear_content()

        page = tk.Frame(self.content, bg=self.colors["panel"], highlightthickness=1, highlightbackground="#243244")
        page.pack(fill="both", expand=True)

        head = tk.Frame(page, bg=self.colors["panel"])
        head.pack(fill="x", padx=18, pady=(14, 8))

        left = tk.Frame(head, bg=self.colors["panel"])
        left.pack(side="left", fill="x", expand=True)

        tk.Label(left, text="Spotify", font=self.font_small, bg=self.colors["panel"], fg=self.colors["green"]).pack(anchor="w")
        tk.Label(left, text="Playlisty", font=self.font_h2, bg=self.colors["panel"], fg=self.colors["text"]).pack(anchor="w")

        self.button(head, "Odśwież", self.load_playlists, side="right", padx=3, ipadx=10, ipady=6)
        self.button(head, "Spotify", self.show_spotify, side="right", padx=3, ipadx=10, ipady=6, bg=self.colors["panel2"], fg=self.colors["text"])

        self.playlists_frame = tk.Frame(page, bg=self.colors["panel"])
        self.playlists_frame.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        self.render_playlists()

        if not self.playlists:
            self.load_playlists()

        self.toast("Playlisty")

    def load_playlists(self):
        self.toast("Ładuję playlisty...")

        def worker():
            items, error = spotify_get_playlists(limit=30)
            if error:
                self.playlists = [{"name": error, "total": 0, "id": None, "uri": None}]
            else:
                self.playlists = items

            self.root.after(0, self.show_playlists)

        threading.Thread(target=worker, daemon=True).start()

    def render_playlists(self):
        for child in self.playlists_frame.winfo_children():
            child.destroy()

        if not self.playlists:
            tk.Label(
                self.playlists_frame,
                text="Ładowanie playlist albo brak playlist.",
                font=self.font_body,
                bg=self.colors["panel"],
                fg=self.colors["muted"]
            ).pack(anchor="w", pady=8)
            return

        for playlist in self.playlists[:8]:
            row = tk.Frame(self.playlists_frame, bg=self.colors["card"], highlightthickness=1, highlightbackground="#243244")
            row.pack(fill="x", pady=4)

            tk.Label(row, text="☷", font=self.font_h2, bg=self.colors["card"], fg=self.colors["green"]).pack(side="left", padx=12)

            txt = tk.Frame(row, bg=self.colors["card"])
            txt.pack(side="left", fill="x", expand=True, pady=8)

            tk.Label(txt, text=playlist.get("name", "Playlista"), font=self.font_small, bg=self.colors["card"], fg=self.colors["text"], anchor="w").pack(anchor="w")
            tk.Label(txt, text=f'{playlist.get("total", 0)} utworów', font=self.font_tiny, bg=self.colors["card"], fg=self.colors["muted"], anchor="w").pack(anchor="w")

            if playlist.get("id"):
                tk.Button(
                    row,
                    text="Otwórz",
                    font=self.font_small,
                    bg=self.colors["green"],
                    fg="#041107",
                    relief="flat",
                    command=lambda p=playlist: self.open_playlist(p)
                ).pack(side="right", padx=8, ipadx=8, ipady=5)

    def open_playlist(self, playlist):
        self.current_playlist_uri = playlist.get("uri")
        self.current_playlist_name = playlist.get("name", "Playlista")
        self.playlist_tracks = []
        self.show_playlist_detail(loading=True)

        def worker():
            tracks, error = spotify_get_playlist_tracks(playlist.get("id"), limit=50)
            if error:
                self.playlist_tracks = [{
                    "name": "Spotify nie udostępnia listy utworów",
                    "artist": error,
                    "uri": None,
                    "permission_error": True
                }]
            else:
                self.playlist_tracks = tracks

            self.root.after(0, self.show_playlist_detail)

        threading.Thread(target=worker, daemon=True).start()

    def show_playlist_detail(self, loading=False):
        self.screen = "playlist_detail"
        self.clear_content()

        page = tk.Frame(self.content, bg=self.colors["panel"], highlightthickness=1, highlightbackground="#243244")
        page.pack(fill="both", expand=True)

        head = tk.Frame(page, bg=self.colors["panel"])
        head.pack(fill="x", padx=18, pady=(14, 8))

        left = tk.Frame(head, bg=self.colors["panel"])
        left.pack(side="left", fill="x", expand=True)

        tk.Label(left, text="Playlista", font=self.font_small, bg=self.colors["panel"], fg=self.colors["green"]).pack(anchor="w")
        tk.Label(left, text=self.current_playlist_name, font=self.font_h2, bg=self.colors["panel"], fg=self.colors["text"], wraplength=520, justify="left").pack(anchor="w")

        self.button(head, "Play", self.play_current_playlist, side="right", padx=3, ipadx=12, ipady=6)
        self.button(head, "Wróć", self.show_playlists, side="right", padx=3, ipadx=12, ipady=6, bg=self.colors["panel2"], fg=self.colors["text"])

        body = tk.Frame(page, bg=self.colors["panel"])
        body.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        if loading:
            tk.Label(body, text="Ładowanie utworów...", font=self.font_body, bg=self.colors["panel"], fg=self.colors["muted"]).pack(anchor="w", pady=8)
            return

        if not self.playlist_tracks:
            tk.Label(
                body,
                text="Brak widocznych utworów.\n\nJeżeli przycisk Play odtwarza playlistę, to Spotify pozwala ją odtwarzać, ale nie zwraca aplikacji listy utworów.",
                font=self.font_body,
                bg=self.colors["panel"],
                fg=self.colors["muted"],
                justify="left",
                wraplength=820
            ).pack(anchor="w", pady=8)
            return

        for track in self.playlist_tracks[:8]:
            row = tk.Frame(body, bg=self.colors["card"], highlightthickness=1, highlightbackground="#243244")
            row.pack(fill="x", pady=3)

            icon = "!" if track.get("permission_error") else "♫"
            tk.Label(row, text=icon, font=self.font_h2, bg=self.colors["card"], fg=self.colors["green"]).pack(side="left", padx=10)

            txt = tk.Frame(row, bg=self.colors["card"])
            txt.pack(side="left", fill="x", expand=True, pady=6)

            wrap = 700 if track.get("permission_error") else 520
            tk.Label(
                txt,
                text=track.get("name", "Utwór"),
                font=self.font_small,
                bg=self.colors["card"],
                fg=self.colors["text"],
                anchor="w",
                wraplength=wrap,
                justify="left"
            ).pack(anchor="w")

            tk.Label(
                txt,
                text=track.get("artist", ""),
                font=self.font_tiny,
                bg=self.colors["card"],
                fg=self.colors["muted"],
                anchor="w",
                wraplength=wrap,
                justify="left"
            ).pack(anchor="w")

            if track.get("uri"):
                tk.Button(
                    row,
                    text="Play",
                    font=self.font_small,
                    bg=self.colors["green"],
                    fg="#041107",
                    relief="flat",
                    command=lambda uri=track["uri"]: self.spotify_play_from_playlist(uri)
                ).pack(side="right", padx=8, ipadx=8, ipady=4)

    def play_current_playlist(self):
        if not self.current_playlist_uri:
            self.toast("Nie wybrano playlisty")
            return

        def worker():
            data, code = spotify_api("/me/player/play", method="PUT", payload={"context_uri": self.current_playlist_uri})
            if code in (200, 204):
                self.root.after(0, lambda: self.toast("Odtwarzam playlistę"))
                self.root.after(700, self.show_spotify)
            else:
                self.root.after(0, lambda: self.toast(friendly_spotify_error(code, data)))

        threading.Thread(target=worker, daemon=True).start()

    def spotify_play_from_playlist(self, track_uri):
        if not self.current_playlist_uri:
            return self.spotify_play_track(track_uri)

        def worker():
            data, code = spotify_api(
                "/me/player/play",
                method="PUT",
                payload={
                    "context_uri": self.current_playlist_uri,
                    "offset": {"uri": track_uri}
                }
            )

            if code in (200, 204):
                self.root.after(0, lambda: self.toast("Odtwarzam utwór"))
                self.root.after(700, self.show_spotify)
            else:
                self.root.after(0, lambda: self.toast(friendly_spotify_error(code, data)))

        threading.Thread(target=worker, daemon=True).start()


    def show_audio(self):
        self.screen = "audio"
        self.clear_content()

        page = tk.Frame(self.content, bg=self.colors["panel"], highlightthickness=1, highlightbackground="#243244")
        page.pack(fill="both", expand=True)

        head = tk.Frame(page, bg=self.colors["panel"])
        head.pack(fill="x", padx=18, pady=(12, 6))

        left = tk.Frame(head, bg=self.colors["panel"])
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="Audio Stable", font=self.font_small, bg=self.colors["panel"], fg=self.colors["green"]).pack(anchor="w")
        tk.Label(left, text="Spotify Connect + Bluetooth + Volume", font=self.font_h2, bg=self.colors["panel"], fg=self.colors["text"]).pack(anchor="w")

        self.button(head, "Odśwież", self.show_audio, side="right", padx=3, ipadx=8, ipady=5)
        self.button(head, "Spotify", self.show_spotify, side="right", padx=3, ipadx=8, ipady=5, bg=self.colors["panel2"], fg=self.colors["text"])

        body = tk.Frame(page, bg=self.colors["panel"])
        body.pack(fill="both", expand=True, padx=18, pady=(0, 10))

        status_row = tk.Frame(body, bg=self.colors["panel"])
        status_row.pack(fill="x", pady=(0, 8))

        status_box = tk.Frame(status_row, bg=self.colors["card"], highlightthickness=1, highlightbackground="#243244")
        status_box.pack(side="left", fill="both", expand=True, padx=(0, 8))

        librespot_bin = "TAK" if command_exists("librespot") or (Path.home() / ".cargo/bin/librespot").exists() else "NIE"
        librespot_service = service_status("librespot-md-smart-hub.service")
        bt = bluetooth_status()

        tk.Label(status_box, text="Status audio", font=self.font_small, bg=self.colors["card"], fg=self.colors["green"]).pack(anchor="w", padx=14, pady=(10, 0))
        tk.Label(
            status_box,
            text=f"Librespot: {librespot_bin}   Usługa: {librespot_service}\nBluetooth: {bt}",
            font=self.font_small,
            bg=self.colors["card"],
            fg=self.colors["muted"],
            justify="left",
            wraplength=610
        ).pack(anchor="w", padx=14, pady=(5, 10))

        action_box = tk.Frame(status_row, bg=self.colors["card"], width=310, highlightthickness=1, highlightbackground="#243244")
        action_box.pack(side="right", fill="y")
        action_box.pack_propagate(False)
        tk.Label(action_box, text="Szybkie akcje", font=self.font_small, bg=self.colors["card"], fg=self.colors["green"]).pack(anchor="w", padx=12, pady=(8, 0))
        rowa = tk.Frame(action_box, bg=self.colors["card"])
        rowa.pack(anchor="w", padx=8, pady=(8, 6))
        self.button(rowa, "Soundbar", self.connect_soundbar_action, side="left", padx=3, ipadx=6, ipady=4)
        self.button(rowa, "Restart Connect", self.restart_connect_action, side="left", padx=3, ipadx=6, ipady=4, bg=self.colors["panel2"], fg=self.colors["text"])

        volume_row = tk.Frame(body, bg=self.colors["panel"])
        volume_row.pack(fill="x", pady=(0, 8))

        sp_box = tk.Frame(volume_row, bg=self.colors["card"], highlightthickness=1, highlightbackground="#243244")
        sp_box.pack(side="left", fill="both", expand=True, padx=(0, 8))

        sp = spotify_status()
        spotify_vol = sp.get("volume_percent")
        spotify_text = f"{spotify_vol}%" if isinstance(spotify_vol, int) else "--%"

        tk.Label(sp_box, text="Głośność Spotify", font=self.font_small, bg=self.colors["card"], fg=self.colors["green"]).pack(anchor="w", padx=14, pady=(10, 0))
        tk.Label(sp_box, text=spotify_text, font=self.font_h2, bg=self.colors["card"], fg=self.colors["text"]).pack(anchor="w", padx=14, pady=(2, 2))
        rowv = tk.Frame(sp_box, bg=self.colors["card"])
        rowv.pack(anchor="w", padx=10, pady=(0, 10))
        self.button(rowv, "-10", lambda: self.change_volume(-10), side="left", padx=3, ipadx=8, ipady=4, bg=self.colors["panel2"], fg=self.colors["text"])
        self.button(rowv, "+10", lambda: self.change_volume(10), side="left", padx=3, ipadx=8, ipady=4)
        self.button(rowv, "70%", lambda: self.set_volume(70), side="left", padx=3, ipadx=8, ipady=4, bg=self.colors["panel2"], fg=self.colors["text"])

        sys_box = tk.Frame(volume_row, bg=self.colors["card"], highlightthickness=1, highlightbackground="#243244")
        sys_box.pack(side="right", fill="both", expand=True)

        sys_vol = system_volume_get()
        sys_text = f"{sys_vol}%" if isinstance(sys_vol, int) else "--%"

        tk.Label(sys_box, text="Głośność systemowa Raspberry", font=self.font_small, bg=self.colors["card"], fg=self.colors["green"]).pack(anchor="w", padx=14, pady=(10, 0))
        tk.Label(sys_box, text=sys_text, font=self.font_h2, bg=self.colors["card"], fg=self.colors["text"]).pack(anchor="w", padx=14, pady=(2, 2))
        rows = tk.Frame(sys_box, bg=self.colors["card"])
        rows.pack(anchor="w", padx=10, pady=(0, 10))
        self.button(rows, "-10", lambda: self.change_system_volume(-10), side="left", padx=3, ipadx=8, ipady=4, bg=self.colors["panel2"], fg=self.colors["text"])
        self.button(rows, "+10", lambda: self.change_system_volume(10), side="left", padx=3, ipadx=8, ipady=4)
        self.button(rows, "80%", lambda: self.set_system_volume(80), side="left", padx=3, ipadx=8, ipady=4, bg=self.colors["panel2"], fg=self.colors["text"])

        tk.Label(body, text="Urządzenia Spotify", font=self.font_small, bg=self.colors["panel"], fg=self.colors["green"]).pack(anchor="w", pady=(2, 4))
        devices_frame = tk.Frame(body, bg=self.colors["panel"])
        devices_frame.pack(fill="both", expand=True)

        devices, error = spotify_get_devices()
        if error:
            tk.Label(devices_frame, text=error, font=self.font_body, bg=self.colors["panel"], fg=self.colors["muted"]).pack(anchor="w", pady=8)
            return

        if not devices:
            tk.Label(devices_frame, text="Brak urządzeń Spotify. Uruchom Spotify na telefonie lub włącz usługę Spotify Connect.", font=self.font_body, bg=self.colors["panel"], fg=self.colors["muted"]).pack(anchor="w", pady=8)
            return

        for device in devices[:5]:
            row = tk.Frame(devices_frame, bg=self.colors["card"], highlightthickness=1, highlightbackground="#243244")
            row.pack(fill="x", pady=3)

            icon = "✓" if device.get("is_active") else "🔊"
            tk.Label(row, text=icon, font=self.font_h2, bg=self.colors["card"], fg=self.colors["green"]).pack(side="left", padx=12)

            txt = tk.Frame(row, bg=self.colors["card"])
            txt.pack(side="left", fill="x", expand=True, pady=6)

            name = device.get("name", "Urządzenie")
            sub = f"{device.get('type', 'device')} • {device.get('volume_percent', '--')}%"
            tk.Label(txt, text=name, font=self.font_small, bg=self.colors["card"], fg=self.colors["text"]).pack(anchor="w")
            tk.Label(txt, text=sub, font=self.font_tiny, bg=self.colors["card"], fg=self.colors["muted"]).pack(anchor="w")

            if device.get("id"):
                tk.Button(
                    row,
                    text="Wybierz",
                    font=self.font_small,
                    bg=self.colors["green"],
                    fg="#041107",
                    relief="flat",
                    command=lambda did=device["id"]: self.transfer_device(did)
                ).pack(side="right", padx=8, ipadx=8, ipady=4)

        self.toast("Audio Stable")

    def set_volume(self, value):
        def worker():
            ok, error = spotify_set_volume(value)
            if ok:
                self.root.after(0, lambda: self.toast(f"Spotify {value}%"))
            else:
                self.root.after(0, lambda: self.toast(error or "Błąd głośności Spotify"))
            self.root.after(500, self.show_audio)
        threading.Thread(target=worker, daemon=True).start()

    def change_volume(self, delta):
        sp = spotify_status()
        current = sp.get("volume_percent")
        if not isinstance(current, int):
            current = 50
        self.set_volume(max(0, min(100, current + delta)))

    def set_system_volume(self, value):
        def worker():
            ok = system_volume_set(value)
            if ok:
                self.root.after(0, lambda: self.toast(f"System {value}%"))
            else:
                self.root.after(0, lambda: self.toast("Nie udało się zmienić głośności systemu"))
            self.root.after(500, self.show_audio)
        threading.Thread(target=worker, daemon=True).start()

    def change_system_volume(self, delta):
        current = system_volume_get()
        if not isinstance(current, int):
            current = 50
        self.set_system_volume(max(0, min(100, current + delta)))

    def transfer_device(self, device_id):
        def worker():
            ok, error = spotify_transfer_device(device_id, play=False)
            if ok:
                self.root.after(0, lambda: self.toast("Wybrano urządzenie Spotify"))
            else:
                self.root.after(0, lambda: self.toast(error or "Błąd urządzenia"))
            self.root.after(800, self.show_audio)
        threading.Thread(target=worker, daemon=True).start()

    def connect_soundbar_action(self):
        def worker():
            ok, msg = connect_saved_soundbar()
            self.root.after(0, lambda: self.toast(msg))
            self.root.after(900, self.show_audio)
        threading.Thread(target=worker, daemon=True).start()

    def restart_connect_action(self):
        def worker():
            ok = restart_user_service("librespot-md-smart-hub.service")
            self.root.after(0, lambda: self.toast("Restart Spotify Connect OK" if ok else "Nie udało się zrestartować Spotify Connect"))
            self.root.after(900, self.show_audio)
        threading.Thread(target=worker, daemon=True).start()


    def show_weather(self):
        self.screen = "weather"
        self.clear_content()

        page = tk.Frame(self.content, bg=self.colors["panel"], highlightthickness=1, highlightbackground="#243244")
        page.pack(fill="both", expand=True)

        tk.Label(page, text="Pogoda", font=self.font_small, bg=self.colors["panel"], fg=self.colors["green"]).pack(anchor="w", padx=24, pady=(24, 0))
        tk.Label(page, text=self.weather_data["icon"], font=tkfont.Font(family="Arial", size=92, weight="bold"), bg=self.colors["panel"], fg=self.colors["blue"]).pack(pady=(24, 0))
        tk.Label(page, text=f'{self.weather_data["temp"]}°C', font=tkfont.Font(family="Arial", size=58, weight="bold"), bg=self.colors["panel"], fg=self.colors["text"]).pack()
        tk.Label(page, text=self.weather_data["text"], font=self.font_h2, bg=self.colors["panel"], fg=self.colors["muted"]).pack()
        tk.Label(page, text=f'Miasto: {CONFIG["city"]}   Wiatr: {self.weather_data["wind"]} km/h', font=self.font_body, bg=self.colors["panel"], fg=self.colors["text"]).pack(pady=18)

        self.button(page, "Odśwież pogodę", self.refresh_weather_now, ipadx=18, ipady=8)

        self.toast("Pogoda")

    def show_system(self):
        self.screen = "system"
        self.clear_content()

        page = tk.Frame(self.content, bg=self.colors["bg"])
        page.pack(fill="both", expand=True)
        page.columnconfigure(0, weight=1)
        page.columnconfigure(1, weight=1)
        page.rowconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)

        self.system_cards = {}

        self.system_cards["temp"] = self.metric(page, "CPU Temp", "--°C", 0, 0)
        self.system_cards["cpu"] = self.metric(page, "CPU Load", "--%", 0, 1)
        self.system_cards["ram"] = self.metric(page, "RAM", "--%", 1, 0)
        self.system_cards["uptime"] = self.metric(page, "Uptime", "--", 1, 1)

        self.update_system_screen()
        self.toast("System")

    def show_settings(self):
        self.screen = "settings"
        self.clear_content()

        page = tk.Frame(self.content, bg=self.colors["panel"], highlightthickness=1, highlightbackground="#243244")
        page.pack(fill="both", expand=True)

        tk.Label(page, text="Ustawienia", font=self.font_small, bg=self.colors["panel"], fg=self.colors["green"]).pack(anchor="w", padx=24, pady=(24, 0))
        tk.Label(page, text="MD Smart Hub OS", font=self.font_h1, bg=self.colors["panel"], fg=self.colors["text"]).pack(anchor="w", padx=24, pady=(10, 0))

        text = (
            f"Wersja: {APP_VERSION}\n"
            f"Miasto: {CONFIG['city']}\n"
            f"Redirect URI Spotify: {REDIRECT_URI}\n\n"
            "ESC wyłącza pełny ekran.\n"
            "F11 przełącza pełny ekran.\n\n"
            "Kolejny etap: v4.4 Spotify Connect Stable + Bluetooth autostart."
        )

        tk.Label(
            page,
            text=text,
            font=self.font_body,
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            justify="left"
        ).pack(anchor="w", padx=24, pady=18)

        self.button(page, "Zamknij aplikację", self.root.destroy, anchor="w", padx=24, pady=10, ipadx=18, ipady=8, bg=self.colors["red"], fg="white")

        self.toast("Ustawienia")

    def metric(self, parent, title, value, row, column):
        frame = tk.Frame(parent, bg=self.colors["panel"], highlightthickness=1, highlightbackground="#243244")
        frame.grid(row=row, column=column, sticky="nsew", padx=6, pady=6)

        tk.Label(frame, text=title, font=self.font_small, bg=self.colors["panel"], fg=self.colors["green"]).pack(anchor="w", padx=18, pady=(18, 0))
        value_label = tk.Label(frame, text=value, font=self.font_h1, bg=self.colors["panel"], fg=self.colors["text"])
        value_label.pack(anchor="w", padx=18, pady=(16, 0))

        bar_bg = tk.Frame(frame, bg="#263449", height=10)
        bar_bg.pack(fill="x", padx=18, pady=(18, 0))
        bar_bg.pack_propagate(False)

        bar = tk.Frame(bar_bg, bg=self.colors["green"], width=1)
        bar.pack(side="left", fill="y")

        return {"frame": frame, "value": value_label, "bar": bar, "bar_bg": bar_bg}

    def update_metric(self, key, value, percent):
        if not hasattr(self, "system_cards") or key not in self.system_cards:
            return

        card = self.system_cards[key]
        card["value"].configure(text=value)

        width = card["bar_bg"].winfo_width()
        if width <= 1:
            width = 300

        new_width = max(4, int(width * max(0, min(percent, 100)) / 100))
        card["bar"].configure(width=new_width)

        if percent > 80:
            card["bar"].configure(bg=self.colors["red"])
        elif percent > 60:
            card["bar"].configure(bg=self.colors["warn"])
        else:
            card["bar"].configure(bg=self.colors["green"])

    def update_system_screen(self):
        temp = cpu_temp()
        cpu = CPU.percent()
        ram = ram_percent()
        uptime = int(time.time() - BOOT_TIME)
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60

        self.update_metric("temp", f"{temp:.1f}°C", min(100, temp / 85 * 100))
        self.update_metric("cpu", f"{cpu:.0f}%", cpu)
        self.update_metric("ram", f"{ram:.0f}%", ram)
        self.update_metric("uptime", f"{hours}h {minutes}m", min(100, hours / 24 * 100))

    def tick_clock(self):
        now = time.localtime()
        self.time_label.configure(text=time.strftime("%H:%M", now))
        self.date_label.configure(text=time.strftime("%d.%m.%Y", now))
        self.root.after(1000, self.tick_clock)

    def tick_system(self):
        temp = cpu_temp()
        wifi = "Wi‑Fi ✓" if is_online() else "Wi‑Fi ?"
        spotify_txt = "Spotify ✓" if spotify_tokens() else "Spotify ?"
        self.status_label.configure(text=f"{wifi} • {spotify_txt} • CPU {temp:.1f}°C • MD")

        if self.screen == "system":
            self.update_system_screen()

        self.root.after(3000, self.tick_system)

    def tick_spotify(self):
        def worker():
            self.spotify_last = spotify_status()
            if self.screen in ("spotify", "home"):
                # Do not redraw too aggressively while user interacts.
                pass

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(5000, self.tick_spotify)

    def start_weather_loop(self):
        self.refresh_weather_now()
        self.root.after(600000, self.start_weather_loop)

    def refresh_weather_now(self):
        def worker():
            try:
                data = fetch_weather()
                self.weather_data = data
                self.root.after(0, self.after_weather_update)
            except Exception:
                self.weather_data["text"] = "Brak połączenia"
                self.root.after(0, self.after_weather_update)

        threading.Thread(target=worker, daemon=True).start()

    def after_weather_update(self):
        if self.screen == "home":
            self.show_home()
        elif self.screen == "weather":
            self.show_weather()


def main():
    ensure_callback_server()
    root = tk.Tk()
    SmartHubApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
