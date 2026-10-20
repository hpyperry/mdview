import './styles/app.css';
import { islands } from './islands';
import type { IslandDefinition } from './types';

type IdleWindow = Window & {
  requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
};

function markMounted(name: string): void {
  const diagnostics = window.__mdviewIslands;
  if (diagnostics && !diagnostics.mounted.includes(name)) diagnostics.mounted.push(name);
}

function markError(name: string, error: unknown): void {
  const diagnostics = window.__mdviewIslands;
  const message = `${name}: ${error instanceof Error ? error.message : String(error)}`;
  diagnostics?.errors.push(message);
  console.error(`[mdview] island ${name} failed`, error);
}

function run(island: IslandDefinition): void {
  try {
    const result = island.mount();
    if (result && typeof (result as Promise<void>).catch === 'function') {
      (result as Promise<void>).catch((error) => markError(island.name, error));
    }
    markMounted(island.name);
  } catch (error) {
    markError(island.name, error);
  }
}

function mountVisible(island: IslandDefinition, root: Element): void {
  if (!('IntersectionObserver' in window)) {
    run(island);
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    if (!entries.some((entry) => entry.isIntersecting)) return;
    observer.disconnect();
    run(island);
  }, { rootMargin: '1200px 0px' });
  observer.observe(root);
}

function mountIdle(island: IslandDefinition): void {
  const idle = (window as IdleWindow).requestIdleCallback;
  if (idle) idle(() => run(island), { timeout: 1000 });
  else window.setTimeout(() => run(island), 0);
}

function boot(): void {
  document.documentElement.classList.remove('no-js');
  document.documentElement.classList.add('js');
  window.__mdviewIslands = { mounted: [], errors: [] };

  const manifest = (document.body.dataset.islands || '').split(/\s+/).filter(Boolean);
  for (const name of manifest) {
    const island = islands[name];
    if (!island) continue;
    const root = island.root?.() ?? document.body;
    if (!root) continue;
    if (island.when === 'immediate') run(island);
    else if (island.when === 'idle') mountIdle(island);
    else mountVisible(island, root);
  }
  document.documentElement.dataset.islandsReady = 'ready';
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot, { once: true });
} else {
  boot();
}
