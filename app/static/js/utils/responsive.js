(function () {
  'use strict';

  // ==========================================================================
  // Variáveis e Configurações
  // ==========================================================================

  var BREAKPOINTS = {
    xs: 320,
    sm: 576,
    md: 768,
    lg: 992,
    xl: 1200,
    xxl: 1400
  };

  var currentBreakpoint = getCurrentBreakpoint();
  var resizeTimeout;

  // ==========================================================================
  // Utilitários
  // ==========================================================================

  function getCurrentBreakpoint() {
    var width = window.innerWidth || document.documentElement.clientWidth || document.body.clientWidth;
    if (width < BREAKPOINTS.sm) return 'xs';
    if (width < BREAKPOINTS.md) return 'sm';
    if (width < BREAKPOINTS.lg) return 'md';
    if (width < BREAKPOINTS.xl) return 'lg';
    if (width < BREAKPOINTS.xxl) return 'xl';
    return 'xxl';
  }

  function isMobile() {
    return (window.innerWidth || document.documentElement.clientWidth || document.body.clientWidth) < BREAKPOINTS.md;
  }

  function isTablet() {
    var w = window.innerWidth || document.documentElement.clientWidth || document.body.clientWidth;
    return w >= BREAKPOINTS.md && w < BREAKPOINTS.lg;
  }

  function debounce(func, wait, key) {
    if (typeof key === 'undefined') key = 'responsive-default';
    return (window.Utils && Utils.debounce) ? Utils.debounce(func, wait, key) : (function () {
      var timeout;
      return function () {
        var context = this, args = arguments;
        clearTimeout(timeout);
        timeout = setTimeout(function () { func.apply(context, args); }, wait);
      };
    })();
  }

  // ==========================================================================
  // Gerenciamento de Tabelas Responsivas
  // ==========================================================================

  function initResponsiveTables() {
    var tables = document.querySelectorAll('table');
    Array.prototype.forEach.call(tables, function (table) {
      if (!closest(table, '.table-responsive')) {
        var wrapper = document.createElement('div');
        wrapper.className = 'table-responsive';
        if (table.parentNode) {
          table.parentNode.insertBefore(wrapper, table);
          wrapper.appendChild(table);
        }
      }
      addMobileTableClasses(table);
    });
  }

  function addMobileTableClasses(table) {
    var headers = table.querySelectorAll('th');
    var rows = table.querySelectorAll('tbody tr');

    var lessImportantColumns = [];
    Array.prototype.forEach.call(headers, function (header, index) {
      var text = (header.textContent || '').toLowerCase();
      if (text.indexOf('data') !== -1 || text.indexOf('criado') !== -1 || text.indexOf('atualizado') !== -1 ||
          text.indexOf('detalhes') !== -1 || text.indexOf('observações') !== -1) {
        lessImportantColumns.push(index);
      }
    });

    Array.prototype.forEach.call(lessImportantColumns, function (colIndex) {
      if (headers[colIndex]) {
        headers[colIndex].classList.add('d-none-mobile');
      }
      Array.prototype.forEach.call(rows, function (row) {
        var cell = row.children[colIndex];
        if (cell) { cell.classList.add('d-none-mobile'); }
      });
    });
  }

  // ==========================================================================
  // Otimizações de Performance
  // ==========================================================================

  function optimizeAnimations() {
    var mql;
    try { if (window.matchMedia) mql = window.matchMedia('(prefers-reduced-motion: reduce)'); } catch (e) {}
    if (!mql) return;

    function handleMotionPreference(e) {
      var prefersReduced = !!(e && e.matches);
      if (prefersReduced) {
        document.documentElement.style.setProperty('--animation-duration-fast', '0.1s');
        document.documentElement.style.setProperty('--animation-duration-normal', '0.15s');
        document.documentElement.style.setProperty('--animation-duration-slow', '0.2s');
      } else {
        document.documentElement.style.removeProperty('--animation-duration-fast');
        document.documentElement.style.removeProperty('--animation-duration-normal');
        document.documentElement.style.removeProperty('--animation-duration-slow');
      }
    }

    if (typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', handleMotionPreference);
    } else if (typeof mql.addListener === 'function') {
      mql.addListener(handleMotionPreference);
    }
    handleMotionPreference(mql);
  }

  function optimizeImages() {
    if (!isMobile()) return;
    var images = document.querySelectorAll('img[data-mobile-src]');
    Array.prototype.forEach.call(images, function (img) {
      var mobileSrc = img.getAttribute('data-mobile-src');
      if (mobileSrc) { img.src = mobileSrc; }
    });
  }

  // ==========================================================================
  // Gerenciamento de Orientação
  // ==========================================================================

  function handleOrientationChange() {
    setTimeout(function () {
      try {
        if (typeof window.adjustSidebarForScreenSize === 'function') { window.adjustSidebarForScreenSize(); }
      } catch (e) {}
      initResponsiveTables();

      var angle = 0;
      try { angle = (screen.orientation && screen.orientation.angle) ? screen.orientation.angle : 0; } catch (e) {}

      var evt;
      try {
        evt = new CustomEvent('orientationChanged', { detail: { orientation: angle } });
      } catch (e) {
        evt = document.createEvent('CustomEvent');
        evt.initCustomEvent('orientationChanged', true, true, { orientation: angle });
      }
      window.dispatchEvent(evt);
    }, 100);
  }

  // ==========================================================================
  // Event Listeners e Inicialização
  // ==========================================================================

  var handleResize = debounce(function () {
    var newBreakpoint = getCurrentBreakpoint();
    if (newBreakpoint !== currentBreakpoint) {
      currentBreakpoint = newBreakpoint;
      try {
        if (typeof window.adjustSidebarForScreenSize === 'function') { window.adjustSidebarForScreenSize(); }
      } catch (e) {}
      optimizeImages();

      var evt;
      try {
        evt = new CustomEvent('breakpointChanged', { detail: { breakpoint: newBreakpoint } });
      } catch (e) {
        evt = document.createEvent('CustomEvent');
        evt.initCustomEvent('breakpointChanged', true, true, { breakpoint: newBreakpoint });
      }
      window.dispatchEvent(evt);
    }
  }, 250, 'responsive-resize');

  function init() {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init);
      return;
    }

    initResponsiveTables();
    optimizeAnimations();
    optimizeImages();

    window.addEventListener('resize', handleResize);
    window.addEventListener('orientationchange', handleOrientationChange);

    document.documentElement.setAttribute('data-responsive-initialized', 'true');

    try { if (window.console && console.log) console.log('Sistema de responsividade inicializado'); } catch (e) {}
  }

  // ==========================================================================
  // API Pública
  // ==========================================================================

  window.ResponsiveManager = {
    isMobile: isMobile,
    isTablet: isTablet,
    getCurrentBreakpoint: getCurrentBreakpoint
  };

  init();

  // Helper: closest selector (limited)
  function closest(el, selector) {
    while (el && el.nodeType === 1) {
      if (matchesSelector(el, selector)) return el;
      el = el.parentElement;
    }
    return null;
  }

  function matchesSelector(el, selector) {
    var p = Element.prototype;
    var f = p.matches || p.msMatchesSelector || p.webkitMatchesSelector;
    if (!f) return false;
    try { return f.call(el, selector); } catch (e) { return false; }
  }

})();