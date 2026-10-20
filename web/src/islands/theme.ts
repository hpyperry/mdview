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
  apply(readMode(), button);
  button.addEventListener('click', () => {
    const current = readMode();
    const next = modes[(modes.indexOf(current) + 1) % modes.length];
    savePref('mdview-theme', next);
    apply(next, button);
  });
}
