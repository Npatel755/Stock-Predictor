/* Display-only controls for the saved SVG. No market data or simulation. */
(() => {
  const chart = document.getElementById('top5-chart');
  const status = document.getElementById('top5-status');
  const toggles = Array.from(document.querySelectorAll('[data-top5-toggle]'));
  if (!chart || !status || !toggles.length) return;

  function sync() {
    const svg = chart.contentDocument;
    let visible = 0;
    toggles.forEach(input => {
      const rank = input.dataset.top5Toggle;
      const show = input.checked;
      visible += Number(show);
      ['net', 'dd'].forEach(kind => {
        const group = svg?.getElementById(`top5-${kind}-${rank}`);
        if (group) group.style.display = show ? '' : 'none';
      });
      ['line', 'label'].forEach(kind => {
        const group = svg?.getElementById(`top5-legend-${kind}-${rank}`);
        if (group) group.style.opacity = show ? '1' : '0.25';
      });
    });
    status.textContent = visible ? `Showing ${visible} of ${toggles.length} strategies.` : 'No strategies selected. Check a strategy or choose Show all.';
  }

  toggles.forEach(input => input.addEventListener('change', sync));
  document.querySelectorAll('[data-top5-only]').forEach(button => {
    button.addEventListener('click', () => {
      toggles.forEach(input => { input.checked = input.dataset.top5Toggle === button.dataset.top5Only; });
      sync();
    });
  });
  document.getElementById('top5-show-all')?.addEventListener('click', () => {
    toggles.forEach(input => { input.checked = true; });
    sync();
  });
  document.getElementById('top5-hide-all')?.addEventListener('click', () => {
    toggles.forEach(input => { input.checked = false; });
    sync();
  });
  chart.addEventListener('load', sync);
  sync();
})();
