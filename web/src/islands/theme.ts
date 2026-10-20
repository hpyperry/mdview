import { readPref, savePref } from '../utils';

type ThemeMode = 'system' | 'light' | 'dark';

const modes: ThemeMode[] = ['system', 'light', 'dark'];
const labels: Record<ThemeMode, string> = {
  system: '跟随系统',
  light: '浅色',
  dark: '深色',
};

function readMode(): ThemeMode {
  const value = readPref('mdview-theme', 'system');
  return value === 'light' || value === 'dark' ? value : 'system';
}

function apply(mode: ThemeMode, button: HTMLElement): void {
  const root = document.documentElement;
  root.dataset.themeMode = mode;
  if (mode === 'system') delete root.dataset.theme;
  else root.dataset.theme = mode;
  button.title = `主题：${labels[mode]}`;
  button.setAttribute('aria-label', `切换主题，当前${labels[mode]}`);
}

export function mountTheme(): void {
  const button = document.getElementById('theme-toggle');
  if (!button) return;
  let status: HTMLElement | null = null;
  let statusTimer = 0;
  const host = button.parentElement;
  if (host) {
    status = document.createElement('span');
    status.className = 'theme-status';
    status.id = 'theme-status';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    host.appendChild(status);
  }

  function announce(mode: ThemeMode): void {
    if (!status) return;
    status.textContent = `主题：${labels[mode]}`;
    status.classList.add('is-visible');
    window.clearTimeout(statusTimer);
    statusTimer = window.setTimeout(() => status.classList.remove('is-visible'), 1200);
  }

  let mode = readMode();
  apply(mode, button);
  button.addEventListener('click', () => {
    mode = modes[(modes.indexOf(mode) + 1) % modes.length];
    savePref('mdview-theme', mode);
    apply(mode, button);
    announce(mode);
  });
}
