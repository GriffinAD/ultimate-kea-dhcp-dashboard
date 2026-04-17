async function loadRules(container) {
  const res = await fetch('/api/automation/rules');
  const rules = await res.json();

  container.innerHTML = `
    <h2>Rules</h2>
    <button onclick="window.addRule()">Add Rule</button>
    <div id="rule-list">
      ${rules.map((r, i) => `
        <div class="card">
          <strong>${r.event}</strong>
          <pre>${JSON.stringify(r.actions, null, 2)}</pre>
          <button onclick="window.deleteRule(${i})">Delete</button>
        </div>
      `).join('')}
    </div>
  `;
}

export async function render(container) {
  container.innerHTML = `<h1>Automation</h1><div id="automation-root"></div>`;
  const root = document.getElementById('automation-root');

  await loadRules(root);

  window.addRule = async () => {
    const event = prompt('Event type (e.g. plugin.failure)');
    if (!event) return;

    const url = prompt('Webhook URL');
    if (!url) return;

    await fetch('/api/automation/rules/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event,
        actions: [{ type: 'webhook', url }]
      })
    });

    loadRules(root);
  };

  window.deleteRule = async (index) => {
    await fetch('/api/automation/rules/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ index })
    });

    loadRules(root);
  };
}

export const ui = {
  route: '/automation',
  title: 'Automation',
  render
};
