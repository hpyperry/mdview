import type { JSX } from 'preact';

type IconName = 'list' | 'chevrons-right' | 'copy' | 'check' | 'x' | 'code';

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
};

export function Icon({ name, class: className = 'icon' }: { name: IconName; class?: string }): JSX.Element {
  return (
    <svg class={className} viewBox="0 0 24 24" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}
