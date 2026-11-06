import { label } from './module.js';

const set = (id, text) => {
  const node = document.getElementById(id);
  if (node) node.textContent = text;
};

set('module', `module: ${label}`);

try {
  sessionStorage.setItem('mdview-second-origin', 'ok');
  set('storage', `storage: ${sessionStorage.getItem('mdview-second-origin')}`);
} catch (error) {
  set('storage', `storage: ${error.name}`);
}

fetch('./data.json', { cache: 'no-store' })
  .then((response) => response.json())
  .then((data) => set('fetch', `fetch: ${data.value}`))
  .catch((error) => set('fetch', `fetch: ${error.name}`));

fetch('./app.css', { cache: 'no-store' })
  .then((response) => {
    const type = response.headers.get('content-type') || '';
    return response.text().then((text) => ({
      ok: response.ok && type.startsWith('text/css') && text.includes('background'),
      type: `${response.status} ${type}`,
    }));
  })
  .then((result) => set('mime', `mime: ${result.ok ? 'ok' : result.type}`))
  .catch((error) => set('mime', `mime: ${error.name}`));

if ('serviceWorker' in navigator) {
  navigator.serviceWorker
    .register('./sw.js')
    .then(() => set('sw', 'sw: registered'))
    .catch((error) => set('sw', `sw: ${error.name}`));
} else {
  set('sw', 'sw: unavailable');
}

set('title', 'HTML second origin ok');
