/**
 * Pagination System (ES5 Compatible)
 * - Handles pagination controls, per-page selection, and smooth transitions
 * - Graceful fallbacks for older browsers (no async/await, no classes, no arrow functions)
 */
(function() {
  'use strict';

  function assign(target) {
    for (var i = 1; i < arguments.length; i++) {
      var source = arguments[i] || {};
      for (var key in source) {
        if (Object.prototype.hasOwnProperty.call(source, key)) {
          target[key] = source[key];
        }
      }
    }
    return target;
  }

  function matchesSelector(el, selector) {
    if (!el || !selector) return false;
    var p = Element.prototype;
    var f = p.matches || p.msMatchesSelector || p.webkitMatchesSelector;
    if (!f) return false;
    try { return f.call(el, selector); } catch (_) { return false; }
  }

  function closest(el, selector) {
    while (el && el.nodeType === 1) {
      if (matchesSelector(el, selector)) return el;
      el = el.parentElement;
    }
    return null;
  }

  function updateQueryParam(url, key, value) {
    try {
      var u = new URL(url, window.location.origin);
      u.searchParams.set(key, value);
      return u.toString();
    } catch (e) {
      var re = new RegExp('([?&])' + key + '=[^&]*');
      var sep = url.indexOf('?') !== -1 ? '&' : '?';
      if (re.test(url)) {
        return url.replace(re, '$1' + key + '=' + encodeURIComponent(value));
      }
      return url + sep + key + '=' + encodeURIComponent(value);
    }
  }

  function removeQueryParam(url, key) {
    try {
      var u = new URL(url, window.location.origin);
      u.searchParams.delete(key);
      return u.toString();
    } catch (e) {
      var re = new RegExp('([?&])' + key + '=[^&]*');
      var newUrl = url.replace(re, function(match, p1) {
        return p1 === '?' ? '?' : '';
      });
      // Clean trailing separators
      newUrl = newUrl.replace(/[?&]$/, '');
      return newUrl;
    }
  }

  function ModernPagination(options) {
    this.options = assign({
      containerSelector: '.pagination-section',
      tableSelector: '.vulnerabilities-table, .recent-vulnerabilities-table',
      loadingClass: 'pagination-loading',
      animationDuration: 300
    }, options || {});

    this.init();
  }

  ModernPagination.prototype.init = function() {
    this.bindEvents();
    this.setupLoadingStates();
  };

  ModernPagination.prototype.bindEvents = function() {
    var self = this;

    // Per-page select handler (skip if VulnerabilitiesPage manages it)
    document.addEventListener('change', function(e) {
      if (window.VulnerabilitiesPage) return;
      var t = e.target || e.srcElement;
      if (t && t.id === 'per-page-select') {
        self.changePerPage(t.value);
      }
    });

    // Pagination clicks with AJAX (skip if VulnerabilitiesPage manages it)
    document.addEventListener('click', function(e) {
      if (window.VulnerabilitiesPage) return;
      var t = e.target || e.srcElement;
      var pageLink = closest(t, '.page-link:not(.disabled)');
      if (pageLink && !matchesSelector(pageLink, '.disabled')) {
        var href = pageLink.getAttribute('href');
        if (href && href !== '#') {
          e.preventDefault ? e.preventDefault() : (e.returnValue = false);
          self.loadPage(href);
        }
      }
    });

    // Keyboard navigation (skip if VulnerabilitiesPage manages it)
    document.addEventListener('keydown', function(e) {
      if (window.VulnerabilitiesPage) return;
      var t = e.target || e.srcElement;
      if (closest(t, '.pagination-modern, .pagination-min')) {
        self.handleKeyboardNavigation(e);
      }
    });
  };

  ModernPagination.prototype.setupLoadingStates = function() {
    var style = document.createElement('style');
    style.type = 'text/css';
    style.textContent =
      '.pagination-loading{opacity:.6;pointer-events:none;position:relative}' +
      '.pagination-loading::after{content:"";position:absolute;top:50%;left:50%;width:20px;height:20px;margin:-10px 0 0 -10px;border:2px solid var(--primary-color);border-top:2px solid transparent;border-radius:50%;animation:pagination-spin 1s linear infinite;z-index:1000}' +
      '@keyframes pagination-spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}' +
      '.table-fade-in{animation:fadeIn .3s ease-in-out}' +
      '@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}';
    document.head.appendChild(style);
  };

  ModernPagination.prototype.changePerPage = function(perPage) {
    var currentUrl;
    try {
      currentUrl = new URL(window.location.href);
      currentUrl.searchParams.set('per_page', perPage);
      currentUrl.searchParams.delete('page');
      this.loadPage(currentUrl.toString());
    } catch (e) {
      var url = updateQueryParam(window.location.href, 'per_page', perPage);
      url = removeQueryParam(url, 'page');
      window.location.href = url;
    }
  };

  ModernPagination.prototype.loadPage = function(url, options) {
    options = options || {};
    var skipPush = options.skipPush === true;
    var self = this;

    self.showLoading();

    if (window.fetch) {
      // AJAX fetch
      window.fetch(url, {
        headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'text/html' }
      }).then(function(response) {
        if (!response || !response.ok) {
          throw new Error('HTTP error! status: ' + (response ? response.status : 'unknown'));
        }
        return response.text();
      }).then(function(html) {
        self.updateContent(html);
        if (!skipPush && window.history && window.history.pushState) {
          window.history.pushState({}, '', url);
        }
        self.scrollToTable();
      }).catch(function(error) {
        if (window.console && console.error) console.error('Error loading page:', error);
        self.showError('Erro ao carregar a página. Tente novamente.');
      }).finally ? window.Promise && Promise.resolve().then(function(){ self.hideLoading(); }) : self.hideLoading();
    } else {
      // Fallback to full reload
      window.location.href = url;
    }
  };

  ModernPagination.prototype.updateContent = function(html) {
    try {
      var parser = new DOMParser();
      var doc = parser.parseFromString(html, 'text/html');

      // Update table content
      var newTable = doc.querySelector(this.options.tableSelector);
      var currentTable = document.querySelector(this.options.tableSelector);

      if (newTable && currentTable) {
        currentTable.style.opacity = '0';
        setTimeout(function() {
          currentTable.innerHTML = newTable.innerHTML;
          currentTable.style.opacity = '1';
          currentTable.classList.add('table-fade-in');
          setTimeout(function() {
            currentTable.classList.remove('table-fade-in');
          }, this.options.animationDuration);
        }.bind(this), 150);
      }

      // Update pagination controls
      var newPagination = doc.querySelector(this.options.containerSelector);
      var currentPagination = document.querySelector(this.options.containerSelector);
      if (newPagination && currentPagination) {
        var newControls = newPagination.querySelector('.pagination-nav') || newPagination;
        var currentControls = currentPagination.querySelector('.pagination-nav') || currentPagination;
        if (newControls && currentControls) {
          currentControls.innerHTML = newControls.innerHTML;
        }
      }

      // Update results counter if exists
      this.updateResultsCounter(doc);

      // Re-initialize any table-specific functionality
      this.reinitializeTableFeatures();
    } catch (e) {
      if (window.console && console.error) console.error('updateContent error:', e);
    }
  };

  ModernPagination.prototype.updateResultsCounter = function(doc) {
    var newCounter = doc.querySelector('.results-counter');
    var currentCounter = document.querySelector('.results-counter');
    if (newCounter && currentCounter) {
      currentCounter.textContent = newCounter.textContent;
    }
  };

  ModernPagination.prototype.reinitializeTableFeatures = function() {
    try {
      if (window.initializeTableSorting) { window.initializeTableSorting(); }
      if (window.initializeTableFiltering) { window.initializeTableFiltering(); }
      var evt;
      try {
        evt = new CustomEvent('paginationUpdated', { detail: { timestamp: Date.now() } });
      } catch (e) {
        evt = document.createEvent('CustomEvent');
        evt.initCustomEvent('paginationUpdated', true, true, { timestamp: Date.now() });
      }
      document.dispatchEvent(evt);
    } catch (e) {
      // Silent fail
    }
  };

  ModernPagination.prototype.showLoading = function() {
    var container = document.querySelector(this.options.containerSelector);
    if (container) { container.classList.add(this.options.loadingClass); }
    var table = document.querySelector(this.options.tableSelector);
    if (table) { table.style.opacity = '0.5'; }
  };

  ModernPagination.prototype.hideLoading = function() {
    var container = document.querySelector(this.options.containerSelector);
    if (container) { container.classList.remove(this.options.loadingClass); }
    var table = document.querySelector(this.options.tableSelector);
    if (table) { table.style.opacity = '1'; }
  };

  ModernPagination.prototype.showError = function(message) {
    var errorDiv = document.querySelector('.pagination-error');
    if (!errorDiv) {
      errorDiv = document.createElement('div');
      errorDiv.className = 'pagination-error alert alert-danger mt-3';
      errorDiv.style.display = 'none';
      var container = document.querySelector(this.options.containerSelector);
      if (container) { container.appendChild(errorDiv); }
    }
    errorDiv.innerHTML = '<i class="bi bi-exclamation-triangle me-2"></i>' + message + '<button type="button" class="btn-close" onclick="this.parentElement.style.display=\'none\'"></button>';
    errorDiv.style.display = 'block';
    setTimeout(function() { if (errorDiv) { errorDiv.style.display = 'none'; } }, 5000);
  };

  ModernPagination.prototype.scrollToTable = function() {
    var table = document.querySelector(this.options.tableSelector);
    if (table) {
      var offset = 100; // Offset for fixed headers
      var elementPosition = table.offsetTop;
      var offsetPosition = elementPosition - offset;
      try {
        window.scrollTo({ top: offsetPosition, behavior: 'smooth' });
      } catch (e) {
        window.scrollTo(0, offsetPosition);
      }
    }
  };

  ModernPagination.prototype.handleKeyboardNavigation = function(e) {
    var pagination = closest(e.target || e.srcElement, '.pagination-modern, .pagination-min');
    if (!pagination) return;
    var links = pagination.querySelectorAll('.page-link:not(.disabled), .page-link-prev:not(.disabled), .page-link-next:not(.disabled)');
    var linksArr = Array.prototype.slice.call(links);
    var currentIndex = linksArr.indexOf(e.target || e.srcElement);
    var targetIndex = -1;
    var key = e.key || e.keyCode;
    switch (key) {
      case 'ArrowLeft':
      case 37:
        targetIndex = Math.max(0, currentIndex - 1);
        break;
      case 'ArrowRight':
      case 39:
        targetIndex = Math.min(links.length - 1, currentIndex + 1);
        break;
      case 'Home':
        targetIndex = 0;
        break;
      case 'End':
        targetIndex = links.length - 1;
        break;
      case 'Enter':
      case ' ':
      case 13:
      case 32:
        if (e.preventDefault) e.preventDefault();
        (e.target || e.srcElement).click();
        return;
    }
    if (targetIndex >= 0 && targetIndex < links.length) {
      if (e.preventDefault) e.preventDefault();
      links[targetIndex].focus();
    }
  };

  // Backward-compatible global function
  window.changePerPage = function(perPage) {
    if (window.modernPagination) {
      window.modernPagination.changePerPage(perPage);
    } else {
      // Fallback to page reload
      var url;
      try {
        var u = new URL(window.location.href);
        u.searchParams.set('per_page', perPage);
        u.searchParams.delete('page');
        url = u.toString();
      } catch (e) {
        url = updateQueryParam(window.location.href, 'per_page', perPage);
        url = removeQueryParam(url, 'page');
      }
      window.location.href = url;
    }
  };

  // Initialize when DOM is ready
  document.addEventListener('DOMContentLoaded', function() {
    try {
      window.modernPagination = new ModernPagination();
    } catch (e) {
      if (window.console && console.error) console.error('Pagination init error:', e);
    }
  });

  // Handle browser back/forward buttons with AJAX update
  window.addEventListener('popstate', function() {
    if (window.modernPagination) {
      try {
        window.modernPagination.loadPage(window.location.href, { skipPush: true });
      } catch (e) {
        window.location.href = window.location.href;
      }
    } else {
      window.location.href = window.location.href;
    }
  });
})();