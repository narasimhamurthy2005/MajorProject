// Mirrors backend/thresholds.py bands, just enough to color-code cards client-side.
const BANDS = {
  temperature:        { warnLow: -10, critLow: -25, critHigh: 80, warnHigh: 65, unit: "°C" },
  battery_voltage:    { warnLow: 24, critLow: 21, critHigh: 37, warnHigh: 35, unit: "V" },
  solar_panel_output: { warnLow: 50, critLow: 30, critHigh: 160, warnHigh: 145, unit: "W" },
  signal_strength:    { warnLow: 40, critLow: 20, critHigh: 999, warnHigh: 999, unit: "%" },
  fuel_level:         { warnLow: 20, critLow: 10, critHigh: 999, warnHigh: 999, unit: "%" },
  attitude_error:     { warnLow: -999, critLow: -999, critHigh: 5, warnHigh: 2, unit: "°" },
};

const CARD_PARAMS = ["temperature", "battery_voltage", "solar_panel_output", "signal_strength", "fuel_level", "attitude_error"];
const LABELS = {
  temperature: "Temperature", battery_voltage: "Battery Voltage", solar_panel_output: "Solar Output",
  signal_strength: "Signal Strength", fuel_level: "Fuel Level", attitude_error: "Attitude Error",
};

let currentSatId = null;
let tempBattChart, solarSignalChart;
let refreshTimer = null;

function statusFor(param, value) {
  const b = BANDS[param];
  if (!b) return "ok";
  if (value <= b.critLow || value >= b.critHigh) return "high";
  if (value <= b.warnLow || value >= b.warnHigh) return "low";
  return "ok";
}

function renderHealthCards(latest) {
  const wrap = document.getElementById("health-cards");
  wrap.innerHTML = "";
  CARD_PARAMS.forEach((param) => {
    const value = latest[param];
    const status = statusFor(param, value);
    const dotClass = status === "high" ? "status-high" : status === "low" ? "status-low" : "status-ok";
    const div = document.createElement("div");
    div.className = "panel stat-card";
    div.innerHTML = `
      <div class="label"><span class="status-dot ${dotClass}"></span>${LABELS[param]}</div>
      <div class="value">${value.toFixed(1)}<span style="font-size:16px;color:var(--text-dim);">${BANDS[param].unit}</span></div>
    `;
    wrap.appendChild(div);
  });
}

function buildChart(ctx, labels, datasets) {
  return new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      animation: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { ticks: { color: "#93a0b8", maxTicksLimit: 6 }, grid: { color: "rgba(255,255,255,0.05)" } },
        y: { ticks: { color: "#93a0b8" }, grid: { color: "rgba(255,255,255,0.05)" } },
      },
      plugins: { legend: { labels: { color: "#e8edf7" } } },
    },
  });
}

function fmtTime(ts) {
  return new Date(ts + "Z").toLocaleTimeString();
}

async function loadCharts(satId) {
  const history = await apiGet(`/satellites/${satId}/telemetry?limit=60`);
  const labels = history.map((h) => fmtTime(h.timestamp));

  const tempData = history.map((h) => h.temperature);
  const battData = history.map((h) => h.battery_voltage);
  const solarData = history.map((h) => h.solar_panel_output);
  const signalData = history.map((h) => h.signal_strength);

  if (tempBattChart) tempBattChart.destroy();
  if (solarSignalChart) solarSignalChart.destroy();

  tempBattChart = buildChart(document.getElementById("chart-temp-batt"), labels, [
    { label: "Temperature (°C)", data: tempData, borderColor: "#4fd6ff", tension: 0.3, pointRadius: 0 },
    { label: "Battery Voltage (V)", data: battData, borderColor: "#7c5cff", tension: 0.3, pointRadius: 0 },
  ]);
  solarSignalChart = buildChart(document.getElementById("chart-solar-signal"), labels, [
    { label: "Solar Output (W)", data: solarData, borderColor: "#4dffb0", tension: 0.3, pointRadius: 0 },
    { label: "Signal Strength (%)", data: signalData, borderColor: "#ffb84d", tension: 0.3, pointRadius: 0 },
  ]);
}

async function loadAnomalies(satId) {
  const all = await apiGet(`/anomalies?resolved=0`);
  const filtered = all.filter((a) => a.satellite_id === satId).slice(0, 15);
  const tbody = document.querySelector("#sat-anomaly-table tbody");
  tbody.innerHTML = "";
  document.getElementById("no-anomalies").style.display = filtered.length ? "none" : "block";
  filtered.forEach((a) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${fmtTime(a.timestamp)}</td>
      <td>${a.parameter}</td>
      <td><span class="badge badge-${a.severity}">${a.severity.toUpperCase()}</span></td>
      <td>${a.description}</td>
    `;
    tbody.appendChild(tr);
  });
}

async function refreshAll() {
  if (!currentSatId) return;
  try {
    const latest = await apiGet(`/satellites/${currentSatId}/latest`);
    renderHealthCards(latest);
    await loadCharts(currentSatId);
    await loadAnomalies(currentSatId);
  } catch (e) {
    console.error(e);
  }
}

async function init() {
  const select = document.getElementById("sat-select");
  let sats = [];
  try {
    sats = await apiGet("/satellites");
  } catch (e) {
    document.querySelector(".container").innerHTML =
      '<p style="color:#ff4d6d;">Could not reach the backend at http://127.0.0.1:8000 — make sure the FastAPI server is running (see README).</p>';
    return;
  }

  sats.forEach((sat) => {
    const opt = document.createElement("option");
    opt.value = sat.id;
    opt.textContent = `${sat.name} (${sat.type})`;
    select.appendChild(opt);
  });

  select.addEventListener("change", () => {
    currentSatId = parseInt(select.value, 10);
    const sat = sats.find((s) => s.id === currentSatId);
    document.getElementById("sat-meta").textContent =
      `${sat.orbit_type} orbit · nominal altitude ${sat.nominal_altitude_km} km · launched ${sat.launch_date}`;
    refreshAll();
  });

  if (sats.length) {
    currentSatId = sats[0].id;
    select.value = currentSatId;
    select.dispatchEvent(new Event("change"));
  }

  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = setInterval(refreshAll, 5000);
}

init();
