export async function render(container) {
  container.innerHTML = `
    <h1>Home Assistant</h1>
    <div id="ha-root">Loading...</div>
  `;

  try {
    const res = await fetch('/api/plugins/home_assistant/status');
    const data = await res.json();
    document.getElementById('ha-root').innerHTML = `
      <div class="grid">
        <div class="card"><strong>Configured</strong><div>${data.configured ? 'Yes' : 'No'}</div></div>
        <div class="card"><strong>Status Events</strong><div>${data.send_status_events ? 'Enabled' : 'Disabled'}</div></div>
        <div class="card"><strong>Retry Count</strong><div>${data.retry_count}</div></div>
      </div>
      <div class="card">
        <h2>Routing</h2>
        <pre>${JSON.stringify(data.routing || {}, null, 2)}</pre>
      </div>
      <div class="card">
        <h2>Delivery Failures</h2>
        <pre>${JSON.stringify(data.delivery_failures || {}, null, 2)}</pre>
      </div>
      <button onclick="window.testHomeAssistant()">Send Test</button>
    `;

    window.testHomeAssistant = async () => {
      await fetch('/api/plugins/home_assistant/test');
      render(container);
    };
  } catch (e) {
    const el = document.getElementById('ha-root');
    if (el) el.textContent = `Failed to load status: ${e}`;
  }
}

export const ui = {
  route: '/home-assistant',
  title: 'Home Assistant',
  render
};
