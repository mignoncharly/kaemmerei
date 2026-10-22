/* Progressive enhancement: authorization and mutations stay on the server. */
(() => {
  const sidebar = document.querySelector('.sidebar');
  const toggle = document.querySelector('[data-nav-toggle]');
  const backdrop = document.querySelector('.drawer-backdrop');
  const workspace = document.querySelector('#app-workspace');
  const mobile = matchMedia('(max-width: 1000px)');
  let returnFocus;
  function closeDrawer(restore = true) {
    document.body.classList.remove('nav-open');
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
    if (backdrop) backdrop.hidden = true;
    if (workspace) workspace.inert = false;
    if (sidebar) { sidebar.inert = mobile.matches; sidebar.removeAttribute('role'); sidebar.removeAttribute('aria-modal'); }
    if (restore && returnFocus) returnFocus.focus();
  }
  if (sidebar) {
    document.body.classList.add('navigation-ready'); closeDrawer(false);
    toggle.addEventListener('click', () => {
      returnFocus = document.activeElement; sidebar.inert = false;
      sidebar.setAttribute('role', 'dialog'); sidebar.setAttribute('aria-modal', 'true');
      document.body.classList.add('nav-open'); toggle.setAttribute('aria-expanded', 'true');
      backdrop.hidden = false; workspace.inert = true;
      sidebar.querySelector('[data-nav-close]').focus();
    });
    document.querySelectorAll('[data-nav-close]').forEach(button => button.addEventListener('click', () => closeDrawer()));
    mobile.addEventListener('change', () => closeDrawer(false));
    document.addEventListener('keydown', event => {
      if (!document.body.classList.contains('nav-open')) return;
      if (event.key === 'Escape') { event.preventDefault(); closeDrawer(); }
      if (event.key === 'Tab') {
        const items = [...sidebar.querySelectorAll('a,button')].filter(item => item.getClientRects().length);
        const first = items[0], last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    });
  }
  document.querySelectorAll('.table-scroll').forEach(region => {
    region.tabIndex = 0; region.setAttribute('role', 'region');
    region.setAttribute('aria-label', 'Datentabelle – bei Bedarf horizontal scrollen');
  });
  const filterForm = document.querySelector('#contract-filter-form');
  if (filterForm && typeof HTMLDialogElement !== 'undefined' && HTMLDialogElement.prototype.showModal) {
    const disclosure = document.querySelector('#advanced-filter-disclosure');
    const filterToggle = document.querySelector('#filter-toggle');
    const panel = document.querySelector('#advanced-filter-panel');
    const dialog = document.createElement('dialog');
    dialog.className = 'contract-filter-dialog';
    dialog.setAttribute('aria-labelledby', 'filter-panel-title');
    // Move the one existing form into the native modal. No duplicated controls.
    dialog.append(panel);
    disclosure.replaceWith(dialog);
    filterToggle.hidden = false;
    panel.querySelector('[data-filter-close]').hidden = false;
    function positionFilters() {
      const anchor = filterToggle.getBoundingClientRect();
      const width = Math.min(620, window.innerWidth - 32);
      const top = Math.max(16, Math.min(anchor.bottom + 8, window.innerHeight - 96));
      // CSSOM coordinates keep placement local to the trigger without inline templates.
      dialog.style.setProperty('--filter-left', Math.max(16, Math.min(anchor.right - width, window.innerWidth - width - 16)) + 'px');
      dialog.style.setProperty('--filter-top', top + 'px');
      dialog.style.setProperty('--filter-height', Math.max(80, window.innerHeight - top - 16) + 'px');
    }
    function openFilters(focusSearch = true) {
      if (dialog.open) return;
      positionFilters();
      dialog.showModal(); // Native focus containment and inert background, also on mobile.
      dialog.scrollTop = 0;
      document.body.classList.add('contract-filter-open');
      filterToggle.setAttribute('aria-expanded', 'true');
      if (focusSearch) filterForm.querySelector('#q').focus({preventScroll: true});
    }
    function closeFilters() { if (dialog.open) dialog.close(); }
    filterToggle.addEventListener('click', () => dialog.open ? closeFilters() : openFilters());
    panel.querySelector('[data-filter-close]').addEventListener('click', closeFilters);
    dialog.addEventListener('close', () => {
      if (dialog.open) return;
      document.body.classList.remove('contract-filter-open');
      filterToggle.setAttribute('aria-expanded', 'false');
      filterToggle.focus({preventScroll: true});
    });
    // Escape uses the native dialog cancel event. Only a full outside click dismisses.
    const outside = event => {
      const rect = dialog.getBoundingClientRect();
      return event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom);
    };
    let outsideStart = false;
    dialog.addEventListener('pointerdown', event => { outsideStart = outside(event); });
    dialog.addEventListener('click', event => { if (outsideStart && outside(event)) closeFilters(); outsideStart = false; });
    window.addEventListener('resize', () => { if (dialog.open) positionFilters(); });
    filterForm.addEventListener('invalid', event => {
      openFilters(false);
    }, true);
    const invalid = panel.querySelector('[aria-invalid="true"], [role="alert"]');
    if (invalid) { openFilters(false); invalid.focus(); }
    window.addEventListener('pageshow', () => {
      filterToggle.setAttribute('aria-expanded', String(dialog.open));
      document.body.classList.toggle('contract-filter-open', dialog.open);
      if (dialog.open) positionFilters();
      else if (location.hash === '#contract-toolbar' || location.hash === '#q') filterToggle.focus({preventScroll: true});
    });
  }
  const selectionForm = document.querySelector('#selection-export-form');
  if (selectionForm) {
    const boxes = [...document.querySelectorAll('.select-contract')];
    const all = document.querySelector('#select-page');
    const exportButton = document.querySelector('#export-selection');
    const ids = document.querySelector('#selected-contract-ids');
    const count = document.querySelector('#selection-count');
    function syncSelection() {
      const selected = boxes.filter(box => box.checked);
      ids.value = selected.map(box => box.value).join(',');
      all.checked = selected.length === boxes.length;
      all.indeterminate = selected.length > 0 && selected.length < boxes.length;
      selectionForm.hidden = selected.length === 0;
      exportButton.disabled = selected.length === 0;
      count.textContent = selected.length === 1 ? '1 Vertrag ausgewählt'
        : selected.length === boxes.length ? `Alle ${selected.length} Verträge auf dieser Seite ausgewählt`
        : `${selected.length} Verträge ausgewählt`;
      boxes.forEach(box => box.closest('tr').classList.toggle('export-selected', box.checked));
    }
    function clearSelection() { boxes.forEach(box => { box.checked = false; }); syncSelection(); }
    document.querySelectorAll('[data-selection-cell]').forEach(cell => { cell.hidden = false; });
    boxes.forEach(box => box.addEventListener('change', syncSelection));
    all.addEventListener('change', () => { boxes.forEach(box => { box.checked = all.checked; }); syncSelection(); });
    document.querySelector('#clear-selection').addEventListener('click', () => { clearSelection(); all.focus(); });
    selectionForm.addEventListener('submit', event => {
      syncSelection();
      if (exportButton.disabled) event.preventDefault();
      // Native POST/download: backend errors remain visible; no speculative success toast.
    });
    filterForm?.addEventListener('input', clearSelection);
    filterForm?.addEventListener('change', clearSelection);
    window.addEventListener('pagehide', clearSelection);
    window.addEventListener('pageshow', clearSelection); // Includes restored back/forward pages.
    clearSelection();
  }
  const excelFile = document.querySelector('#excel-file');
  if (excelFile) {
    const filename = document.createElement('span');
    filename.className = 'excel-filename'; filename.setAttribute('role', 'status');
    excelFile.after(filename);
    excelFile.addEventListener('change', () => {
      filename.textContent = excelFile.files.length ? 'Ausgewählt: ' + excelFile.files[0].name : '';
    });
  }
  document.querySelectorAll('input,select,textarea').forEach(input => {
    const hint = input.parentElement.querySelector('.hint,.field-hint');
    if (hint && input.id && !input.hasAttribute('aria-describedby')) {
      hint.id ||= input.id + '-hint'; input.setAttribute('aria-describedby', hint.id);
    }
    input.addEventListener('invalid', () => {
      input.setAttribute('aria-invalid', 'true');
      if (!input.id) return;
      let message = document.getElementById(input.id + '-error');
      if (!message) { message = document.createElement('span'); message.id = input.id + '-error'; message.className = 'field-error'; input.after(message); }
      message.textContent = input.validationMessage;
      input.setAttribute('aria-describedby', [input.getAttribute('aria-describedby'), message.id].filter(Boolean).join(' '));
    });
    input.addEventListener('input', () => {
      input.removeAttribute('aria-invalid');
      document.getElementById(input.id + '-error')?.remove();
      const ids = (input.getAttribute('aria-describedby') || '').split(' ').filter(id => id !== input.id + '-error');
      if (ids.length) input.setAttribute('aria-describedby', ids.join(' ')); else input.removeAttribute('aria-describedby');
    });
  });
  const alert = document.querySelector('main .alert[role="alert"]');
  if (alert) { alert.tabIndex = -1; alert.focus(); }
  document.querySelectorAll('form[method="post"]').forEach(form => {
    if (form === selectionForm) return; // A native file download does not navigate the page.
    form.addEventListener('submit', () => {
      if (form.dataset.submitted) return;
      form.dataset.submitted = 'true';
      const status = document.createElement('p'); status.className = 'submission-status';
      status.setAttribute('role', 'status');
      status.textContent = form.enctype === 'multipart/form-data'
        ? 'Übertragung und Prüfung läuft. Bitte warten …' : 'Anfrage wird verarbeitet …';
      form.append(status);
    });
  });
  window.addEventListener('pageshow', () => {
    document.querySelectorAll('.submission-status').forEach(item => item.remove());
    document.querySelectorAll('form[data-submitted]').forEach(form => delete form.dataset.submitted);
  });
})();
