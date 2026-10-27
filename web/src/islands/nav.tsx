import { render } from 'preact';
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'preact/hooks';
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
  partial?: boolean;
  tree: NavNode[];
}

interface NavDirPayload {
  root: string;
  dir: string;
  partial?: boolean;
  nodes: NavNode[];
}

interface NavProps {
  panel: HTMLElement;
  toggle: HTMLElement;
  rootName: string;
  currentPath: string;
  currentIsDir: boolean;
}

interface DirStatus {
  loading: boolean;
  error: string;
}

const EXPANDED_KEY = 'mdview-nav-expanded';
const HOVER_DELAY = 150;
const HOVER_PREFETCH =
  typeof window !== 'undefined' &&
  ((typeof window.matchMedia === 'function' && window.matchMedia('(hover: hover)').matches) ||
    !('ontouchstart' in window));

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
  loadedChildren,
  dirStatus,
  onToggle,
  onEnsure,
  onRetry,
  onNavigate,
}: {
  node: NavNode;
  depth: number;
  expanded: Set<string>;
  currentPath: string;
  loadedChildren: Record<string, NavNode[]>;
  dirStatus: Record<string, DirStatus>;
  onToggle: (node: NavNode) => void;
  onEnsure: (path: string) => void | Promise<void>;
  onRetry: (path: string) => void;
  onNavigate: () => void;
}) {
  const paddingLeft = `${8 + depth * 14}px`;
  const childPaddingLeft = `${8 + (depth + 1) * 14 + 22}px`;
  const isDir = node.type === 'dir';
  const isOpen = isDir && expanded.has(node.path);
  const children = node.children ?? loadedChildren[node.path];
  const status = dirStatus[node.path];
  const hoverTimer = useRef<number | null>(null);

  const clearHover = useCallback(() => {
    if (hoverTimer.current !== null) {
      window.clearTimeout(hoverTimer.current);
      hoverTimer.current = null;
    }
  }, []);

  useEffect(() => clearHover, [clearHover]);

  useEffect(() => {
    if (!isDir || !isOpen || children !== undefined) return;
    if (status?.loading || status?.error) return;
    void onEnsure(node.path);
  }, [isDir, isOpen, children, status?.loading, status?.error, node.path, onEnsure]);

  if (isDir) {
    function onEnter(): void {
      if (!HOVER_PREFETCH || children !== undefined || status?.error) return;
      clearHover();
      hoverTimer.current = window.setTimeout(() => {
        hoverTimer.current = null;
        void onEnsure(node.path);
      }, HOVER_DELAY);
    }

    return (
      <div class={`nav-dir${isOpen ? ' is-open' : ''}`}>
        <button
          class="nav-row"
          type="button"
          style={{ paddingLeft }}
          aria-expanded={isOpen}
          onClick={() => onToggle(node)}
          onPointerEnter={onEnter}
          onPointerLeave={clearHover}
        >
          <Icon name="chevron-right" class="nav-chevron" />
          <Icon name="folder" />
          <span>{node.name}</span>
        </button>
        {isOpen ? (
          children === undefined ? (
            status?.error ? (
              <div class="nav-status" style={{ paddingLeft: childPaddingLeft }}>
                <span>{status.error}</span>
                <button class="nav-retry" type="button" onClick={() => onRetry(node.path)}>
                  重试
                </button>
              </div>
            ) : (
              <div class="nav-status" style={{ paddingLeft: childPaddingLeft }}>
                加载中…
              </div>
            )
          ) : children.length ? (
            <div class="nav-children">
              {children.map((child) => (
                <TreeNode
                  key={child.path}
                  node={child}
                  depth={depth + 1}
                  expanded={expanded}
                  currentPath={currentPath}
                  loadedChildren={loadedChildren}
                  dirStatus={dirStatus}
                  onToggle={onToggle}
                  onEnsure={onEnsure}
                  onRetry={onRetry}
                  onNavigate={onNavigate}
                />
              ))}
            </div>
          ) : (
            <div class="nav-empty" style={{ paddingLeft: childPaddingLeft }}>
              空目录
            </div>
          )
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
  const [loadedChildren, setLoadedChildren] = useState<Record<string, NavNode[]>>({});
  const [dirStatus, setDirStatus] = useState<Record<string, DirStatus>>({});
  const [partial, setPartial] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const loadedRef = useRef(false);
  const loadingRef = useRef(false);
  const openRef = useRef(false);
  const expandedRef = useRef(expanded);
  const loadedChildrenRef = useRef<Record<string, NavNode[]>>({});
  const pendingRef = useRef<Map<string, Promise<void>>>(new Map());
  const closeRef = useRef<HTMLButtonElement>(null);

  function applyOpen(next: boolean): void {
    openRef.current = next;
    setOpen(next);
    document.documentElement.dataset.navOpen = next ? '1' : '0';
    toggle.setAttribute('aria-expanded', String(next));
    panel.setAttribute('aria-hidden', String(!next));
    if (next) window.requestAnimationFrame(() => closeRef.current?.focus());
    else toggle.focus();
  }

  function applyExpanded(next: Set<string>): void {
    expandedRef.current = next;
    setExpanded(next);
  }

  const storeChildren = useCallback((path: string, nodes: NavNode[]): void => {
    const next = { ...loadedChildrenRef.current, [path]: nodes };
    loadedChildrenRef.current = next;
    setLoadedChildren(next);
  }, []);

  const ensureChildren = useCallback(
    (path: string): Promise<void> => {
      if (loadedChildrenRef.current[path] !== undefined) return Promise.resolve();
      const pending = pendingRef.current.get(path);
      if (pending) return pending;
      setDirStatus((current) => ({ ...current, [path]: { loading: true, error: '' } }));
      const promise = (async () => {
        try {
          const params = new URLSearchParams({ __mdview: 'nav', dir: path });
          const response = await fetch(`/_nav?${params.toString()}`, {
            headers: { Accept: 'application/json' },
          });
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const data = (await response.json()) as NavDirPayload;
          storeChildren(path, Array.isArray(data.nodes) ? data.nodes : []);
          if (data.partial) setPartial(true);
          setDirStatus((current) => {
            const next = { ...current };
            delete next[path];
            return next;
          });
        } catch {
          setDirStatus((current) => ({
            ...current,
            [path]: { loading: false, error: '加载失败' },
          }));
        } finally {
          pendingRef.current.delete(path);
        }
      })();
      pendingRef.current.set(path, promise);
      return promise;
    },
    [storeChildren],
  );

  const retryDir = useCallback(
    (path: string): void => {
      setDirStatus((current) => {
        const next = { ...current };
        delete next[path];
        return next;
      });
      void ensureChildren(path);
    },
    [ensureChildren],
  );

  async function load(): Promise<void> {
    if (loadedRef.current || loadingRef.current) return;
    loadingRef.current = true;
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({ __mdview: 'nav' });
      if (currentPath) params.set('active', currentPath);
      const response = await fetch(`/_nav?${params.toString()}`, {
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = (await response.json()) as NavPayload;
      setPayload(data);
      setPartial(Boolean(data.partial));
      applyExpanded(readExpanded(currentPath, currentIsDir));
      loadedRef.current = true;
    } catch {
      setError('导航加载失败');
    } finally {
      loadingRef.current = false;
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
      const next = !openRef.current;
      applyOpen(next);
      if (next) void load();
    }
    toggle.addEventListener('click', onToggle);
    return () => toggle.removeEventListener('click', onToggle);
  }, []);

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
  }, [open, payload, loadedChildren]);

  function close(): void {
    applyOpen(false);
  }

  function toggleDir(node: NavNode): void {
    const next = new Set(expandedRef.current);
    if (next.has(node.path)) {
      next.delete(node.path);
    } else {
      next.add(node.path);
      if (node.children === undefined && loadedChildrenRef.current[node.path] === undefined) {
        void ensureChildren(node.path);
      }
    }
    applyExpanded(next);
    saveExpanded(next);
  }

  function retry(): void {
    loadedRef.current = false;
    setPayload(null);
    setPartial(false);
    loadedChildrenRef.current = {};
    setLoadedChildren({});
    setDirStatus({});
    pendingRef.current.clear();
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
        <>
          <div class="nav-tree" role="tree">
            {payload.tree.map((node) => (
              <TreeNode
                key={node.path}
                node={node}
                depth={0}
                expanded={expanded}
                currentPath={currentPath}
                loadedChildren={loadedChildren}
                dirStatus={dirStatus}
                onToggle={toggleDir}
                onEnsure={ensureChildren}
                onRetry={retryDir}
                onNavigate={close}
              />
            ))}
          </div>
          {partial ? <div class="nav-note">部分目录无法读取，内容未显示</div> : null}
        </>
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
