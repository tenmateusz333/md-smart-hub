#!/usr/bin/env python3
import json
import os
import subprocess
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
BOOT_TIME = time.time()
_last_cpu = None

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
    def do_GET(self):
        if self.path == "/api/system":
            data = {
                "cpu_temp": cpu_temp(),
                "cpu_percent": cpu_percent(),
                "ram_percent": ram_percent(),
                "uptime_seconds": int(time.time() - BOOT_TIME),
                "online": is_online()
            }

            body = json.dumps(data).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        return super().do_GET()

if __name__ == "__main__":
    os.chdir(FRONTEND_ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("MD Smart Hub OS running at http://127.0.0.1:8765")
    server.serve_forever()
