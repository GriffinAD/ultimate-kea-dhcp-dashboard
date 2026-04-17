export async function renderAlerts(container) {
  async function load() {
    const alerts = await fetch("/api/admin/alerts").then(r => r.json());

    container.innerHTML = `
      <h2>Alerts</h2>
      ${alerts.map(a => `
        <div>
          <b>${a.plugin || "system"}</b>
          <div>${a.message}</div>
        </div>
      `).join("")}
    `;
  }

  await load();
  setInterval(load, 5000);
}
