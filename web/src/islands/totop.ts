export function mountBackToTop(): void {
  if (!document.body.hasAttribute('data-totop')) return;
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'totop';
  button.title = '回到顶部';
  button.setAttribute('aria-label', '回到顶部');
  button.textContent = '↑';
  button.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'auto' });
  });
  document.body.appendChild(button);
}
