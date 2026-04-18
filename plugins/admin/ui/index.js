import { renderHealth } from "./health.js";
import { renderAlerts } from "./alerts.js";

async function renderPlugins(container) {
  container.innerHTML = `<h2>Plugins</h2><div id="plugin-list">Loading...</div>`;

  try {
    const res = await fetch('/api/plugins/admin/plugins');
    const plugins = await res.json();
    const list = document.getElementById('plugin-list');

    list.innerHTML = plugins.map(p => `
      <div class="card">
        <strong>${p.id}</strong>
        <div>Status: ${p.enabled ? 'Enabled' : 'Disabled'}</div>
        <button onclick="window.restartPlugin('${p.id}')">Restart</button>
        <button onclick="window.togglePlugin('${p.id}', ${p.configured_enabled})">
          ${p.configured_enabled ? 'Disable' : 'Enable'}
        </button>
      </div>
    `).join('');

    window.restartPlugin = async (plugin) => {
      await fetch('/api/plugins/admin/plugins/restart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plugin })
      });
      renderPlugins(container);
    };

    window.togglePlugin = async (plugin, enabled) => {
      const url = enabled
        ? '/api/plugins/admin/plugins/disable'
        : '/api/plugins/admin/plugins/enable';

      await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plugin })
      });

      renderPlugins(container);
    };
  } catch (e) {
    const list = document.getElementById('plugin-list');
    if (list) list.textContent = `Failed to load plugins: ${e}`;
  }
}

async function renderMarketplace(container) {
  container.innerHTML = `<h2>Marketplace</h2><div id="marketplace-list">Loading...</div>`;

  try {
    const res = await fetch('/api/plugins/admin/marketplace/plugins');
    const plugins = await res.json();
    const list = document.getElementById('marketplace-list');

    list.innerHTML = plugins.map(p => `
      <div class="card">
        <strong>${p.name}</strong>
        <div>Version: ${p.version}</div>
        <div>Status: ${p.installed ? 'Installed' : 'Not Installed'}</div>
        ${p.installed
          ? `<span class="status-ok">Installed</span>`
          : `<button onclick="window.installPlugin('${p.id}')">Install</button>`}
      </div>
    `).join('');

    window.installPlugin = async (plugin) => {
      await fetch('/api/plugins/admin/marketplace/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plugin })
      });
      renderMarketplace(container);
    };
  } catch (e) {
    const list = document.getElementById('marketplace-list');
    if (list) list.textContent = `Failed to load marketplace: ${e}`;
  }
}

export function render(container) {
  container.innerHTML = `
    <h1>Admin Dashboard</h1>
    <div class="grid">
      <button onclick="nav('health')">Health</button>
      <button onclick="nav('alerts')">Alerts</button>
      <button onclick="nav('plugins')">Plugins</button>
      <button onclick="nav('marketplace')">Marketplace</button>
    </div>
    <div id="admin-content"></div>
  `;

  window.nav = (page) => {
    const el = document.getElementById("admin-content");
    if (page === "health") renderHealth(el);
    if (page === "alerts") renderAlerts(el);
    if (page === "plugins") renderPlugins(el);
    if (page === "marketplace") renderMarketplace(el);
  };

  window.nav("health");
}

export const ui = {
  route: '/admin',
  title: 'Admin',
  render
};
