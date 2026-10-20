import type { JSX } from 'preact';

type IconName =
  | 'list'
  | 'chevrons-right'
  | 'chevron-right'
  | 'copy'
  | 'check'
  | 'x'
  | 'code'
  | 'folder'
  | 'file'
  | 'file-text'
  | 'image'
  | 'rotate-cw';

const paths: Record<IconName, JSX.Element> = {
  list: (
    <>
      <path d="M8 6h13M8 12h13M8 18h13" />
      <path d="M3 6h.01M3 12h.01M3 18h.01" />
    </>
  ),
  'chevrons-right': (
    <>
      <path d="m6 17 5-5-5-5" />
      <path d="m13 17 5-5-5-5" />
    </>
  ),
  'chevron-right': <path d="m9 18 6-6-6-6" />,
  copy: (
    <>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </>
  ),
  check: <path d="M20 6 9 17l-5-5" />,
  x: <path d="M4 4l16 16M20 4 4 20" />,
  code: (
    <>
      <path d="m8 9-3 3 3 3" />
      <path d="m16 9 3 3-3 3" />
    </>
  ),
  folder: <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />,
  file: (
    <>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
    </>
  ),
  'file-text': (
    <>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6M8 13h8M8 17h6" />
    </>
  ),
  image: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <circle cx="8.5" cy="8.5" r="1.5" />
      <path d="m21 15-5-5L5 21" />
    </>
  ),
  'rotate-cw': (
    <>
      <path d="M21 12a9 9 0 1 1-3-6.7L21 8" />
      <path d="M21 3v5h-5" />
    </>
  ),
};

export function Icon({ name, class: className = 'icon' }: { name: IconName; class?: string }): JSX.Element {
  return (
    <svg class={className} viewBox="0 0 24 24" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}
