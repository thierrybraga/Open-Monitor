(function () {
  'use strict';

  // Safe console
  var safeConsole = (function () {
    if (typeof window !== 'undefined' && window.console) return window.console;
    return { log: function () {}, error: function () {} };
  })();

  // Helper: find closest anchor element
  function closestAnchor(el) {
    while (el && el.nodeType === 1) {
      if (el.tagName && el.tagName.toUpperCase() === 'A') return el;
      el = el.parentElement;
    }
    return null;
  }

  // Simple thenable/Promise fallback creator
  function createThenable(duration, setupFn) {
    try { if (typeof setupFn === 'function') setupFn(); } catch (e) {}
    if (window.Promise) {
      return new Promise(function (resolve) { setTimeout(resolve, duration); });
    }
    return {
      then: function (resolve) { setTimeout(function () { if (typeof resolve === 'function') resolve(); }, duration); }
    };
  }

  // Constructor
  function PageTransitionManager() {
    this.isTransitioning = false;
    this.progressBar = null;
    this.loadingOverlay = null;
    this.init();
  }

  PageTransitionManager.prototype.init = function () {
    this.createProgressBar();
    this.createLoadingOverlay();
    this.setupEventListeners();
    this.addPageFadeIn();
  };

  PageTransitionManager.prototype.createProgressBar = function () {
    var bar = document.createElement('div');
    bar.className = 'page-progress-bar';
    document.body.appendChild(bar);
    this.progressBar = bar;
  };

  PageTransitionManager.prototype.createLoadingOverlay = function () {
    var overlay = document.createElement('div');
    overlay.className = 'page-loading-overlay';
    overlay.innerHTML = '<div class="page-loading-spinner"></div>';
    document.body.appendChild(overlay);
    this.loadingOverlay = overlay;
  };

  PageTransitionManager.prototype.setupEventListeners = function () {
    var self = this;

    // Intercept internal link clicks
    document.addEventListener('click', function (e) {
      var link = closestAnchor(e.target || e.srcElement);
      if (self.shouldInterceptLink(link)) {
        if (e.preventDefault) e.preventDefault(); else e.returnValue = false;
        self.navigateWithTransition(link.href);
      }
    });

    // Intercept form submissions (POST)
    document.addEventListener('submit', function (e) {
      var form = e.target || e.srcElement;
      if (self.shouldInterceptForm(form)) {
        self.showLoadingState();
      }
    });

    // Page load
    window.addEventListener('load', function () {
      self.hideLoadingState();
    });

    // Browser navigation (back/forward)
    window.addEventListener('popstate', function () {
      self.showLoadingState();
      setTimeout(function () { self.hideLoadingState(); }, 300);
    });
  };

  PageTransitionManager.prototype.shouldInterceptLink = function (link) {
    if (!link || this.isTransitioning) return false;

    // Disabled explicitly
    if (link.getAttribute('data-no-transition')) return false;
    if (link.classList && link.classList.contains('no-transition')) return false;

    // New tab
    var target = link.getAttribute('target');
    if (target && target.toLowerCase() === '_blank') return false;

    var href = link.getAttribute('href');
    if (!href || href.indexOf('#') === 0 || href.indexOf('mailto:') === 0 || href.indexOf('tel:') === 0) return false;

    // Internal link check
    try {
      var url = new URL(href, window.location.origin);
      return url.origin === window.location.origin;
    } catch (e) {
      return false;
    }
  };

  PageTransitionManager.prototype.shouldInterceptForm = function (form) {
    return !!(form && form.method && String(form.method).toLowerCase() === 'post');
  };

  PageTransitionManager.prototype.navigateWithTransition = function (url) {
    if (this.isTransitioning) return;
    this.isTransitioning = true;

    try {
      this.showLoadingState();
      setTimeout(function () {
        window.location.href = url;
      }, 200);
    } catch (error) {
      safeConsole.error('Erro na transição:', error);
      this.hideLoadingState();
      this.isTransitioning = false;
    }
  };

  PageTransitionManager.prototype.showLoadingState = function () {
    if (!this.progressBar) return;
    this.progressBar.style.width = '30%';
    if (this.progressBar.classList) this.progressBar.classList.add('loading');
    setTimeout(function () { this.progressBar.style.width = '70%'; }.bind(this), 200);

    var contentWrapper = document.querySelector('.main-content, .content-wrapper, main');
    if (contentWrapper && contentWrapper.classList) {
      contentWrapper.classList.add('content-fade-out');
    }
  };

  PageTransitionManager.prototype.hideLoadingState = function () {
    if (!this.progressBar) return;
    this.progressBar.style.width = '100%';
    var self = this;
    setTimeout(function () {
      self.progressBar.style.width = '0%';
      if (self.progressBar.classList) self.progressBar.classList.remove('loading');
    }, 300);

    var contentWrapper = document.querySelector('.main-content, .content-wrapper, main');
    if (contentWrapper && contentWrapper.classList) {
      contentWrapper.classList.remove('content-fade-out');
    }

    if (this.loadingOverlay && this.loadingOverlay.classList) {
      this.loadingOverlay.classList.remove('active');
    }
    this.isTransitioning = false;
  };

  PageTransitionManager.prototype.addPageFadeIn = function () {
    var mainContent = document.querySelector('.main-content, .content-wrapper, main');
    if (mainContent && mainContent.classList) {
      mainContent.classList.add('page-fade-in');
    }
  };

  PageTransitionManager.prototype.showCustomLoading = function (message) {
    if (!this.loadingOverlay) return;
    if (this.loadingOverlay.classList) this.loadingOverlay.classList.add('active');
    if (message) {
      var spinner = this.loadingOverlay.querySelector('.page-loading-spinner');
      if (spinner && spinner.insertAdjacentHTML) {
        spinner.insertAdjacentHTML('afterend', '<p class="mt-3 text-muted">' + message + '</p>');
      }
    }
  };

  PageTransitionManager.prototype.hideCustomLoading = function () {
    if (!this.loadingOverlay) return;
    if (this.loadingOverlay.classList) this.loadingOverlay.classList.remove('active');
    var msg = this.loadingOverlay.querySelector('p');
    if (msg && msg.parentNode) { msg.parentNode.removeChild(msg); }
  };

  // Transition utilities
  var TransitionUtils = {
    fadeOut: function (element, duration) {
      duration = typeof duration === 'number' ? duration : 300;
      return createThenable(duration, function () {
        try {
          element.style.transition = 'opacity ' + duration + 'ms ease';
          element.style.opacity = '0';
        } catch (e) {}
      });
    },
    fadeIn: function (element, duration) {
      duration = typeof duration === 'number' ? duration : 300;
      return createThenable(duration, function () {
        try {
          element.style.transition = 'opacity ' + duration + 'ms ease';
          element.style.opacity = '1';
        } catch (e) {}
      });
    },
    slideUp: function (element, duration) {
      duration = typeof duration === 'number' ? duration : 300;
      return createThenable(duration, function () {
        try {
          element.style.transition = 'transform ' + duration + 'ms ease, opacity ' + duration + 'ms ease';
          element.style.transform = 'translateY(-20px)';
          element.style.opacity = '0';
        } catch (e) {}
      });
    },
    slideDown: function (element, duration) {
      duration = typeof duration === 'number' ? duration : 300;
      return createThenable(duration, function () {
        try {
          element.style.transition = 'transform ' + duration + 'ms ease, opacity ' + duration + 'ms ease';
          element.style.transform = 'translateY(0)';
          element.style.opacity = '1';
        } catch (e) {}
      });
    }
  };

  // Initialize when DOM is ready
  document.addEventListener('DOMContentLoaded', function () {
    var prefersReducedMotion = false;
    try {
      if (window.matchMedia) {
        prefersReducedMotion = !!window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      }
    } catch (e) {}

    if (!prefersReducedMotion) {
      window.pageTransitionManager = new PageTransitionManager();
    }

    // Expose utils
    window.TransitionUtils = TransitionUtils;
  });

  // CommonJS export (noop in browser)
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { PageTransitionManager: PageTransitionManager, TransitionUtils: TransitionUtils };
  }
})();