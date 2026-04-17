import { render as renderAdmin } from '/plugins/admin/ui/index.js';

const routes = {
  '/admin': renderAdmin
};

function renderRoute() {
  const path = window.location.pathname;
  const app = document.getElementById('app');

  if (routes[path]) {
    routes[path](app);
  } else {
    app.innerHTML = '<h1>Welcome</h1><a href="/admin">Admin</a>';
  }
}

window.addEventListener('popstate', renderRoute);
renderRoute();
