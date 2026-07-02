const config = {
  city: "Warszawa",
  latitude: 52.2297,
  longitude: 21.0122
};

function updateClock() {
  const now = new Date();
  document.getElementById("time").textContent = now.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
  document.getElementById("date").textContent = now.toLocaleDateString("pl-PL", { weekday: "long", day: "numeric", month: "long" });
}

function showScreen(id) {
  document.querySelectorAll(".screen").forEach(screen => screen.classList.remove("active"));
  document.getElementById(id).classList.add("active");
  if (id === "home") toast("Dashboard");
  if (id === "spotify") toast("Ekran Spotify");
  if (id === "weather") toast("Pogoda online");
  if (id === "system") toast("Dane Raspberry");
}

function toast(text) {
  const el = document.getElementById("toast");
  el.textContent = text;
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => { el.textContent = "System gotowy"; }, 3000);
}

function fmtMs(ms) {
  if (!ms || ms < 0) return "0:00";
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const r = String(s % 60).padStart(2, "0");
  return `${m}:${r}`;
}

function connectSpotify() {
  window.location.href = "/spotify/login";
}

async function spotifyControl(action) {
  try {
    await fetch(`/api/spotify/control/${action}`, { method: "POST" });
    setTimeout(loadSpotify, 500);
  } catch (e) {
    toast("Błąd sterowania Spotify");
  }
}

function setCover(el, url, fallback = "🎧") {
  if (url) {
    el.textContent = "";
    el.style.backgroundImage = `url('${url}')`;
  } else {
    el.style.backgroundImage = "";
    el.textContent = fallback;
  }
}

async function loadSpotify() {
  try {
    const res = await fetch("/api/spotify/status");
    const data = await res.json();

    const status = document.getElementById("spotifyStatus");
    const loginBtn = document.getElementById("spotifyLoginBtn");

    if (!data.connected) {
      status.textContent = "Spotify ?";
      loginBtn.textContent = "Połącz Spotify";
      document.getElementById("spotifyTitle").textContent = "Spotify";
      document.getElementById("spotifyArtist").textContent = "Połącz konto Spotify.";
      document.getElementById("homeTrack").textContent = "Web Player";
      document.getElementById("homeArtist").textContent = "Dotknij, żeby otworzyć odtwarzacz.";
      setCover(document.getElementById("spotifyCover"), null);
      setCover(document.getElementById("homeCover"), null);
      return;
    }

    status.textContent = "Spotify ✓";
    loginBtn.textContent = "Otwórz Spotify Web";

    if (!data.playing_track) {
      document.getElementById("spotifyTitle").textContent = "Brak aktywnego utworu";
      document.getElementById("spotifyArtist").textContent = "Włącz muzykę w Spotify.";
      document.getElementById("homeTrack").textContent = "Brak utworu";
      document.getElementById("homeArtist").textContent = "Włącz muzykę.";
      setCover(document.getElementById("spotifyCover"), null);
      setCover(document.getElementById("homeCover"), null);
      document.getElementById("spotifyProgress").style.width = "0%";
      return;
    }

    document.getElementById("spotifyTitle").textContent = data.track_name;
    document.getElementById("spotifyArtist").textContent = data.artist_name;
    document.getElementById("homeTrack").textContent = data.track_name;
    document.getElementById("homeArtist").textContent = data.artist_name;
    document.getElementById("spotifyPlay").textContent = data.is_playing ? "⏸" : "▶";
    document.getElementById("spotifyElapsed").textContent = fmtMs(data.progress_ms);
    document.getElementById("spotifyDuration").textContent = fmtMs(data.duration_ms);

    const pct = data.duration_ms ? Math.min(100, (data.progress_ms / data.duration_ms) * 100) : 0;
    document.getElementById("spotifyProgress").style.width = `${pct}%`;

    setCover(document.getElementById("spotifyCover"), data.album_image);
    setCover(document.getElementById("homeCover"), data.album_image);
  } catch (e) {
    document.getElementById("spotifyStatus").textContent = "Spotify ?";
  }
}

function openSpotify() {
  window.location.href = "https://open.spotify.com";
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

loadSpotify();
setInterval(loadSpotify, 2000);
