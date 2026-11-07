/**
 * Directory rows keep their action icons visible. The action column is fixed
 * at two slots: normally one icon per action, and when a row has more than two
 * actions the trailing ones move into the row's "more" popup.
 */
const ROW_SLOTS = 2;

interface RowState {
  actions: HTMLElement;
  more: HTMLElement;
  panel: HTMLElement;
  button: HTMLElement;
}

function rowItems(state: RowState): HTMLElement[] {
  const inline = Array.from(
    state.actions.querySelectorAll<HTMLElement>(':scope > .dl:not(.more-btn)'),
  );
  const hidden = Array.from(
    state.panel.querySelectorAll<HTMLElement>(':scope > .dl'),
  );
  return inline.concat(hidden);
}

export function mountDirRows(): void {
  const states: RowState[] = [];
  for (const row of document.querySelectorAll<HTMLElement>('.dir-row')) {
    const actions = row.querySelector<HTMLElement>('.row-actions');
    const more = actions?.querySelector<HTMLElement>('.row-more');
    const panel = more?.querySelector<HTMLElement>('.page-actions');
    const button = more?.querySelector<HTMLElement>('.more-btn');
    if (!actions || !more || !panel || !button) continue;
    if (!actions.querySelector('.dl')) continue;
    states.push({ actions, more, panel, button });
  }
  if (states.length === 0) return;

  function apply(): void {
    const slots = ROW_SLOTS;
    for (const state of states) {
      const items = rowItems(state);
      const total = items.length;
      const hidden = total > slots;
      const visible = hidden ? 1 : total;
      state.panel.hidden = true;
      state.button.setAttribute('aria-expanded', 'false');
      state.more.hidden = !hidden;
      items.forEach((item, index) => {
        const host = index < visible ? state.actions : state.panel;
        if (item.parentElement !== host) host.appendChild(item);
      });
      // Keep the "more" trigger as the last item so the popup stays anchored
      // to the right edge of the action column.
      if (state.more.parentElement !== state.actions) {
        state.actions.appendChild(state.more);
      }
    }
  }

  apply();
  window.addEventListener('resize', apply);
}
