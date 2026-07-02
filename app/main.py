#!/usr/bin/env python3
import json
import os
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import font as tkfont

APP_VERSION = "v4.0 Alpha App Edition"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data"
CONFIG_PATH = DATA_ROOT / "config.json"

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
        self.font_tile_icon = tkfont.Font(family="Arial", size=36, weight="bold")

        self.build_layout()
        self.show_home()
        self.tick_clock()
        self.tick_system()
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
            text="Wi‑Fi • CPU --°C • MD",
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
            ("♫", "spotify", self.show_spotify_placeholder),
            ("☁", "weather", self.show_weather),
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
            btn.pack(fill="both", expand=True, padx=8, pady=6)
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
            text="Nowa wersja App Edition działa bez Chromium.\nTo jest baza pod Spotify, Bluetooth i Smart Home.",
            font=self.font_body,
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            justify="left"
        ).pack(anchor="w", padx=18, pady=10)

        tk.Button(
            hero,
            text="Otwórz Spotify",
            font=self.font_body,
            bg=self.colors["green"],
            fg="#041107",
            relief="flat",
            command=self.show_spotify_placeholder
        ).pack(anchor="w", padx=18, pady=12, ipadx=18, ipady=8)

        weather = self.card(grid, row=0, column=1, sticky="nsew", pady=(0, 8))
        tk.Label(weather, text=self.weather_data["icon"], font=tkfont.Font(family="Arial", size=70, weight="bold"), bg=self.colors["panel"], fg=self.colors["blue"]).pack(pady=(20, 0))
        tk.Label(weather, text=f'{self.weather_data["temp"]}°C', font=self.font_h1, bg=self.colors["panel"], fg=self.colors["text"]).pack()
        tk.Label(weather, text=self.weather_data["text"], font=self.font_body, bg=self.colors["panel"], fg=self.colors["muted"]).pack()
        tk.Label(weather, text=CONFIG["city"], font=self.font_small, bg=self.colors["panel"], fg=self.colors["green"]).pack(pady=(8, 0))

        spotify = self.card(grid, row=1, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(spotify, text="♫", font=self.font_tile_icon, bg=self.colors["panel"], fg=self.colors["green"]).pack(side="left", padx=18)
        txt = tk.Frame(spotify, bg=self.colors["panel"])
        txt.pack(side="left", fill="both", expand=True, pady=18)
        tk.Label(txt, text="Spotify", font=self.font_h2, bg=self.colors["panel"], fg=self.colors["text"]).pack(anchor="w")
        tk.Label(txt, text="Moduł Spotify wraca w v4.1 jako natywna część aplikacji.", font=self.font_small, bg=self.colors["panel"], fg=self.colors["muted"]).pack(anchor="w")

        system = self.card(grid, row=1, column=1, sticky="nsew")
        temp = cpu_temp()
        tk.Label(system, text="Raspberry", font=self.font_small, bg=self.colors["panel"], fg=self.colors["green"]).pack(anchor="w", padx=16, pady=(16, 0))
        tk.Label(system, text=f"CPU {temp:.1f}°C", font=self.font_h2, bg=self.colors["panel"], fg=self.colors["text"]).pack(anchor="w", padx=16, pady=(8, 0))
        tk.Label(system, text=f"RAM {ram_percent():.0f}%", font=self.font_body, bg=self.colors["panel"], fg=self.colors["muted"]).pack(anchor="w", padx=16, pady=(8, 0))

        self.toast("Dashboard")

    def show_spotify_placeholder(self):
        self.screen = "spotify"
        self.clear_content()

        page = tk.Frame(self.content, bg=self.colors["panel"], highlightthickness=1, highlightbackground="#243244")
        page.pack(fill="both", expand=True)

        tk.Label(page, text="Spotify", font=self.font_small, bg=self.colors["panel"], fg=self.colors["green"]).pack(anchor="w", padx=24, pady=(24, 0))
        tk.Label(page, text="Moduł Spotify", font=self.font_h1, bg=self.colors["panel"], fg=self.colors["text"]).pack(anchor="w", padx=24, pady=(10, 0))
        tk.Label(
            page,
            text=(
                "W v4.0 Alpha przenieśliśmy projekt z przeglądarki do aplikacji.\n\n"
                "Spotify wróci w v4.1 jako natywny moduł aplikacji:\n"
                "• teraz gra\n"
                "• play/pauza\n"
                "• wyszukiwarka\n"
                "• playlisty\n"
                "• własna klawiatura ekranowa\n\n"
                "Najpierw testujemy stabilność aplikacji na ekranie 7 cali."
            ),
            font=self.font_body,
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            justify="left"
        ).pack(anchor="w", padx=24, pady=18)

        tk.Button(
            page,
            text="Wróć do dashboardu",
            font=self.font_body,
            bg=self.colors["green"],
            fg="#041107",
            relief="flat",
            command=self.show_home
        ).pack(anchor="w", padx=24, pady=10, ipadx=18, ipady=8)

        self.toast("Spotify będzie w v4.1")

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

        tk.Button(
            page,
            text="Odśwież pogodę",
            font=self.font_body,
            bg=self.colors["green"],
            fg="#041107",
            relief="flat",
            command=self.refresh_weather_now
        ).pack(ipadx=18, ipady=8)

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
        tk.Label(
            page,
            text=(
                f"Wersja: {APP_VERSION}\n"
                f"Miasto: {CONFIG['city']}\n"
                f"Ekran: 1024×600\n\n"
                "ESC wyłącza pełny ekran.\n"
                "F11 przełącza pełny ekran.\n\n"
                "Kolejny etap: v4.1 Spotify Native."
            ),
            font=self.font_body,
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            justify="left"
        ).pack(anchor="w", padx=24, pady=18)

        tk.Button(
            page,
            text="Zamknij aplikację",
            font=self.font_body,
            bg=self.colors["red"],
            fg="white",
            relief="flat",
            command=self.root.destroy
        ).pack(anchor="w", padx=24, pady=10, ipadx=18, ipady=8)

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
        self.status_label.configure(text=f"{wifi} • CPU {temp:.1f}°C • MD")

        if self.screen == "system":
            self.update_system_screen()

        self.root.after(3000, self.tick_system)

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
    root = tk.Tk()
    app = SmartHubApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
