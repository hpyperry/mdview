import { render } from 'preact';
import { useState } from 'preact/hooks';
import { Icon } from '../icons';
import { copyText, hasExplicitLanguage, languageOf } from '../utils';

const MAX_HIGHLIGHT_CHARS = 256 * 1024;

function CodeBar({ code, lang, skipped }: { code: HTMLElement; lang: string; skipped: boolean }) {
  const [state, setState] = useState<'idle' | 'done' | 'fail'>('idle');

  async function copy(): Promise<void> {
    try {
      await copyText(code.innerText);
      setState('done');
      window.setTimeout(() => setState('idle'), 1200);
    } catch {
      setState('fail');
    }
  }

  return (
    <>
      <span class="lang">
        <Icon name="code" />
        {lang}
        {skipped ? ' · 未高亮' : ''}
      </span>
      <button
        class="copy-btn"
        type="button"
        aria-label="复制代码"
        onClick={copy}
      >
        <Icon name={state === 'done' ? 'check' : state === 'fail' ? 'x' : 'copy'} />
        {state === 'done' ? '已复制' : state === 'fail' ? '复制失败' : '复制'}
      </button>
    </>
  );
}

export function mountMarkdownCode(): void {
  const article = document.querySelector('.markdown-body');
  if (!article) return;
  const blocks = Array.from(article.querySelectorAll<HTMLElement>('pre > code'));
  for (const code of blocks) {
    const pre = code.parentElement;
    if (!pre || pre.closest('.code-block')) continue;
    const wrapper = document.createElement('div');
    wrapper.className = 'code-block';
    const bar = document.createElement('div');
    bar.className = 'code-bar';
    pre.parentNode?.insertBefore(wrapper, pre);
    wrapper.appendChild(bar);
    wrapper.appendChild(pre);

    const lang = languageOf(code);
    const skipped = Boolean(code.textContent && code.textContent.length > MAX_HIGHLIGHT_CHARS);
    if (skipped) code.dataset.highlightSkipped = '1';
    render(<CodeBar code={code} lang={lang} skipped={skipped} />, bar);

    if (skipped || !window.hljs || !hasExplicitLanguage(code)) continue;
    const highlight = () => {
      try {
        window.hljs?.highlightElement(code);
      } catch {
        // keep plain text
      }
    };
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        observer.disconnect();
        highlight();
      }, { rootMargin: '1200px 0px' });
      observer.observe(wrapper);
    } else {
      highlight();
    }
  }
}
