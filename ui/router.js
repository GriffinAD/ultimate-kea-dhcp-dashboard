const routes = {};

export function registerRoute(path, renderer) {
  routes[path] = renderer;
}

export function navigate(path) {
  window.history.pushState({}, '', path);
  renderRoute();
}

function renderRoute() {
  const path = window.location.pathname;
  const app = document.getElementById('app');

  if (routes[path]) {
    routes[path](app);
  } else {
    app.innerHTML = `<h1>Kea Dashboard</h1>
      <nav>
        <a href="/admin" onclick="event.preventDefault(); window.navigate('/admin')">Admin</a>
      </nav>`;
  }
}

window.addEventListener('popstate', renderRoute);
window.navigate = navigate;

// register built-in routes
import { render as renderAdmin } from '/plugins/admin/ui/index.js';
registerRoute('/admin', renderAdmin);

renderRoute();
