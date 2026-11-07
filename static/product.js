/* No simulated scans, fake submissions, or automatic platform changes. */
(() => {
  const menu = document.querySelector('.menu-btn');
  const nav = document.getElementById('main-nav');
  function closeMenu() { if (!menu || !nav) return; nav.classList.remove('open'); menu.setAttribute('aria-expanded', 'false'); menu.setAttribute('aria-label', 'Open navigation'); }
  menu?.addEventListener('click', () => { const open = menu.getAttribute('aria-expanded') !== 'true'; nav.classList.toggle('open', open); menu.setAttribute('aria-expanded', String(open)); menu.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation'); });
  nav?.addEventListener('click', e => { if (e.target.closest('a')) closeMenu(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && menu?.getAttribute('aria-expanded') === 'true') { closeMenu(); menu.focus(); } });
  const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
  const reduceMotion = motionPreference.matches;
  const replay = document.getElementById('align-demo');
  if (replay) {
    const stage = replay.closest('.alignment-stage');
    let alignmentTimer;
    const align = () => stage.classList.add('locked');
    const play = () => {
      window.clearTimeout(alignmentTimer);
      if (motionPreference.matches) { align(); return; }
      stage.classList.remove('locked');
      alignmentTimer = window.setTimeout(align, 950);
    };
    replay.addEventListener('click', play);
    motionPreference.addEventListener('change', () => {
      if (motionPreference.matches) { window.clearTimeout(alignmentTimer); align(); }
    });
    play();
  }
  // Submit normally to the real audit endpoint; only the waiting UI is enhanced.
  const scanForm = document.querySelector('[data-scan-form]');
  if (scanForm) {
    const submit = scanForm.querySelector('button[type="submit"]');
    const status = document.getElementById('scan-progress');
    const initialStatus = status.textContent;
    const initialLabel = submit.textContent;
    const reset = () => {
      scanForm.removeAttribute('aria-busy');
      submit.disabled = false;
      submit.textContent = initialLabel;
      status.textContent = initialStatus;
    };
    scanForm.addEventListener('submit', event => {
      if (scanForm.getAttribute('aria-busy') === 'true') { event.preventDefault(); return; }
      scanForm.setAttribute('aria-busy', 'true');
      submit.disabled = true;
      submit.textContent = 'Checking available sources…';
      status.textContent = 'Checking available sources… this can take a moment';
    });
    // Back/forward cache must not leave an old form disabled.
    window.addEventListener('pageshow', reset);
  }
  // Progressive enhancement: content stays visible if JS or observers are unavailable.
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
