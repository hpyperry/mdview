(function () {
  'use strict';

  function applyTheme() {
    var dark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.body.classList.toggle('vscode-dark', dark);
    document.body.classList.toggle('vscode-light', !dark);
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

  function addCopyButtons() {
    document.querySelectorAll('pre').forEach(function (pre) {
      var code = pre.querySelector('code');
      if (!code) return;
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'copy-btn';
      button.textContent = '复制';
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
      pre.appendChild(button);
    });
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

  document.addEventListener('DOMContentLoaded', function () {
    applyTheme();
    if (window.matchMedia) {
      var query = window.matchMedia('(prefers-color-scheme: dark)');
      if (query.addEventListener) query.addEventListener('change', applyTheme);
    }
    if (window.hljs) {
      document.querySelectorAll('pre code').forEach(function (code) {
        try { window.hljs.highlightElement(code); } catch (err) { /* keep plain text */ }
      });
    }
    addCopyButtons();
    addZoom();
    addBackToTop();
  });
})();
