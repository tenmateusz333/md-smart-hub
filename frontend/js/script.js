const config = {
  city: "Warszawa",
  latitude: 52.2297,
  longitude: 21.0122
};

function updateClock() {
  const now = new Date();

  document.getElementById("time").textContent = now.toLocaleTimeString("pl-PL", {
    hour: "2-digit",
    minute: "2-digit"
  });

  document.getElementById("date").textContent = now.toLocaleDateString("pl-PL", {
    weekday: "long",
    day: "numeric",
    month: "long"
  });
}

function showScreen(id) {
  document.querySelectorAll(".screen").forEach(screen => {
    screen.classList.remove("active");
  });

  document.getElementById(id).classList.add("active");

  if (id === "home") toast("Dashboard");
  if (id === "spotify") toast("Ekran Spotify");
  if (id === "weather") toast("Pogoda online");
  if (id === "system") toast("Dane Raspberry");
}

function openSpotify() {
  toast("Otwieram Spotify...");
  setTimeout(() => {
    window.location.href = "https://open.spotify.com";
  }, 500);
}

function toast(text) {
  const el = document.getElementById("toast");
  el.textContent = text;
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => {
    el.textContent = "System gotowy";
  }, 3000);
}

function codeIcon(code) {
  if (code === 0) return "☀️";
  if ([1, 2].includes(code)) return "🌤️";
  if (code === 3) return "☁️";
  if ([45, 48].includes(code)) return "🌫️";
  if ([51, 53, 55, 61, 63, 65, 80, 81, 82].includes(code)) return "🌧️";
  if ([71, 73, 75, 77, 85, 86].includes(code)) return "❄️";
  if ([95, 96, 99].includes(code)) return "⛈️";
  return "🌤️";
}

function codeText(code) {
  if (code === 0) return "Bezchmurnie";
  if ([1, 2].includes(code)) return "Częściowe zachmurzenie";
  if (code === 3) return "Pochmurno";
  if ([45, 48].includes(code)) return "Mgła";
  if ([51, 53, 55].includes(code)) return "Mżawka";
  if ([61, 63, 65, 80, 81, 82].includes(code)) return "Deszcz";
  if ([71, 73, 75, 77, 85, 86].includes(code)) return "Śnieg";
  if ([95, 96, 99].includes(code)) return "Burza";
  return "Pogoda";
}

async function loadWeather() {
  try {
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${config.latitude}&longitude=${config.longitude}&current=temperature_2m,weather_code,wind_speed_10m&timezone=auto`;
    const res = await fetch(url);
    const data = await res.json();
    const current = data.current;

    const temp = Math.round(current.temperature_2m);
    const code = current.weather_code;
    const wind = Math.round(current.wind_speed_10m);

    document.getElementById("weatherTile").textContent = `${temp}°C`;
    document.getElementById("weatherTemp").textContent = `${temp}°C`;
    document.getElementById("weatherDesc").textContent = codeText(code);
    document.getElementById("weatherIcon").textContent = codeIcon(code);
    document.getElementById("homeWeatherIcon").textContent = codeIcon(code);
    document.getElementById("wind").textContent = `${wind} km/h`;
    document.getElementById("city").textContent = config.city;
  } catch (error) {
    document.getElementById("weatherDesc").textContent = "Brak połączenia";
    toast("Pogoda offline");
  }
}

function setBar(id, value, max = 100) {
  const el = document.getElementById(id);
  const width = Math.max(1, Math.min(100, (value / max) * 100));
  el.style.width = `${width}%`;

  if (width > 80) el.style.background = "var(--red)";
  else if (width > 60) el.style.background = "var(--warn)";
  else el.style.background = "var(--green)";
}

function formatUptime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);

  if (h > 24) {
    const d = Math.floor(h / 24);
    return `${d}d ${h % 24}h`;
  }

  return `${h}h ${m}m`;
}

async function loadSystem() {
  try {
    const res = await fetch("/api/system");
    const data = await res.json();

    const temp = Number(data.cpu_temp).toFixed(1);
    const cpu = Math.round(data.cpu_percent);
    const ram = Math.round(data.ram_percent);

    document.getElementById("tempTile").textContent = `${temp}°C`;
    document.getElementById("topTemp").textContent = `CPU ${temp}°C`;
    document.getElementById("cpuTemp").textContent = `${temp}°C`;
    document.getElementById("cpuLoad").textContent = `${cpu}%`;
    document.getElementById("ram").textContent = `${ram}%`;
    document.getElementById("uptime").textContent = formatUptime(data.uptime_seconds);

    setBar("tempBar", Number(temp), 85);
    setBar("cpuBar", cpu);
    setBar("ramBar", ram);

    document.getElementById("wifi").textContent = data.online ? "Wi‑Fi ✓" : "Wi‑Fi ?";
  } catch (error) {
    toast("API systemu offline");
  }
}

updateClock();
setInterval(updateClock, 1000);

loadWeather();
setInterval(loadWeather, 600000);

loadSystem();
setInterval(loadSystem, 3000);
