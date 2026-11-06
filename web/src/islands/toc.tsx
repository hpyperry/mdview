import { createPortal } from 'preact/compat';
import { render } from 'preact';
import { useEffect, useLayoutEffect, useRef, useState } from 'preact/hooks';
import { Icon } from '../icons';

type HeadingLevel = 1 | 2 | 3 | 4 | 5 | 6;

interface Heading {
  id: string;
  text: string;
  level: HeadingLevel;
}

interface TocProps {
  headings: Heading[];
  inlineNav: HTMLElement | null;
  rail: HTMLElement;
}

interface Tip {
  text: string;
  top: number;
}

function collectHeadings(): Heading[] {
  const article = document.querySelector('.markdown-body');
  if (!article) return [];
  const headings = Array.from(article.querySelectorAll<HTMLElement>('h1, h2, h3, h4, h5, h6'));
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
      level: Number(heading.tagName.slice(1)) as HeadingLevel,
    };
  });
}

/// TOC jumps are navigation, not decoration. Some embedded/older Chromium
/// builds stall or ignore smooth scrolling, so always jump immediately.
function scrollWindowTo(top: number): void {
  window.scrollTo({ top: Math.max(0, top), behavior: 'auto' });
}

function headingOffset(): number {
  const bar = document.querySelector<HTMLElement>('.topbar');
  return (bar?.getBoundingClientRect().height || 56) + 32;
}

function scrollToHeading(id: string): void {
  const target = document.getElementById(id);
  if (!target) return;
  const top = window.scrollY + target.getBoundingClientRect().top - headingOffset();
  scrollWindowTo(top);
}

function scrollToTop(): void {
  scrollWindowTo(0);
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
          class={`toc-link toc-h${heading.level}${active === heading.id ? ' active' : ''}`}
          href={`#${heading.id}`}
          data-target={heading.id}
          title={heading.text}
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
  const [tip, setTip] = useState<Tip | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const ticksRef = useRef<HTMLDivElement>(null);
  const islandListRef = useRef<HTMLDivElement>(null);

  function close(): void {
    setPinned(false);
    setTip(null);
  }

  function select(id: string): void {
    setActive(id);
    close();
    scrollToHeading(id);
  }

  function showTip(heading: Heading, event: Event): void {
    const target = event.currentTarget as HTMLElement | null;
    if (!target) return;
    const railRect = rail.getBoundingClientRect();
    const rect = target.getBoundingClientRect();
    setTip({
      text: heading.text,
      top: rect.top - railRect.top + rect.height / 2,
    });
  }

  function hideTip(): void {
    setTip(null);
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
    if (!pinned) return;
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
  }, [pinned]);

  useEffect(() => {
    const container = ticksRef.current;
    if (!container) return;
    const tick = container.querySelector<HTMLElement>(
      `.toc-tick[data-target="${CSS.escape(active)}"]`,
    );
    if (!tick) return;
    const box = container.getBoundingClientRect();
    const rect = tick.getBoundingClientRect();
    if (rect.top < box.top) container.scrollTop += rect.top - box.top;
    else if (rect.bottom > box.bottom) container.scrollTop += rect.bottom - box.bottom;
  }, [active]);

  useEffect(() => {
    if (!pinned) return;
    const panel = panelRef.current;
    if (!panel) return;
    const link = panel.querySelector<HTMLElement>(`.toc-link[data-target="${CSS.escape(active)}"]`);
    if (!link) return;
    const panelRect = panel.getBoundingClientRect();
    const linkRect = link.getBoundingClientRect();
    if (linkRect.top < panelRect.top + 8) panel.scrollTop += linkRect.top - panelRect.top - 8;
    else if (linkRect.bottom > panelRect.bottom - 8) panel.scrollTop += linkRect.bottom - panelRect.bottom + 8;
  }, [active, pinned]);

  useEffect(() => {
    const container = islandListRef.current;
    if (!container) return;
    const link = container.querySelector<HTMLElement>(
      `.toc-link[data-target="${CSS.escape(active)}"]`,
    );
    if (!link) return;
    const box = container.getBoundingClientRect();
    const rect = link.getBoundingClientRect();
    if (rect.top < box.top) container.scrollTop += rect.top - box.top;
    else if (rect.bottom > box.bottom) container.scrollTop += rect.bottom - box.bottom;
  }, [active]);

  useEffect(() => {
    const narrow = window.matchMedia('(max-width: 1359px)');
    function onNarrow(): void {
      if (narrow.matches) close();
    }
    narrow.addEventListener('change', onNarrow);
    return () => narrow.removeEventListener('change', onNarrow);
  }, []);

  return (
    <>
      <div class="toc-island" id="toc-island" aria-label="本页目录">
        <div class="toc-island-head">
          <span>本页目录</span>
          <span class="toc-island-count">{headings.length}</span>
        </div>
        <div class="toc-island-list" ref={islandListRef}>
          <TocLinks headings={headings} active={active} onSelect={select} />
        </div>
        <button class="toc-top" type="button" onClick={scrollToTop}>
          <span aria-hidden="true">↑</span>
          <span>回到顶部</span>
        </button>
      </div>
      <button
        class="toc-rail-btn"
        type="button"
        aria-label="本页目录"
        aria-expanded={pinned}
        aria-pressed={pinned}
        title={pinned ? '收起本页目录' : '展开本页目录'}
        onClick={() => setPinned((current) => !current)}
      >
        <Icon name="toc" />
      </button>
      <div class="toc-ticks" ref={ticksRef}>
        {headings.map((heading) => (
          <button
            key={heading.id}
            class={`toc-tick is-h${heading.level}${active === heading.id ? ' is-active' : ''}`}
            type="button"
            data-target={heading.id}
            aria-label={heading.text}
            title={heading.text}
            onPointerEnter={(event) => showTip(heading, event)}
            onPointerLeave={hideTip}
            onFocus={(event) => showTip(heading, event)}
            onBlur={hideTip}
            onClick={() => select(heading.id)}
          />
        ))}
      </div>
      {tip && (
        <div class="toc-tip" role="tooltip" style={{ top: `${tip.top}px` }}>
          {tip.text}
        </div>
      )}
      {pinned && (
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
    delete document.body.dataset.hasToc;
    return;
  }
  document.body.dataset.hasToc = '1';
  document.getElementById('shell')?.classList.remove('no-toc');
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
