const routes = {};
const navItems = [];

export function registerRoute(path, renderer, title) {
  routes[path] = renderer;
  if (!navItems.find(i => i.path === path)) {
    navItems.push({ path, title });
  }
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

// dynamic plugin UI loading
fetch('/api/ui/plugins')
  .then(r => r.json())
  .then(plugins => {
    Promise.all(
      plugins.map(p =>
        import(`/plugins/${p.plugin}/ui/index.js`).then(mod => {
          if (mod.ui) {
            registerRoute(p.route, mod.ui.render, p.title);
          }
        })
      )
    ).then(() => renderRoute());
  })
  .catch(() => {
    document.getElementById('app').innerHTML = '<h1>Failed to load plugins</h1>';
  });
