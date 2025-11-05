// vendor_scope.js
// Propaga automaticamente vendor_ids em links de navegação (navbar, sidebar)
// e em outros links internos relevantes.

(function () {
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
      return url.toString();
    } catch (e) {
      return href;
    }
  }

  function propagateToAnchors(rootSelector) {
    const ids = getEffectiveVendorIds();
    const root = document.querySelector(rootSelector);
    if (!root) return;
    const anchors = Array.from(root.querySelectorAll('a[href]'));
    anchors.forEach((a) => {
      if (shouldSkipAnchor(a)) return;
      const href = a.getAttribute('href');
      const updated = appendVendorIdsToUrl(href, ids);
      a.setAttribute('href', updated);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    // Navbar and Sidebar
    propagateToAnchors('header.navbar');
    propagateToAnchors('#sidebar');
  });
})();