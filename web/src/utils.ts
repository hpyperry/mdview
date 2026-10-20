export function readPref(key: string, fallback: string): string {
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
}

export function savePref(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // private mode
  }
}

export function copyText(text: string): Promise<void> {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text);
  }
  return new Promise((resolve, reject) => {
    const area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    try {
      document.execCommand('copy') ? resolve() : reject(new Error('copy failed'));
    } catch (error) {
      reject(error);
    }
    document.body.removeChild(area);
  });
}

export function hasExplicitLanguage(code: HTMLElement): boolean {
  return /(?:^|\s)language-[\w-]+/.test(code.className || '');
}

export function languageOf(code: HTMLElement): string {
  const match = (code.className || '').match(/(?:^|\s)language-([\w-]+)/);
  return match ? match[1] : '代码';
}

export function isNarrow(): boolean {
  return window.matchMedia('(max-width: 900px)').matches;
}

export function prefersReducedMotion(): boolean {
  return Boolean(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
}
