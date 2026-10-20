(function () {
  'use strict';

  var root = document.documentElement;

  function readPref(key, fallback) {
    try {
      return localStorage.getItem(key) || fallback;
    } catch (err) {
      return fallback;
    }
  }

  function savePref(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch (err) {
      /* private mode */
    }
  }

  function applyTheme(mode) {
    if (mode !== 'light' && mode !== 'dark') mode = 'system';
    root.dataset.themeMode = mode;
    if (mode === 'system') {
      delete root.dataset.theme;
    } else {
      root.dataset.theme = mode;
    }
    var button = document.getElementById('theme-toggle');
    if (!button) return;
    var labels = { system: '跟随系统', light: '浅色', dark: '深色' };
    button.title = '主题：' + labels[mode];
    button.setAttribute('aria-label', '切换主题，当前' + labels[mode]);
  }

  function toggleTheme() {
    var order = ['system', 'light', 'dark'];
    var current = readPref('mdview-theme', 'system');
    var index = order.indexOf(current);
    if (index < 0) index = 0;
    var next = order[(index + 1) % order.length];
    savePref('mdview-theme', next);
    applyTheme(next);
  }

  function copyText(text, done, fail) {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done, fail);
      return;
    }
    var area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    try {
      document.execCommand('copy') ? done() : fail();
    } catch (err) {
      fail();
    }
    document.body.removeChild(area);
  }

  var MAX_HIGHLIGHT_CHARS = 256 * 1024;
  var SOURCE_LINE_HEIGHT = 21;
  var SOURCE_CHUNK_MARGIN = 1500;

  function hasExplicitLanguage(code) {
    return /(?:^|\s)language-[\w-]+/.test(code.className || '');
  }

  function languageOf(code) {
    var match = (code.className || '').match(/(?:^|\s)language-([\w-]+)/);
    if (!match) return '代码';
    return match[1];
  }

  function addCodeBlocks() {
    document.querySelectorAll('.markdown-body pre > code').forEach(function (code) {
      var pre = code.parentElement;
      if (!pre || pre.closest('.code-block')) return;
      var block = document.createElement('div');
      block.className = 'code-block';
      var bar = document.createElement('div');
      bar.className = 'code-bar';
      var lang = document.createElement('span');
      lang.className = 'lang';
      lang.textContent = languageOf(code) + (code.dataset.highlightSkipped === '1' ? ' · 未高亮' : '');
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'copy-btn';
      button.textContent = '复制';
      button.setAttribute('aria-label', '复制代码');
      button.addEventListener('click', function () {
        copyText(
          code.innerText,
          function () {
            button.textContent = '已复制';
            window.setTimeout(function () { button.textContent = '复制'; }, 1200);
          },
          function () { button.textContent = '复制失败'; }
        );
      });
      bar.appendChild(lang);
      bar.appendChild(button);
      pre.parentNode.insertBefore(block, pre);
      block.appendChild(bar);
      block.appendChild(pre);
    });
  }

  function addSourceChunks() {
    var wrap = document.querySelector('.source-chunked');
    if (!wrap) return;
    var chunks = Array.prototype.slice.call(wrap.querySelectorAll('.source-chunk'));
    if (!chunks.length) return;
    var chunkSize = Number.parseInt(wrap.getAttribute('data-chunk-lines'), 10) || 500;
    var total = Number.parseInt(wrap.getAttribute('data-source-lines'), 10) || 0;

    function startOf(chunk) {
      return Number.parseInt(chunk.getAttribute('data-start'), 10) || 1;
    }

    function ensureGutter(chunk) {
      if (chunk.dataset.gutterReady === '1') return;
      var start = startOf(chunk);
      var rows = Number.parseInt(chunk.getAttribute('data-rows'), 10) || 0;
      var gutter = chunk.querySelector('.gutter');
      if (!gutter || !rows) return;
      var fragment = document.createDocumentFragment();
      for (var i = 0; i < rows; i += 1) {
        var line = start + i;
        var anchor = document.createElement('a');
        anchor.id = 'L' + line;
        anchor.href = '#L' + line;
        anchor.textContent = String(line);
        fragment.appendChild(anchor);
      }
      gutter.replaceChildren(fragment);
      chunk.dataset.gutterReady = '1';
    }

    function ensureHighlight(chunk) {
      if (chunk.dataset.highlightReady === '1') return;
      chunk.dataset.highlightReady = '1';
      var code = chunk.querySelector('.code code');
      if (!window.hljs || !code || !hasExplicitLanguage(code)) return;
      if (code.textContent.length > MAX_HIGHLIGHT_CHARS) {
        code.dataset.highlightSkipped = '1';
        return;
      }
      try { window.hljs.highlightElement(code); } catch (err) { /* keep plain text */ }
    }

    var targetAnchor = null;
    var targetOverlay = null;

    function clearTarget() {
      if (targetAnchor) targetAnchor.classList.remove('target');
      targetAnchor = null;
      if (targetOverlay && targetOverlay.parentNode) {
        targetOverlay.parentNode.removeChild(targetOverlay);
      }
      targetOverlay = null;
    }

    function goHash() {
      var match = window.location.hash.match(/^#L(\d+)$/);
      if (!match) {
        clearTarget();
        return;
      }
      var line = Number.parseInt(match[1], 10);
      var chunk = line > 0 ? chunks[Math.floor((line - 1) / chunkSize)] : null;
      if (!line || (total && line > total) || !chunk) {
        clearTarget();
        return;
      }
      clearTarget();
      ensureGutter(chunk);
      var anchor = document.getElementById('L' + line);
      if (!anchor) return;
      var rows = Number.parseInt(chunk.getAttribute('data-rows'), 10) || 0;
      var offset = line - startOf(chunk);
      if (offset >= 0 && offset < rows) {
        var overlay = document.createElement('div');
        overlay.className = 'source-target-line';
        overlay.style.top = (14 + offset * SOURCE_LINE_HEIGHT) + 'px';
        chunk.appendChild(overlay);
        targetOverlay = overlay;
      }
      anchor.classList.add('target');
      targetAnchor = anchor;
      window.requestAnimationFrame(function () {
        anchor.scrollIntoView({ block: 'center' });
      });
    }

    function enhanceVisible() {
      var viewport = window.innerHeight || 800;
      chunks.forEach(function (chunk) {
        var rect = chunk.getBoundingClientRect();
        if (rect.bottom < -SOURCE_CHUNK_MARGIN || rect.top > viewport + SOURCE_CHUNK_MARGIN) return;
        ensureGutter(chunk);
        ensureHighlight(chunk);
      });
    }

    var enhanceScheduled = false;
    function scheduleEnhance() {
      if (enhanceScheduled) return;
      enhanceScheduled = true;
      window.setTimeout(function () {
        enhanceScheduled = false;
        enhanceVisible();
      }, 80);
    }

    window.addEventListener('scroll', scheduleEnhance, { passive: true });
    window.addEventListener('resize', scheduleEnhance);
    enhanceVisible();

    window.addEventListener('hashchange', goHash);
    if (window.location.hash) goHash();
  }

  function addToc() {
    var article = document.querySelector('.markdown-body');
    var column = document.getElementById('toc-nav');
    var inline = document.getElementById('toc-slot');
    var inlineList = inline ? inline.querySelector('.toc-list') : null;
    if (!article || (!column && !inlineList)) return;
    var shell = document.getElementById('shell');
    var toggle = document.getElementById('toc-toggle');
    var headings = Array.prototype.slice.call(article.querySelectorAll('h2, h3'));
    if (!headings.length) {
      if (column) column.closest('.toc-col').hidden = true;
      if (inline) inline.hidden = true;
      if (shell) shell.classList.add('no-toc');
      if (toggle) toggle.hidden = true;
      return;
    }

    var lists = [];
    if (column) lists.push(column);
    if (inlineList) lists.push(inlineList);
    var links = [];
    headings.forEach(function (heading, index) {
      if (!heading.id) {
        var base = 'toc-' + (index + 1);
        var id = base;
        var suffix = 1;
        while (document.getElementById(id)) {
          suffix += 1;
          id = base + '-' + suffix;
        }
        heading.id = id;
      }
      lists.forEach(function (list) {
        var link = document.createElement('a');
        link.href = '#' + heading.id;
        link.className = heading.tagName === 'H3' ? 'toc-h3' : 'toc-h2';
        link.textContent = heading.textContent;
        link.setAttribute('data-target', heading.id);
        link.addEventListener('click', function (event) {
          event.preventDefault();
          heading.scrollIntoView({ behavior: 'smooth', block: 'start' });
          setActive(heading.id);
        });
        list.appendChild(link);
        links.push(link);
      });
    });

    if (inline) {
      var summary = inline.querySelector('summary');
      if (summary) summary.textContent = '本页目录（' + headings.length + '）';
    }

    var activeId = '';
    function setActive(id) {
      activeId = id;
      links.forEach(function (link) {
        var active = link.getAttribute('data-target') === id;
        link.classList.toggle('active', active);
        if (active) link.setAttribute('aria-current', 'location');
        else link.removeAttribute('aria-current');
      });
      if (!column) return;
      var box = column.closest('.toc-col');
      if (!box || box.offsetParent === null) return;
      var activeLink = links.filter(function (link) {
        return link.parentElement === column && link.getAttribute('data-target') === id;
      })[0];
      if (!activeLink) return;
      var boxRect = box.getBoundingClientRect();
      var linkRect = activeLink.getBoundingClientRect();
      if (linkRect.top < boxRect.top + 12) {
        box.scrollTop += linkRect.top - boxRect.top - 12;
      } else if (linkRect.bottom > boxRect.bottom - 12) {
        box.scrollTop += linkRect.bottom - boxRect.bottom + 12;
      }
    }

    function spy() {
      var bar = document.querySelector('.topbar');
      var offset = (bar ? bar.getBoundingClientRect().height : 58) + 20;
      var active = headings[0].id;
      for (var i = 0; i < headings.length; i += 1) {
        if (headings[i].getBoundingClientRect().top <= offset) active = headings[i].id;
        else break;
      }
      if (active !== activeId) setActive(active);
    }

    var scheduled = false;
    window.addEventListener('scroll', function () {
      if (scheduled) return;
      scheduled = true;
      window.requestAnimationFrame(function () {
        scheduled = false;
        spy();
      });
    }, { passive: true });
    window.addEventListener('resize', spy);
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) spy();
    });

    function setTocHidden(hidden) {
      if (hidden) root.dataset.toc = 'hidden';
      else delete root.dataset.toc;
      savePref('mdview-toc', hidden ? 'hidden' : 'visible');
      if (toggle) {
        toggle.setAttribute('aria-pressed', String(!hidden));
        toggle.title = hidden ? '显示本页目录' : '隐藏本页目录';
      }
    }
    if (toggle) {
      setTocHidden(root.dataset.toc === 'hidden');
      toggle.addEventListener('click', function () {
        setTocHidden(root.dataset.toc !== 'hidden');
      });
    }
    spy();
  }

  function addZoom() {
    var dialog = null;
    var dialogImage = null;
    var caption = null;
    var lastFocus = null;

    function ensureDialog() {
      if (dialog) return;
      dialog = document.createElement('dialog');
      dialog.className = 'zoomdlg';
      dialog.tabIndex = -1;

      var close = document.createElement('button');
      close.type = 'button';
      close.className = 'zoom-close';
      close.setAttribute('aria-label', '关闭');
      close.innerHTML = '<svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><path d="M4 4l12 12M16 4L4 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
      close.addEventListener('click', function () { dialog.close(); });

      dialogImage = document.createElement('img');
      caption = document.createElement('p');
      caption.className = 'zoom-caption';
      dialog.appendChild(close);
      dialog.appendChild(dialogImage);
      dialog.appendChild(caption);
      dialog.addEventListener('click', function (event) {
        if (event.target === dialog) dialog.close();
      });
      dialog.addEventListener('close', function () {
        if (lastFocus) lastFocus.focus();
      });
      document.body.appendChild(dialog);
    }

    function show(source, alt, focusElement) {
      ensureDialog();
      lastFocus = focusElement;
      dialogImage.src = source;
      dialogImage.alt = alt || '';
      dialogImage.removeAttribute('loading');
      caption.textContent = alt || '';
      dialog.showModal();
      dialog.focus();
    }

    document.querySelectorAll('.markdown-body a.zoom').forEach(function (link) {
      link.classList.add('zoomable');
      link.addEventListener('click', function (event) {
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
          return;
        }
        event.preventDefault();
        var image = link.querySelector('img');
        show(link.getAttribute('href'), image ? image.alt : '', link);
      });
    });

    document.querySelectorAll('.markdown-body img').forEach(function (image) {
      if (image.closest('a')) return;
      image.classList.add('zoomable');
      image.addEventListener('click', function (event) {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        show(image.currentSrc || image.src, image.alt || '', image);
      });
    });
  }

  function addBackToTop() {
    if (!document.body.hasAttribute('data-totop')) return;
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'totop';
    button.title = '回到顶部';
    button.setAttribute('aria-label', '回到顶部');
    button.textContent = '↑';
    button.addEventListener('click', function () {
      var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      window.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
    });
    document.body.appendChild(button);
  }

  function addSidebar() {
    var toggle = document.getElementById('sidebar-toggle');
    var scrim = document.getElementById('scrim');
    if (!toggle) return;
    var narrow = window.matchMedia('(max-width: 900px)');

    function syncScrim() {
      if (!scrim) return;
      scrim.hidden = !(narrow.matches && root.dataset.sidebarOpen === '1');
    }
    function closeDrawer() {
      delete root.dataset.sidebarOpen;
      syncScrim();
    }

    toggle.addEventListener('click', function () {
      if (narrow.matches) {
        if (root.dataset.sidebarOpen === '1') {
          closeDrawer();
        } else {
          root.dataset.sidebarOpen = '1';
          syncScrim();
        }
        return;
      }
      if (root.dataset.sidebar === 'collapsed') {
        delete root.dataset.sidebar;
        savePref('mdview-sidebar', 'open');
      } else {
        root.dataset.sidebar = 'collapsed';
        savePref('mdview-sidebar', 'collapsed');
      }
      syncScrim();
    });
    if (scrim) scrim.addEventListener('click', closeDrawer);
    if (narrow.addEventListener) narrow.addEventListener('change', closeDrawer);
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && root.dataset.sidebarOpen === '1') closeDrawer();
    });
    syncScrim();
  }

  function addSearchBehaviour() {
    var input = document.querySelector('.searchbox input[name="q"]');
    if (!input) return;
    document.addEventListener('keydown', function (event) {
      var target = event.target;
      var typing = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable);
      if (event.key === '/' && !typing) {
        event.preventDefault();
        input.focus();
        input.select();
      }
      if (event.key === 'Escape' && document.activeElement === input) {
        input.value = '';
        input.blur();
      }
    });

    if (document.body.dataset.page !== 'search') return;
    var query = input.value.trim();
    if (!query) return;
    var needle = query.toLowerCase();
    document.querySelectorAll('.hit-snippet').forEach(function (snippet) {
      markNode(snippet, needle);
    });
  }

  function markNode(node, needle) {
    if (node.nodeType === 3) {
      var text = node.nodeValue;
      var lower = text.toLowerCase();
      var index = lower.indexOf(needle);
      if (index < 0) return;
      var fragment = document.createDocumentFragment();
      var cursor = 0;
      while (index >= 0) {
        if (index > cursor) fragment.appendChild(document.createTextNode(text.slice(cursor, index)));
        var mark = document.createElement('mark');
        mark.textContent = text.slice(index, index + needle.length);
        fragment.appendChild(mark);
        cursor = index + needle.length;
        index = lower.indexOf(needle, cursor);
      }
      if (cursor < text.length) fragment.appendChild(document.createTextNode(text.slice(cursor)));
      node.parentNode.replaceChild(fragment, node);
      return;
    }
    if (node.nodeType !== 1) return;
    if (node.tagName === 'MARK' || node.tagName === 'SCRIPT' || node.tagName === 'STYLE') return;
    Array.prototype.slice.call(node.childNodes).forEach(function (child) {
      markNode(child, needle);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    root.classList.remove('no-js');
    root.classList.add('js');
    applyTheme(readPref('mdview-theme', 'system'));
    var themeButton = document.getElementById('theme-toggle');
    if (themeButton) themeButton.addEventListener('click', toggleTheme);

    if (window.hljs) {
      document.querySelectorAll('pre code').forEach(function (code) {
        if (code.closest('.source-chunk')) return;
        if (!hasExplicitLanguage(code)) return;
        if (code.textContent.length > MAX_HIGHLIGHT_CHARS) {
          code.dataset.highlightSkipped = '1';
          return;
        }
        try { window.hljs.highlightElement(code); } catch (err) { /* keep plain text */ }
      });
    }
    addCodeBlocks();
    addSourceChunks();
    addToc();
    addZoom();
    addBackToTop();
    addSidebar();
    addSearchBehaviour();
  });
})();
