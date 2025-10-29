'use strict';

/**
 * Vulnerabilities Page Legacy Fallback (ES5)
 * This lightweight script avoids ES6 parse errors on older browsers.
 * It provides basic, safe behaviors without advanced filtering/sorting.
 */
(function() {
  function safeLog(msg) { try { console.log(msg); } catch (_){ } }

  function onReady(fn) {
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
      setTimeout(fn, 0);
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
  }

  function ensureSkipLink() {
    var existing = document.querySelector('.skip-link');
    if (existing) return;
    var skipLink = document.createElement('a');
    skipLink.href = '#vulnerabilities-table';
    skipLink.className = 'skip-link';
    skipLink.appendChild(document.createTextNode('Pular para tabela de vulnerabilidades'));
    skipLink.style.position = 'absolute';
    skipLink.style.top = '-40px';
    skipLink.style.left = '6px';
    skipLink.style.background = '#000';
    skipLink.style.color = '#fff';
    skipLink.style.padding = '8px';
    skipLink.style.textDecoration = 'none';
    skipLink.style.zIndex = '1000';
    skipLink.style.borderRadius = '4px';
    skipLink.addEventListener('focus', function() { this.style.top = '6px'; });
    skipLink.addEventListener('blur', function() { this.style.top = '-40px'; });
    document.body.insertBefore(skipLink, document.body.firstChild);
  }

  function markLegacyMode() {
    var table = document.getElementById('vulnerabilities-table');
    if (!table) return;
    var note = document.createElement('div');
    note.className = 'alert alert-info mt-2';
    note.setAttribute('role', 'status');
    note.appendChild(document.createTextNode('Modo legado ativo: funcionalidades avançadas de filtro/ordenar podem estar limitadas.'));
    var container = table.closest('.table-card') || table.closest('.table-section');
    if (container) {
      container.insertBefore(note, container.firstChild);
    }
  }

  onReady(function() {
    window.LegacyVulnerabilitiesFallback = true;
    ensureSkipLink();
    markLegacyMode();
    // Basic ARIA setup for table
    var table = document.getElementById('vulnerabilities-table');
    if (table) {
      table.setAttribute('role', 'table');
      table.setAttribute('aria-label', 'Tabela de vulnerabilidades (modo legado)');
    }
    // Make headers focusable to at least allow keyboard navigation (no JS sorting)
    var headers = document.querySelectorAll('.sortable');
    Array.prototype.forEach.call(headers, function(h) {
      h.setAttribute('tabindex', '0');
      h.setAttribute('role', 'columnheader');
      h.setAttribute('aria-sort', 'none');
    });
    safeLog('Vulnerabilities legacy fallback initialized');
  });
})();