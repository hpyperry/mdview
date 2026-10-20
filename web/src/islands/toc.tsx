import { createPortal } from 'preact/compat';
import { render } from 'preact';
import { useEffect, useLayoutEffect, useRef, useState } from 'preact/hooks';
import { Icon } from '../icons';
import { prefersReducedMotion } from '../utils';

interface Heading {
  id: string;
  text: string;
  level: 2 | 3;
}

interface TocProps {
  headings: Heading[];
  inlineNav: HTMLElement | null;
  rail: HTMLElement;
}

function collectHeadings(): Heading[] {
  const article = document.querySelector('.markdown-body');
  if (!article) return [];
  const headings = Array.from(article.querySelectorAll<HTMLElement>('h2, h3'));
  return headings.map((heading, index) => {
    if (!heading.id) {
      const base = `toc-${index + 1}`;
      let id = base;
      let suffix = 1;
      while (document.getElementById(id)) {
        suffix += 1;
        id = `${base}-${suffix}`;
      }
      heading.id = id;
    }
    return {
      id: heading.id,
      text: (heading.textContent || '').trim(),
      level: heading.tagName === 'H3' ? 3 : 2,
    };
  });
}

function scrollToHeading(id: string): void {
  const target = document.getElementById(id);
  if (!target) return;
  target.scrollIntoView({
    behavior: prefersReducedMotion() ? 'auto' : 'smooth',
    block: 'start',
  });
}

function TocLinks({
  headings,
  active,
  onSelect,
}: {
  headings: Heading[];
  active: string;
  onSelect: (id: string) => void;
}) {
  return (
    <>
      {headings.map((heading) => (
        <a
          key={heading.id}
          class={`toc-link${heading.level === 3 ? ' toc-h3' : ''}${active === heading.id ? ' active' : ''}`}
          href={`#${heading.id}`}
          data-target={heading.id}
          onClick={(event) => {
            event.preventDefault();
            onSelect(heading.id);
          }}
        >
          {heading.text}
        </a>
      ))}
    </>
  );
}

