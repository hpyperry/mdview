const MAX_SIDE = 16000;
const MAX_AREA = 120_000_000;
const MAX_SCALE = 2;

function collectCss(): string {
  const parts: string[] = [];
  for (const sheet of Array.from(document.styleSheets)) {
    try {
      for (const rule of Array.from(sheet.cssRules)) parts.push(rule.cssText);
    } catch {
      // Cross-origin stylesheets are not used by mdview.
    }
  }
  return parts.join('\n');
}

function lightPalette(): string {
  for (const sheet of Array.from(document.styleSheets)) {
    let rules: CSSRuleList;
    try {
      rules = sheet.cssRules;
    } catch {
      continue;
    }
    for (const rule of Array.from(rules)) {
      if (!(rule instanceof CSSStyleRule) || rule.selectorText !== ':root') continue;
      const vars: string[] = [];
      for (let index = 0; index < rule.style.length; index += 1) {
        const name = rule.style.item(index);
        if (name.startsWith('--')) vars.push(`${name}:${rule.style.getPropertyValue(name)}`);
      }
      if (vars.length > 0) return `${vars.join(';')};`;
    }
  }
  return '';
}

function inlineImages(source: HTMLElement, clone: HTMLElement): void {
  const originals = Array.from(source.querySelectorAll('img'));
  const copies = Array.from(clone.querySelectorAll('img'));
  originals.forEach((img, index) => {
    const copy = copies[index];
    if (!copy || !img.complete || !img.naturalWidth || !img.naturalHeight) return;
    try {
      const canvas = document.createElement('canvas');
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const context = canvas.getContext('2d');
      if (!context) return;
      context.drawImage(img, 0, 0);
      copy.removeAttribute('srcset');
      copy.src = canvas.toDataURL('image/png');
    } catch {
      // Keep the original source; the renderer will simply skip it.
    }
  });
}

function loadImage(svg: string): Promise<HTMLImageElement> {
  const image = new Image();
  return new Promise((resolve, reject) => {
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('无法渲染导出图像'));
    image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  });
}

function safeName(name: string): string {
  const cleaned = name.replace(/[\\/:*?"<>|\u0000-\u001f]/g, '_').trim();
  return cleaned || 'document';
}

function download(blob: Blob, name: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function renderPng(article: HTMLElement, name: string): Promise<void> {
  await document.fonts.ready;

  const rect = article.getBoundingClientRect();
  const width = Math.ceil(rect.width);
  const height = Math.ceil(article.scrollHeight);
  if (!width || !height) throw new Error('正文为空');

  const limit = Math.min(
    MAX_SCALE,
    MAX_SIDE / width,
    MAX_SIDE / height,
    Math.sqrt(MAX_AREA / (width * height)),
  );
  const scale = Math.floor(limit * 2) / 2;
  if (!Number.isFinite(scale) || scale < 1) {
    throw new Error('文档过长');
  }

  const clone = article.cloneNode(true) as HTMLElement;
  clone.querySelectorAll('.code-bar, .copy-btn, .zoomdlg, .totop').forEach((node) => node.remove());
  inlineImages(article, clone);
  clone.style.maxWidth = 'none';
  clone.style.width = `${width}px`;
  clone.style.margin = '0';
  clone.style.background = '#ffffff';
  clone.style.color = '#1f2328';

  const style = document.createElement('style');
  style.textContent = collectCss();

  const wrapper = document.createElement('div');
  wrapper.setAttribute('xmlns', 'http://www.w3.org/1999/xhtml');
  const bodyFont = getComputedStyle(document.body).font;
  wrapper.setAttribute(
    'style',
    `width:${width}px;background:#ffffff;color:#1f2328;font:${bodyFont};${lightPalette()}`,
  );
  wrapper.appendChild(style);
  wrapper.appendChild(clone);

  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">` +
    `<foreignObject width="100%" height="100%">${new XMLSerializer().serializeToString(wrapper)}` +
    `</foreignObject></svg>`;
  const image = await loadImage(svg);

  const canvas = document.createElement('canvas');
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  const context = canvas.getContext('2d');
  if (!context) throw new Error('无法创建画布');
  context.fillStyle = '#ffffff';
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.scale(scale, scale);
  context.drawImage(image, 0, 0);

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'));
  if (!blob) throw new Error('无法生成图片');
  download(blob, `${safeName(name)}.png`);
}

export function mountExport(): void {
  const pngButton = document.getElementById('export-png') as HTMLButtonElement | null;
  const pdfButton = document.getElementById('export-pdf') as HTMLButtonElement | null;
  if (!pngButton && !pdfButton) return;

  const status = document.createElement('span');
  status.className = 'export-status';
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  (pdfButton ?? pngButton)?.parentElement?.appendChild(status);

  const name = pngButton?.dataset.exportName || document.title.replace(/ · mdview$/, '');
  let timer = 0;

  const say = (message: string): void => {
    status.textContent = message;
    window.clearTimeout(timer);
    if (message) timer = window.setTimeout(() => { status.textContent = ''; }, 4000);
  };

  pdfButton?.addEventListener('click', () => {
    say('');
    window.print();
  });

  pngButton?.addEventListener('click', async () => {
    const article = document.querySelector<HTMLElement>('.markdown-body');
    if (!article || pngButton.dataset.busy === '1') return;
    pngButton.dataset.busy = '1';
    pngButton.disabled = true;
    say('正在生成图片…');
    try {
      await renderPng(article, name);
      say('图片已生成');
    } catch (error) {
      console.error('[mdview] export png failed', error);
      say(error instanceof Error && error.message === '文档过长'
        ? '文档太长，请改用导出 PDF'
        : '导出失败，请重试');
    } finally {
      delete pngButton.dataset.busy;
      pngButton.disabled = false;
    }
  });
}
