import type { IslandDefinition } from './types';
import { mountTheme } from './islands/theme';
import { mountNav } from './islands/nav';
import { mountSearch } from './islands/search';
import { mountMore } from './islands/more';
import { mountDirRows } from './islands/dirrows';
import { mountIslandHead } from './islands/islandhead';
import { mountBackToTop } from './islands/totop';
import { mountToc } from './islands/toc';
import { mountLineTarget } from './islands/linetarget';
import { mountMarkdownCode } from './islands/code';
import { mountZoom } from './islands/zoom';
import { mountSource } from './islands/source';
import { mountExport } from './islands/export';

export const islands: Record<string, IslandDefinition> = {
  theme: {
    name: 'theme',
    when: 'immediate',
    root: () => document.getElementById('theme-toggle'),
    mount: mountTheme,
  },
  nav: {
    name: 'nav',
    when: 'immediate',
    root: () => document.getElementById('nav-toggle'),
    mount: mountNav,
  },
  search: {
    name: 'search',
    when: 'immediate',
    root: () => document.querySelector('.search-wrap'),
    mount: mountSearch,
  },
  islandhead: {
    name: 'islandhead',
    when: 'immediate',
    root: () => document.querySelector('.island-head'),
    mount: mountIslandHead,
  },
  dirrows: {
    name: 'dirrows',
    when: 'immediate',
    root: () => document.querySelector('.dir-row'),
    mount: mountDirRows,
  },
  more: {
    name: 'more',
    when: 'immediate',
    root: () => document.querySelector('.more-menu'),
    mount: mountMore,
  },
  totop: {
    name: 'totop',
    when: 'immediate',
    root: () => (document.body.hasAttribute('data-totop') ? document.body : null),
    mount: mountBackToTop,
  },
  toc: {
    name: 'toc',
    when: 'immediate',
    root: () => document.getElementById('toc-rail'),
    mount: mountToc,
  },
  linetarget: {
    name: 'linetarget',
    when: 'immediate',
    root: () => document.querySelector('.markdown-body'),
    mount: mountLineTarget,
  },
  code: {
    name: 'code',
    when: 'idle',
    root: () => document.querySelector('.markdown-body'),
    mount: mountMarkdownCode,
  },
  zoom: {
    name: 'zoom',
    when: 'idle',
    root: () => document.querySelector('.markdown-body'),
    mount: mountZoom,
  },
  source: {
    name: 'source',
    when: 'visible',
    root: () => document.querySelector('.source-wrap'),
    mount: mountSource,
  },
  export: {
    name: 'export',
    when: 'idle',
    root: () => document.getElementById('export-png'),
    mount: mountExport,
  },
};
