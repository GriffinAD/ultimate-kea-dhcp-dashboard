export async function renderHealth(container) {
  const data = await fetch("/api/admin/health").then(r => r.json());

  container.innerHTML = `
    <h2>Plugin Health</h2>
    ${Object.entries(data).map(([id, h]) => `
      <div>
        <b>${id}</b> - ${h.status}
        <div>${h.message || ""}</div>
      </div>
    `).join("")}
  `;
}
