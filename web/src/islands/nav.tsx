import { render } from 'preact';
import { useEffect, useLayoutEffect, useRef, useState } from 'preact/hooks';
import { Icon } from '../icons';

interface NavNode {
  name: string;
  path: string;
  type: 'dir' | 'file';
  href?: string;
  file_kind?: 'doc' | 'text' | 'image' | 'pdf' | 'binary';
  children?: NavNode[];
}

interface NavPayload {
  root: string;
  tree: NavNode[];
}

interface NavProps {
  panel: HTMLElement;
  toggle: HTMLElement;
  rootName: string;
  currentPath: string;
  currentIsDir: boolean;
}

const EXPANDED_KEY = 'mdview-nav-expanded';

type IdleWindow = Window & {
  requestIdleCallback?: (callback: () => void, options?: { timeout?: number }) => number;
  cancelIdleCallback?: (id: number) => void;
};

function readExpanded(currentPath: string, currentIsDir: boolean): Set<string> {
  const expanded = new Set<string>();
  try {
    const stored = JSON.parse(localStorage.getItem(EXPANDED_KEY) || '[]');
    if (Array.isArray(stored)) {
      stored.forEach((value) => {
        if (typeof value === 'string') expanded.add(value);
      });
    }
  } catch {
    // ignore malformed local state
  }
  const parts = currentPath.split('/').filter(Boolean);
  const dirCount = currentIsDir ? parts.length : parts.length - 1;
  for (let i = 1; i <= dirCount; i += 1) expanded.add(parts.slice(0, i).join('/'));
  return expanded;
}

function saveExpanded(expanded: Set<string>): void {
  try {
    localStorage.setItem(EXPANDED_KEY, JSON.stringify(Array.from(expanded)));
  } catch {
    // private mode
  }
}

function FileIcon({ kind }: { kind?: NavNode['file_kind'] }) {
  if (kind === 'doc' || kind === 'text') return <Icon name="file-text" />;
  if (kind === 'image') return <Icon name="image" />;
  return <Icon name="file" />;
}

function TreeNode({
  node,
  depth,
  expanded,
  currentPath,
  onToggle,
  onNavigate,
}: {
  node: NavNode;
  depth: number;
  expanded: Set<string>;
  currentPath: string;
  onToggle: (path: string) => void;
  onNavigate: () => void;
}) {
  const paddingLeft = `${8 + depth * 14}px`;
  if (node.type === 'dir') {
    const isOpen = expanded.has(node.path);
    return (
      <div class={`nav-dir${isOpen ? ' is-open' : ''}`}>
        <button
          class="nav-row"
          type="button"
          style={{ paddingLeft }}
          aria-expanded={isOpen}
          onClick={() => onToggle(node.path)}
        >
          <Icon name="chevron-right" class="nav-chevron" />
          <Icon name="folder" />
          <span>{node.name}</span>
        </button>
        {isOpen && node.children?.length ? (
          <div class="nav-children">
            {node.children.map((child) => (
              <TreeNode
                key={child.path}
                node={child}
                depth={depth + 1}
                expanded={expanded}
                currentPath={currentPath}
                onToggle={onToggle}
                onNavigate={onNavigate}
              />
            ))}
          </div>
        ) : null}
      </div>
    );
  }
  const active = node.path === currentPath;
  return (
    <a
      class={`nav-row nav-file${active ? ' is-active' : ''}`}
      href={node.href}
      style={{ paddingLeft }}
      aria-current={active ? 'page' : undefined}
      onClick={onNavigate}
    >
      <FileIcon kind={node.file_kind} />
      <span>{node.name}</span>
    </a>
  );
}

