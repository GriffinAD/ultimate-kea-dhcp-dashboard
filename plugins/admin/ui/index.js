import { renderHealth } from "./health.js";
import { renderAlerts } from "./alerts.js";

export function render(container) {
  container.innerHTML = `
    <h1>Admin Dashboard</h1>
    <div class="grid">
      <button onclick="nav('health')">Health</button>
      <button onclick="nav('alerts')">Alerts</button>
    </div>
    <div id="admin-content"></div>
  `;

  window.nav = (page) => {
    const el = document.getElementById("admin-content");
    if (page === "health") renderHealth(el);
    if (page === "alerts") renderAlerts(el);
  };

  window.nav("health");
}

export const ui = {
  route: '/admin',
  title: 'Admin',
  render
};
