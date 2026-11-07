/* No simulated scans, fake submissions, or automatic platform changes. */
(() => {
  const menu = document.querySelector('.menu-btn');
  const nav = document.getElementById('main-nav');
  function closeMenu() { if (!menu || !nav) return; nav.classList.remove('open'); menu.setAttribute('aria-expanded', 'false'); menu.setAttribute('aria-label', 'Open navigation'); }
  menu?.addEventListener('click', () => { const open = menu.getAttribute('aria-expanded') !== 'true'; nav.classList.toggle('open', open); menu.setAttribute('aria-expanded', String(open)); menu.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation'); });
  nav?.addEventListener('click', e => { if (e.target.closest('a')) closeMenu(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && menu?.getAttribute('aria-expanded') === 'true') { closeMenu(); menu.focus(); } });
  document.getElementById('align-demo')?.addEventListener('click', e => { const stage = e.currentTarget.closest('.alignment-stage'); const aligned = stage.classList.toggle('locked'); e.currentTarget.setAttribute('aria-pressed', String(aligned)); e.currentTarget.textContent = aligned ? 'Reset the illustration ↗' : 'Align the illustration ↗'; });
  // Progressive enhancement: content stays visible if JS or observers are unavailable.
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!reduceMotion && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => entries.forEach(entry => { if (entry.isIntersecting) { entry.target.classList.add('in'); observer.unobserve(entry.target); } }), {threshold: 0.08});
    document.documentElement.classList.add('js');
    document.querySelectorAll('.rv').forEach(el => observer.observe(el));
  }
  document.querySelectorAll('[data-copy-target]').forEach(button => button.addEventListener('click', async () => {
    const field = document.getElementById(button.dataset.copyTarget); const status = button.parentElement.querySelector('.copy-status');
    try { await navigator.clipboard.writeText(field.value); if (status) status.textContent = 'Copied'; }
    catch (_) { field.focus(); field.select(); if (status) status.textContent = 'Select the text and copy it manually.'; }
  }));
  const checklist = document.querySelector('[data-checklist]');
  if (checklist) {
    const boxes = [...checklist.querySelectorAll('input[type=checkbox]')];
    const update = () => { const n = boxes.filter(box => box.checked).length; document.getElementById('checklist-count').textContent = `${n} of ${boxes.length} completed`; const progress = document.getElementById('checklist-progress'); progress.max = boxes.length; progress.value = n; };
    boxes.forEach(box => box.addEventListener('change', update)); update();
  }
})();