function Toc({ headings, inlineNav, rail }: TocProps) {
  const [active, setActive] = useState(headings[0]?.id || '');
  const [pinned, setPinned] = useState(false);
  const [hovered, setHovered] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const expanded = pinned || hovered;

  function close(): void {
    setPinned(false);
    setHovered(false);
  }

  function select(id: string): void {
    setActive(id);
    close();
    scrollToHeading(id);
  }

  useEffect(() => {
    let scheduled = false;
    function spy(): void {
      const bar = document.querySelector('.topbar');
      const offset = (bar?.getBoundingClientRect().height || 56) + 34;
      let next = headings[0]?.id || '';
      for (const heading of headings) {
        const element = document.getElementById(heading.id);
        if (!element) continue;
        if (element.getBoundingClientRect().top <= offset) next = heading.id;
        else break;
      }
      setActive((current) => (current === next ? current : next));
    }
    function schedule(): void {
      if (scheduled) return;
      scheduled = true;
      window.requestAnimationFrame(() => {
        scheduled = false;
        spy();
      });
    }
    function onVisibility(): void {
      if (!document.hidden) spy();
    }
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', spy);
    document.addEventListener('visibilitychange', onVisibility);
    spy();
    return () => {
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', spy);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [headings]);

  useLayoutEffect(() => {
    let closeTimer = 0;
    function clearClose(): void {
      if (closeTimer) {
        window.clearTimeout(closeTimer);
        closeTimer = 0;
      }
    }
    function show(): void {
      clearClose();
      setHovered(true);
    }
    function scheduleClose(): void {
      clearClose();
      closeTimer = window.setTimeout(() => setHovered(false), 160);
    }
    function onFocusOut(event: FocusEvent): void {
      const next = event.relatedTarget as Node | null;
      if (next && rail.contains(next)) return;
      scheduleClose();
    }
    rail.addEventListener('pointerenter', show);
    rail.addEventListener('pointerleave', scheduleClose);
    rail.addEventListener('focusin', show);
    rail.addEventListener('focusout', onFocusOut);
    return () => {
      clearClose();
      rail.removeEventListener('pointerenter', show);
      rail.removeEventListener('pointerleave', scheduleClose);
      rail.removeEventListener('focusin', show);
      rail.removeEventListener('focusout', onFocusOut);
    };
  }, [rail]);

  useLayoutEffect(() => {
    if (!expanded) return;
    function onKey(event: KeyboardEvent): void {
      if (event.key === 'Escape') close();
    }
    function onPointer(event: MouseEvent): void {
      const target = event.target as Element | null;
      if (!target?.closest('.toc-rail')) close();
    }
    document.addEventListener('keydown', onKey);
    document.addEventListener('click', onPointer);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('click', onPointer);
    };
  }, [expanded]);

  useEffect(() => {
    if (!expanded) return;
    const panel = panelRef.current;
    if (!panel) return;
    const link = panel.querySelector<HTMLElement>(`.toc-link[data-target="${CSS.escape(active)}"]`);
    if (!link) return;
    const panelRect = panel.getBoundingClientRect();
    const linkRect = link.getBoundingClientRect();
    if (linkRect.top < panelRect.top + 8) panel.scrollTop += linkRect.top - panelRect.top - 8;
    else if (linkRect.bottom > panelRect.bottom - 8) panel.scrollTop += linkRect.bottom - panelRect.bottom + 8;
  }, [active, expanded]);

  useEffect(() => {
    const narrow = window.matchMedia('(max-width: 1359px)');
    function onNarrow(): void {
      if (narrow.matches) {
        setPinned(false);
        setHovered(false);
      }
    }
    narrow.addEventListener('change', onNarrow);
    return () => narrow.removeEventListener('change', onNarrow);
  }, []);

  return (
    <>
      <button
        class="toc-rail-btn"
        type="button"
        aria-label="本页目录"
        aria-expanded={expanded}
        aria-pressed={pinned}
        title={pinned ? '收起本页目录' : '固定本页目录'}
        onClick={() => {
          const next = !pinned;
          setPinned(next);
          if (!next) setHovered(false);
        }}
      >
        <Icon name="list" />
      </button>
      <div class="toc-ticks">
        {headings.map((heading) => (
          <button
            key={heading.id}
            class={`toc-tick${heading.level === 3 ? ' is-h3' : ''}${active === heading.id ? ' is-active' : ''}`}
            type="button"
            data-target={heading.id}
            aria-label={heading.text}
            title={heading.text}
            onClick={() => select(heading.id)}
          />
        ))}
      </div>
      {expanded && (
        <div class="toc-pop" ref={panelRef}>
          <div class="toc-pop-head">
            <span>本页目录</span>
            <button class="toc-close" type="button" aria-label="收起本页目录" onClick={close}>
              <Icon name="chevrons-right" />
            </button>
          </div>
          <nav class="toc-pop-list" aria-label="本页目录">
            <TocLinks headings={headings} active={active} onSelect={select} />
          </nav>
        </div>
      )}
      {inlineNav
        ? createPortal(<TocLinks headings={headings} active={active} onSelect={select} />, inlineNav)
        : null}
    </>
  );
}

export function mountToc(): void {
  const rail = document.getElementById('toc-rail');
  const slot = document.getElementById('toc-slot');
  const inlineNav = slot?.querySelector<HTMLElement>('.toc-list') || null;
  const headings = collectHeadings();
  if (!headings.length) {
    if (rail) rail.hidden = true;
    if (slot) slot.hidden = true;
    document.getElementById('shell')?.classList.add('no-toc');
    return;
  }
  if (rail) {
    rail.hidden = false;
    render(<Toc headings={headings} inlineNav={inlineNav} rail={rail} />, rail);
  }
  if (slot) {
    slot.hidden = false;
    const summary = slot.querySelector('summary');
    if (summary) summary.textContent = `本页目录（${headings.length}）`;
  }
}