function NavApp({ panel, toggle, rootName, currentPath, currentIsDir }: NavProps) {
  const [open, setOpen] = useState(false);
  const [payload, setPayload] = useState<NavPayload | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(() =>
    readExpanded(currentPath, currentIsDir),
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const loadedRef = useRef(false);
  const closeRef = useRef<HTMLButtonElement>(null);

  function applyOpen(next: boolean): void {
    setOpen(next);
    document.documentElement.dataset.navOpen = next ? '1' : '0';
    toggle.setAttribute('aria-expanded', String(next));
    panel.setAttribute('aria-hidden', String(!next));
    if (next) window.requestAnimationFrame(() => closeRef.current?.focus());
    else toggle.focus();
  }

  async function load(): Promise<void> {
    if (loadedRef.current || loading) return;
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/_nav', { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = (await response.json()) as NavPayload;
      setPayload(data);
      setExpanded(readExpanded(currentPath, currentIsDir));
      loadedRef.current = true;
    } catch {
      setError('导航加载失败');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // 整页导航会重建岛，所以每次页面加载都空闲预取一次。
    let cancelled = false;
    const idle = window as IdleWindow;
    const run = (): void => {
      if (!cancelled) void load();
    };
    if (idle.requestIdleCallback) {
      const id = idle.requestIdleCallback(run, { timeout: 1500 });
      return () => {
        cancelled = true;
        idle.cancelIdleCallback?.(id);
      };
    }
    const id = window.setTimeout(run, 200);
    return () => {
      cancelled = true;
      window.clearTimeout(id);
    };
  }, []);

  useEffect(() => {
    function onToggle(event: Event): void {
      event.preventDefault();
      const next = !open;
      applyOpen(next);
      if (next) void load();
    }
    toggle.addEventListener('click', onToggle);
    return () => toggle.removeEventListener('click', onToggle);
  }, [open, loading]);

  useLayoutEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent): void {
      if (event.key === 'Escape') applyOpen(false);
    }
    function onPointer(event: MouseEvent): void {
      const target = event.target as Element | null;
      if (!target) return;
      if (!target.closest('#nav-panel') && !target.closest('#nav-toggle')) applyOpen(false);
    }
    const scrim = document.getElementById('nav-scrim');
    scrim?.addEventListener('click', close);
    document.addEventListener('keydown', onKey);
    document.addEventListener('click', onPointer);
    return () => {
      scrim?.removeEventListener('click', close);
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('click', onPointer);
    };
  }, [open]);

  useEffect(() => {
    if (!open || !payload) return;
    window.requestAnimationFrame(() => {
      const active = panel.querySelector<HTMLElement>('.nav-file.is-active');
      if (!active) return;
      const panelRect = panel.getBoundingClientRect();
      const activeRect = active.getBoundingClientRect();
      if (activeRect.top < panelRect.top + 42) {
        panel.scrollTop += activeRect.top - panelRect.top - 42;
      } else if (activeRect.bottom > panelRect.bottom - 8) {
        panel.scrollTop += activeRect.bottom - panelRect.bottom + 8;
      }
    });
  }, [open, payload]);

  function close(): void {
    applyOpen(false);
  }

  function toggleDir(path: string): void {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      saveExpanded(next);
      return next;
    });
  }

  function retry(): void {
    loadedRef.current = false;
    setPayload(null);
    void load();
  }

  return (
    <>
      <div class="nav-head">
        <span class="nav-root">{payload?.root || rootName}</span>
        <button class="nav-close" id="nav-close" ref={closeRef} type="button" aria-label="关闭导航" onClick={close}>
          <Icon name="x" />
        </button>
      </div>
      {loading ? <div class="nav-status">加载中…</div> : null}
      {error ? (
        <div class="nav-status">
          <span>{error}</span>
          <button class="nav-retry" type="button" onClick={retry}>重试</button>
        </div>
      ) : null}
      {payload && open ? (
        <div class="nav-tree" role="tree">
          {payload.tree.map((node) => (
            <TreeNode
              key={node.path}
              node={node}
              depth={0}
              expanded={expanded}
              currentPath={currentPath}
              onToggle={toggleDir}
              onNavigate={close}
            />
          ))}
        </div>
      ) : null}
    </>
  );
}

export function mountNav(): void {
  const panel = document.getElementById('nav-panel');
  const toggle = document.getElementById('nav-toggle');
  if (!panel || !toggle) return;
  render(
    <NavApp
      panel={panel}
      toggle={toggle}
      rootName={panel.dataset.root || '导航'}
      currentPath={document.body.dataset.currentPath || ''}
      currentIsDir={document.body.dataset.currentDir === '1'}
    />,
    panel,
  );
}
