export async function render(container) {
  container.innerHTML = `
    <h1>Kea HA</h1>
    <div id="kea-root">Loading...</div>
  `;

  try {
    const res = await fetch('/api/plugins/kea-ha/status');
    const data = await res.json();
    const nodes = data.nodes || {};
    const active = data.active_node || 'Unknown';
    const partnerDown = (data.partner_down_nodes || []).join(', ') || 'None';

    document.getElementById('kea-root').innerHTML = `
      <div class="grid">
        <div class="card"><strong>Active Node</strong><div>${active}</div></div>
        <div class="card"><strong>Partner Down</strong><div>${partnerDown}</div></div>
      </div>
      <div class="card">
        <h2>Nodes</h2>
        ${Object.entries(nodes).map(([name, node]) => `
          <div class="card">
            <strong>${name}</strong>
            <div>Reachable: ${node.reachable ? 'Yes' : 'No'}</div>
            <div>Local State: ${node.local_state || 'Unknown'}</div>
            <div>Remote State: ${node.remote_state || 'Unknown'}</div>
          </div>
        `).join('')}
      </div>
    `;
  } catch (e) {
    const el = document.getElementById('kea-root');
    if (el) el.textContent = `Failed to load status: ${e}`;
  }
}

export const ui = {
  route: '/kea',
  title: 'Kea HA',
  render
};
