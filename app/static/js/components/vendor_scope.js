// vendor_scope.js
// Propaga automaticamente vendor_ids em links de navegação (navbar, sidebar)
// e em outros links internos relevantes.

(function () {
  function getVendorScope() {
    try {
      const url = new URL(window.location.href);
      const scope = (url.searchParams.get('vendor_scope') || '').trim().toLowerCase();
      if (scope === 'all') return 'all';
      // Fallback via localStorage (se existir)
      try {
        const saved = (localStorage.getItem('vendorSelection.scope') || '').trim().toLowerCase();
        if (saved === 'all') return 'all';
      } catch (_) {}
      return 'selected';
    } catch (_) {
      return 'selected';
    }
  }

  function persistScopeIfPresent() {
    try {
      const url = new URL(window.location.href);
      const scope = (url.searchParams.get('vendor_scope') || '').trim().toLowerCase();
      if (scope === 'all') {
        try { localStorage.setItem('vendorSelection.scope', 'all'); } catch (_) {}
      } else {
        // Se houver vendor_ids explícitos na URL, persistir 'selected'
        const hasIds = !!(url.searchParams.get('vendor_ids') || '');
        if (hasIds) {
          try { localStorage.setItem('vendorSelection.scope', 'selected'); } catch (_) {}
        }
      }
    } catch (_) { /* ignore */ }
  }

  function parseIdsFromUrl() {
    try {
      const url = new URL(window.location.href);
      const raw = url.searchParams.get('vendor_ids') || '';
      if (!raw) return [];
      return raw
        .split(',')
        .map((x) => parseInt(x, 10))
        .filter((n) => Number.isFinite(n));
    } catch (e) {
      return [];
    }
  }

  function parseIdsFromLocalStorage() {
    try {
      const raw = localStorage.getItem('vendorSelection.selectedVendorIds');
      if (!raw) return [];
      const arr = JSON.parse(raw);
      if (!Array.isArray(arr)) return [];
      return arr
        .map((x) => parseInt(x, 10))
        .filter((n) => Number.isFinite(n));
    } catch (e) {
      return [];
    }
  }

  function getEffectiveVendorIds() {
    // Em escopo global, não propagar vendor_ids
    if (getVendorScope() === 'all') return [];
    const byUrl = parseIdsFromUrl();
    if (byUrl.length) return byUrl;
    return parseIdsFromLocalStorage();
  }

  function shouldSkipAnchor(a) {
    const href = a.getAttribute('href') || '';
    if (!href) return true;
    if (href.startsWith('#')) return true;
    if (href.startsWith('javascript:')) return true;
    if (a.hasAttribute('download')) return true;
    // External links
    try {
      const url = new URL(href, window.location.origin);
      if (url.origin !== window.location.origin) return true;
      // Evitar reescrever links que apontam para a raiz
      if (url.pathname === '/') return true;
      // Skip static assets
      if (url.pathname.startsWith('/static')) return true;
      return false;
    } catch (e) {
      return true;
    }
  }

  function appendVendorIdsToUrl(href, ids) {
    if (!ids || !ids.length) return href;
    try {
      const url = new URL(href, window.location.origin);
      // Preserve existing vendor_ids but ensure they match effective ids
      url.searchParams.set('vendor_ids', ids.join(','));
      // Em caso de escopo global presente, limpar para evitar conflito
      if ((url.searchParams.get('vendor_scope') || '').toLowerCase() === 'all') {
        url.searchParams.delete('vendor_scope');
      }
      return url.toString();
    } catch (e) {
      return href;
    }
  }

  function appendGlobalScopeToUrl(href) {
    try {
      const url = new URL(href, window.location.origin);
      url.searchParams.set('vendor_scope', 'all');
      // Remover qualquer vendor_ids para manter consistência com escopo global
      url.searchParams.delete('vendor_ids');
      return url.toString();
    } catch (_) {
      return href;
    }
  }

  function propagateToAnchors(rootSelector) {
    const scope = getVendorScope();
    const ids = getEffectiveVendorIds();
    const root = document.querySelector(rootSelector);
    if (!root) return;
    const anchors = Array.from(root.querySelectorAll('a[href]'));
    anchors.forEach((a) => {
      if (shouldSkipAnchor(a)) return;
      const href = a.getAttribute('href');
      const updated = scope === 'all' ? appendGlobalScopeToUrl(href) : appendVendorIdsToUrl(href, ids);
      a.setAttribute('href', updated);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    try { if ((location && location.pathname || '').indexOf('/auth/init-root') === 0) { return; } } catch(_) {}
    persistScopeIfPresent();
    propagateToAnchors('header.navbar');
    propagateToAnchors('#sidebar');
    propagateToAnchors('body');
    try {
      const ids = getEffectiveVendorIds();
      if (ids && ids.length) {
        const url = '/api/v1/account/vendor-preferences';
        const payload = { vendor_ids: ids };
        const opts = {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify(payload),
          keepalive: true
        };
        setTimeout(function(){
          try {
            if ((document && document.body && document.body.getAttribute('data-page') || '') === 'init-root') { return; }
            fetch(url, opts).catch(function(){})
          } catch(_){}
        }, 150);
      }
    } catch(_) {}
  });
})();
