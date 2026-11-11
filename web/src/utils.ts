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

function legacyCopy(text: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.top = '-1000px';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    try {
      const copied = typeof document.execCommand === 'function' && document.execCommand('copy');
      if (copied) resolve();
      else reject(new Error('copy failed'));
    } catch (error) {
      reject(error);
    } finally {
      area.remove();
    }
  });
}

export function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText && window.isSecureContext) {
    try {
      return navigator.clipboard.writeText(text).catch(() => legacyCopy(text));
    } catch {
      return legacyCopy(text);
    }
  }
  return legacyCopy(text);
}

export function showToast(message: string, duration = 2400): void {
  document.getElementById('mdview-toast')?.remove();
  const toast = document.createElement('div');
  toast.id = 'mdview-toast';
  toast.className = 'toast';
  toast.setAttribute('role', 'status');
  toast.setAttribute('aria-live', 'polite');
  toast.textContent = message;
  document.body.appendChild(toast);
  window.setTimeout(() => toast.remove(), duration);
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
