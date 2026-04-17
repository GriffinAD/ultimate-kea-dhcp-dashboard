export function render(container) {
  container.innerHTML = `
    <h1>Automation</h1>
    <div class="card">
      <h2>Rules</h2>
      <pre id="automation-rules">Loading...</pre>
    </div>
  `;

  fetch('/api/automation/rules')
    .then(r => r.json())
    .then(data => {
      const el = document.getElementById('automation-rules');
      if (el) el.textContent = JSON.stringify(data, null, 2);
    })
    .catch(err => {
      const el = document.getElementById('automation-rules');
      if (el) el.textContent = `Failed to load rules: ${err}`;
    });
}

export const ui = {
  route: '/automation',
  title: 'Automation',
  render
};
