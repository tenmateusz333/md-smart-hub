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

  if (id === "spotify") {
    toast("Ekran Spotify");
  } else {
    toast("Dashboard");
  }
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

updateClock();
setInterval(updateClock, 1000);
