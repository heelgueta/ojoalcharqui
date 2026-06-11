// theme toggle (persisted)
(function () {
  const root = document.documentElement;
  const saved = localStorage.getItem("oac-theme");
  if (saved) root.setAttribute("data-theme", saved);
  const btn = document.getElementById("theme-toggle");
  if (btn) btn.addEventListener("click", () => {
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("oac-theme", next);
  });
})();

// global pulse: shows busy if any scrape running
async function pollPulse() {
  try {
    const r = await fetch("/api/progress");
    const all = await r.json();
    const busy = Object.values(all).some(p => p.status === "running");
    const el = document.getElementById("pulse");
    if (el) {
      el.classList.toggle("busy", busy);
      el.textContent = busy ? "● scrapeando…" : "● en línea";
    }
  } catch (e) {}
}
setInterval(pollPulse, 2500); pollPulse();
