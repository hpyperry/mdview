/**
 * Cross-page return target for directory navigation, kept in sessionStorage so
 * the breadcrumb URL stays clean. The directory page consumes it on load:
 * `file` scrolls to that row, `y` restores the previous scroll offset.
 */
export interface ReturnTarget {
  dir: string;
  at: number;
  y?: number;
  file?: string;
}

const STORAGE_KEY = 'mdview:dir-return';
const TTL = 30_000;

export function saveReturnTarget(target: Omit<ReturnTarget, 'at'>): void {
  try {
    sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ ...target, at: Date.now() }),
    );
  } catch {
    /* storage may be unavailable */
  }
}

export function takeReturnTarget(): ReturnTarget | null {
  let raw: string | null = null;
  try {
    raw = sessionStorage.getItem(STORAGE_KEY);
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    return null;
  }
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Record<string, unknown>;
    if (typeof value.dir !== 'string' || typeof value.at !== 'number') return null;
    if (value.y !== undefined && typeof value.y !== 'number') return null;
    if (value.file !== undefined && typeof value.file !== 'string') return null;
    return {
      dir: value.dir,
      at: value.at,
      y: value.y as number | undefined,
      file: value.file as string | undefined,
    };
  } catch {
    return null;
  }
}

export function isFreshTarget(target: ReturnTarget): boolean {
  return Date.now() - target.at <= TTL;
}
