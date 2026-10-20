export type IslandWhen = 'immediate' | 'idle' | 'visible';

export interface IslandDefinition {
  name: string;
  when: IslandWhen;
  root?: () => Element | null;
  mount: () => void | Promise<void>;
}

export interface IslandDiagnostics {
  mounted: string[];
  errors: string[];
}

declare global {
  interface Window {
    __mdviewIslands?: IslandDiagnostics;
    hljs?: {
      highlightElement: (element: HTMLElement) => void;
    };
  }
}
