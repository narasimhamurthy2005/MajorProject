let currentFilter = "all";

function fmtTime(ts) {
  return new Date(ts + "Z").toLocaleString();
}

async function loadStats() {
  const stats = await apiGet("/anomalies/stats");
  document.getElementById("stat-high").textContent = stats.high;
  document.getElementById("stat-low").textContent = stats.low;
  document.getElementById("stat-total").textContent = stats.high + stats.low;
}

async function loadTable() {
  const severityParam = currentFilter === "all" ? "" : `?severity=${currentFilter}`;
  const rows = await apiGet(`/anomalies${severityParam}`);
  const tbody = document.querySelector("#anomaly-table tbody");
  tbody.innerHTML = "";
  document.getElementById("no-anomalies").style.display = rows.length ? "none" : "block";

  rows.forEach((a) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${fmtTime(a.timestamp)}</td>
      <td>${a.satellite_name}</td>
      <td>${a.parameter}</td>
      <td>${a.value.toFixed(2)}</td>
      <td><span class="badge badge-${a.severity}">${a.severity.toUpperCase()}</span></td>
      <td>${a.description}</td>
      <td><button data-id="${a.id}" class="resolve-btn">Resolve</button></td>
    `;
    tbody.appendChild(tr);
  });

  document.querySelectorAll(".resolve-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      btn.textContent = "...";
      await apiPost(`/anomalies/${btn.dataset.id}/resolve`, {});
      await refresh();
    });
  });
}

async function refresh() {
  try {
    await Promise.all([loadStats(), loadTable()]);
  } catch (e) {
    console.error(e);
  }
}

document.querySelectorAll(".filter-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("primary"));
    btn.classList.add("primary");
    currentFilter = btn.dataset.filter;
    refresh();
  });
});

refresh();
setInterval(refresh, 5000);
