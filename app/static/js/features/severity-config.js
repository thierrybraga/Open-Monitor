// severity-config.js
// Reads JSON config from the DOM and exposes it as window.severityConfig
(function() {
  try {
    var el = document.getElementById('severity-config');
    if (!el) return;
    var text = el.textContent || '';
    if (!text.trim()) return;
    var cfg = {};
    try {
      cfg = JSON.parse(text);
    } catch (e) {
      // Attempt to recover if HTML entities or whitespace cause issues
      try { cfg = JSON.parse(text.replace(/\u00a0/g, ' ')); } catch (_) { return; }
    }
    if (cfg && typeof cfg === 'object') {
      window.severityConfig = cfg;
      // Attach data-severity to root container for CSS hooks
      var root = document.querySelector('.vulnerability-details-page');
      if (root && cfg.severity) root.setAttribute('data-severity', String(cfg.severity));
    }
  } catch (e) {
    // Silently ignore to avoid breaking the page
  }
})();