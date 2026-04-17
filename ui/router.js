const routes = {};
const navItems = [];

export function registerRoute(path, renderer, title) {
  routes[path] = renderer;
  navItems.push({ path, title });
}

export function navigate(path) {
  window.history.pushState({}, '', path);
  renderRoute();
}

function renderNav() {
  return `<nav>${navItems.map(i =>
    `<a href="${i.path}" onclick="event.preventDefault(); window.navigate('${i.path}')">${i.title}</a>`
  ).join(' | ')}</nav>`;
}

function renderRoute() {
  const path = window.location.pathname;
  const app = document.getElementById('app');

  if (routes[path]) {
    app.innerHTML = renderNav() + '<div id="page"></div>';
    routes[path](document.getElementById('page'));
  } else {
    app.innerHTML = `<h1>Kea Dashboard</h1>${renderNav()}`;
  }
}

window.addEventListener('popstate', renderRoute);
window.navigate = navigate;

// register plugin UIs
import { render as renderAdmin } from '/plugins/admin/ui/index.js';
import { ui as automationUI } from '/plugins/automation_engine/ui/index.js';

registerRoute('/admin', renderAdmin, 'Admin');
registerRoute(automationUI.route, automationUI.render, automationUI.title);

renderRoute();
