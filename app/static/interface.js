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
  if (filterForm) {
    const disclosure = document.querySelector('#advanced-filter-disclosure');
    const filterToggle = document.querySelector('#filter-toggle');
    const syncFilters = () => filterToggle.setAttribute('aria-expanded', String(disclosure.open));
    filterToggle.hidden = false;
    filterForm.classList.add('toolbar-enhanced');
    filterToggle.addEventListener('click', () => {
      disclosure.open = !disclosure.open;
      syncFilters();
    });
    disclosure.addEventListener('toggle', syncFilters);
    // Reveal invalid controls before the browser tries to focus them.
    filterForm.addEventListener('invalid', event => {
      if (disclosure.contains(event.target)) { disclosure.open = true; syncFilters(); }
    }, true);
    if (disclosure.querySelector('[aria-invalid="true"], [role="alert"]')) disclosure.open = true;
    syncFilters();
    window.addEventListener('pageshow', syncFilters);
    // Removal links reload the server result and return focus to a stable control.
    if (location.hash === '#contract-toolbar') filterToggle.focus({preventScroll: true});
    if (location.hash === '#q') document.querySelector('#q').focus({preventScroll: true});
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
