/**
 * Highlight very large code blocks in a dedicated worker so the main thread
 * stays responsive. Each request times out; a stuck worker is discarded and a
 * fresh one is created for the next block.
 */
const WORKER_TIMEOUT = 3000;

interface Pending {
  resolve: (html: string | null) => void;
  timer: number;
}

let worker: Worker | null = null;
let sequence = 0;
const pending = new Map<number, Pending>();

function workerUrl(): string | null {
  const script = document.querySelector<HTMLScriptElement>('script[src*="/_assets/app.js"]');
  if (!script) return null;
  return script.src.replace('/_assets/app.js', '/_assets/hlworker.js');
}

function recycle(): void {
  worker?.terminate();
  worker = null;
  const entries = Array.from(pending.values());
  pending.clear();
  for (const entry of entries) {
    window.clearTimeout(entry.timer);
    entry.resolve(null);
  }
}

function ensureWorker(): Worker | null {
  if (worker) return worker;
  const url = workerUrl();
  if (!url || typeof Worker === 'undefined') return null;
  try {
    worker = new Worker(url);
  } catch {
    return null;
  }
  worker.onmessage = (event: MessageEvent) => {
    const data = event.data || {};
    const entry = pending.get(data.id);
    if (!entry) return;
    pending.delete(data.id);
    window.clearTimeout(entry.timer);
    entry.resolve(typeof data.html === 'string' ? data.html : null);
  };
  worker.onerror = () => recycle();
  return worker;
}

export function highlightInWorker(
  code: string,
  language: string,
  timeout = WORKER_TIMEOUT,
): Promise<string | null> {
  const active = ensureWorker();
  if (!active) return Promise.resolve(null);
  const id = ++sequence;
  return new Promise((resolve) => {
    const timer = window.setTimeout(() => {
      pending.delete(id);
      // The worker is busy on unresponsive input; replace it for later blocks.
      worker?.terminate();
      worker = null;
      resolve(null);
    }, timeout);
    pending.set(id, { resolve, timer });
    active.postMessage({ id, code, language });
  });
}
