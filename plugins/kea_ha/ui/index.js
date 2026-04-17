export async function render(container) {
  container.innerHTML = `
    <h1>Kea HA</h1>
    <div class="card">
      <h2>Status</h2>
      <pre id="kea-status">Loading...</pre>
    </div>
  `;

  try {
    const res = await fetch('/api/plugins/kea-ha/status');
    const data = await res.json();
    const el = document.getElementById('kea-status');
    if (el) el.textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    const el = document.getElementById('kea-status');
    if (el) el.textContent = `Failed to load status: ${e}`;
  }
}

export const ui = {
  route: '/kea',
  title: 'Kea HA',
  render
};
