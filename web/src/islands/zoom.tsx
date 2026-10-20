import { render } from 'preact';
import { useEffect, useRef, useState } from 'preact/hooks';
import { Icon } from '../icons';

interface ZoomItem {
  src: string;
  alt: string;
  lastFocus: HTMLElement | null;
}

function Zoom() {
  const [item, setItem] = useState<ZoomItem | null>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const itemRef = useRef<ZoomItem | null>(null);
  itemRef.current = item;

  useEffect(() => {
    function onClick(event: MouseEvent): void {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const target = event.target as Element | null;
      if (!target) return;
      const anchor = target.closest<HTMLAnchorElement>('a.zoom');
      if (anchor) {
        event.preventDefault();
        const image = anchor.querySelector('img');
        setItem({
          src: anchor.getAttribute('href') || '',
          alt: image?.alt || '',
          lastFocus: anchor,
        });
        return;
      }
      const image = target.closest<HTMLImageElement>('.markdown-body img');
      if (image && !image.closest('a')) {
        event.preventDefault();
        setItem({
          src: image.currentSrc || image.src,
          alt: image.alt || '',
          lastFocus: image,
        });
      }
    }
    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, []);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (item) {
      if (!dialog.open) dialog.showModal();
      dialog.focus();
    } else if (dialog.open) {
      dialog.close();
    }
  }, [item]);

  function close(): void {
    dialogRef.current?.close();
  }

  return (
    <dialog
      class="zoomdlg"
      ref={dialogRef}
      tabIndex={-1}
      onClose={() => {
        const last = itemRef.current?.lastFocus;
        setItem(null);
        last?.focus();
      }}
      onClick={(event) => {
        if (event.target === dialogRef.current) close();
      }}
    >
      <button class="zoom-close" type="button" aria-label="关闭" onClick={close}>
        <Icon name="x" />
      </button>
      {item ? (
        <>
          <img src={item.src} alt={item.alt} />
          <p class="zoom-caption">{item.alt}</p>
        </>
      ) : null}
    </dialog>
  );
}

export function mountZoom(): void {
  if (!document.querySelector('.markdown-body')) return;
  let host = document.getElementById('zoom-root');
  if (!host) {
    host = document.createElement('div');
    host.id = 'zoom-root';
    document.body.appendChild(host);
  }
  render(<Zoom />, host);
}
