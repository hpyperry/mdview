import { readPref, savePref } from '../utils';

export function mountSidebar(): void {
  const toggle = document.getElementById('sidebar-toggle');
  const scrim = document.getElementById('scrim');
  if (!toggle) return;

  const root = document.documentElement;
  const narrow = window.matchMedia('(max-width: 900px)');

  function syncScrim(): void {
    if (!scrim) return;
    scrim.hidden = !(narrow.matches && root.dataset.sidebarOpen === '1');
  }

  function closeDrawer(): void {
    delete root.dataset.sidebarOpen;
    syncScrim();
  }

  if (readPref('mdview-sidebar', 'open') === 'collapsed') {
    root.dataset.sidebar = 'collapsed';
  }

  toggle.addEventListener('click', () => {
    if (narrow.matches) {
      if (root.dataset.sidebarOpen === '1') closeDrawer();
      else {
        root.dataset.sidebarOpen = '1';
        syncScrim();
      }
      return;
    }
    if (root.dataset.sidebar === 'collapsed') {
      delete root.dataset.sidebar;
      savePref('mdview-sidebar', 'open');
    } else {
      root.dataset.sidebar = 'collapsed';
      savePref('mdview-sidebar', 'collapsed');
    }
  });

  scrim?.addEventListener('click', closeDrawer);
  narrow.addEventListener('change', closeDrawer);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && root.dataset.sidebarOpen === '1') closeDrawer();
  });
  syncScrim();
}
