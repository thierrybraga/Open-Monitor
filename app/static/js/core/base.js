'use strict';

/**
 * Base.js (ES5 Compat) - Core JavaScript for the Open CVE Report base layout
 * - Remove let/const, arrow functions, spread, template strings
 * - Keep behavior identical, add basic fallbacks
 */
(function() {
  // =========================================================================
  // 1. Element Selection
  // =========================================================================
  var htmlEl, bodyEl, sidebarToggle, sidebar, mainContent, navbar, footer, sidebarScrim,
      sidebarLinks, dropdownToggles, systemAlertsContainer;

  function selectElements() {
    htmlEl = document.documentElement;
    bodyEl = document.body;
    sidebarToggle = document.getElementById('sidebarToggle');
    sidebar = document.getElementById('sidebar');
    mainContent = document.getElementById('main-content');
    navbar = document.querySelector('header.navbar');
    footer = document.querySelector('footer.footer');
    sidebarScrim = document.querySelector('.sidebar-scrim');
    sidebarLinks = document.querySelectorAll('.sidebar-nav .sidebar-link');
    dropdownToggles = document.querySelectorAll('[data-bs-toggle="dropdown"]');
    systemAlertsContainer = document.getElementById('system-alerts');
  }

  // =========================================================================
  // 2. Basic Checks
  // =========================================================================
  function checkRequiredElements() {
    var criticalElements = [
      { el: htmlEl, name: 'html element' },
      { el: bodyEl, name: 'body element' },
      { el: sidebarToggle, name: 'sidebarToggle button' },
      { el: sidebar, name: 'sidebar element' },
      { el: mainContent, name: 'main content element' },
      { el: navbar, name: 'navbar element' },
      { el: footer, name: 'footer element' }
    ];

    var optionalElements = [
      { el: sidebarScrim, name: 'sidebar scrim' },
      { el: systemAlertsContainer, name: 'system alerts container' }
    ];

    var allFound = true;
    Array.prototype.forEach.call(criticalElements, function(item) {
      if (!item.el) {
        try { console.warn('Open CVE Report Base JS Warning: Required element "' + item.name + '" not found.'); } catch(_){}
        allFound = false;
      }
    });

    Array.prototype.forEach.call(optionalElements, function(item) {
      if (!item.el) {
        try { console.debug('Open CVE Report Base JS Debug: Optional element "' + item.name + '" not found.'); } catch(_){}
      }
    });

    return allFound;
  }

  // =========================================================================
  // 5. Accessibility Enhancements
  // =========================================================================
  function initializeAccessibility() {
    var skipLink = document.createElement('a');
    skipLink.href = '#main-content';
    skipLink.className = 'skip-link';
    skipLink.textContent = 'Skip to main content';
    // Inline style (avoid template literals)
    skipLink.style.position = 'absolute';
    skipLink.style.top = '-40px';
    skipLink.style.left = '6px';
    skipLink.style.background = 'var(--bs-primary)';
    skipLink.style.color = 'white';
    skipLink.style.padding = '8px';
    skipLink.style.textDecoration = 'none';
    skipLink.style.borderRadius = '4px';
    skipLink.style.zIndex = '1000';
    skipLink.style.transition = 'top 0.3s';

    skipLink.addEventListener('focus', function() {
      this.style.top = '6px';
    });

    skipLink.addEventListener('blur', function() {
      this.style.top = '-40px';
    });

    document.body.insertBefore(skipLink, document.body.firstChild);

    document.addEventListener('keydown', function(e) {
      var key = e.key || e.keyCode;
      if (key === 'Escape' || key === 27) {
        var activeModal = document.querySelector('.modal.show');
        if (activeModal) {
          var modalInstance = (window.bootstrap && bootstrap.Modal) ? bootstrap.Modal.getInstance(activeModal) : null;
          if (modalInstance) {
            modalInstance.hide();
          }
        }
      }
    });

    try { console.log('Accessibility Enhancements Initialized'); } catch(_){}
  }

  // =========================================================================
  // 5.1 Safe Bootstrap helpers
  // =========================================================================
  function getModalInstance(el, options) {
    if (!el) return null;
    try {
      if (typeof window.bootstrap !== 'undefined' && bootstrap.Modal) {
        return bootstrap.Modal.getInstance(el) || new bootstrap.Modal(el, options);
      }
    } catch (e) {
      try { console.warn('Bootstrap Modal init failed:', e); } catch(_){}
    }
    return {
      show: function() {
        el.classList.add('show');
        el.style.display = 'block';
        document.body.classList.add('modal-open');
      },
      hide: function() {
        el.classList.remove('show');
        el.style.display = 'none';
        document.body.classList.remove('modal-open');
        var backdrops = document.querySelectorAll('.modal-backdrop');
        Array.prototype.forEach.call(backdrops, function(b) {
          if (b && b.parentNode) { b.parentNode.removeChild(b); }
        });
      }
    };
  }

  function getToastInstance(el, options) {
    if (!el) return null;
    try {
      if (typeof window.bootstrap !== 'undefined' && bootstrap.Toast) {
        return bootstrap.Toast.getInstance(el) || new bootstrap.Toast(el, options);
      }
    } catch (e) {
      try { console.warn('Bootstrap Toast init failed:', e); } catch(_){}
    }
    return {
      show: function() {
        el.classList.add('show');
        el.style.display = 'block';
      },
      hide: function() {
        el.classList.remove('show');
        el.style.display = 'none';
      }
    };
  }

  window.getModalInstance = getModalInstance;
  window.getToastInstance = getToastInstance;

  // =========================================================================
  // 6. Bootstrap Components Initialization
  // =========================================================================
  function initializeTooltips() {
    var tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    if (tooltipTriggerList.length > 0 && typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
      var tooltipList = Array.prototype.slice.call(tooltipTriggerList).map(function(tooltipTriggerEl) {
        try { return new bootstrap.Tooltip(tooltipTriggerEl); } catch(e){ return null; }
      });
      try { console.log('Initialized ' + tooltipList.length + ' tooltips'); } catch(_){}
    } else if (tooltipTriggerList.length > 0) {
      try { console.warn('Bootstrap Tooltip component not available, but tooltip elements found.'); } catch(_){}
    }
  }

  function setupDynamicTooltipObserver() {
    if (typeof MutationObserver === 'undefined' || typeof bootstrap === 'undefined' || !bootstrap.Tooltip) {
      return;
    }
    var observer = new MutationObserver(function(mutations) {
      for (var i = 0; i < mutations.length; i++) {
        var mutation = mutations[i];
        if (mutation.type === 'childList' && mutation.addedNodes && mutation.addedNodes.length) {
          Array.prototype.forEach.call(mutation.addedNodes, function(node) {
            if (!(node instanceof HTMLElement)) return;
            var candidates = (node.matches && node.matches('[data-bs-toggle="tooltip"]'))
              ? [node]
              : node.querySelectorAll('[data-bs-toggle="tooltip"]');
            Array.prototype.forEach.call(candidates, function(el) {
              if (!bootstrap.Tooltip.getInstance(el)) {
                try { new bootstrap.Tooltip(el); } catch (e) {
                  try { console.warn('Failed to initialize tooltip for element', el, e); } catch(_){}
                }
              }
            });
          });
        }
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function initializeDropdowns() {
    if (dropdownToggles && dropdownToggles.length > 0 && typeof bootstrap !== 'undefined' && bootstrap.Dropdown) {
      Array.prototype.forEach.call(dropdownToggles, function(toggle) {
        try { new bootstrap.Dropdown(toggle); } catch(_){}
      });
      try { console.log('Initialized ' + dropdownToggles.length + ' dropdowns'); } catch(_){}
    } else if (dropdownToggles && dropdownToggles.length > 0) {
      try { console.warn('Bootstrap Dropdown component not available, but dropdown elements found.'); } catch(_){}
    }
  }

  function initializeAlertSystem() {
    if (!systemAlertsContainer) {
      var alertsContainer = document.createElement('div');
      alertsContainer.id = 'system-alerts';
      alertsContainer.className = 'position-fixed top-0 end-0 p-3';
      alertsContainer.style.zIndex = '1055';
      document.body.appendChild(alertsContainer);
      systemAlertsContainer = alertsContainer;
    }

    window.showSystemAlert = function(message, type, duration) {
      type = (typeof type === 'undefined') ? 'info' : type;
      duration = (typeof duration === 'undefined') ? 5000 : duration;
      var alertId = 'alert-' + Date.now();
      var alertElement = document.createElement('div');
      alertElement.id = alertId;
      alertElement.className = 'alert alert-' + type + ' alert-dismissible fade show';
      alertElement.setAttribute('role', 'alert');
      alertElement.innerHTML = (
        String(message) +
        '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>'
      );

      systemAlertsContainer.appendChild(alertElement);

      if (duration > 0) {
        setTimeout(function() {
          var alert = document.getElementById(alertId);
          if (alert && window.bootstrap && bootstrap.Alert) {
            try { var bsAlert = new bootstrap.Alert(alert); bsAlert.close(); } catch(_){}
          } else if (alert && alert.parentNode) {
            alert.parentNode.removeChild(alert);
          }
        }, duration);
      }
    };

    try { console.log('Alert System Initialized'); } catch(_){}
  }

  function initializeOnlineStatusDetection() {
    function updateOnlineStatus() {
      if (navigator.onLine) {
        if (window.showSystemAlert) {
          window.showSystemAlert('Connection restored', 'success', 3000);
        }
      } else {
        if (window.showSystemAlert) {
          window.showSystemAlert('Connection lost. Some features may not work.', 'warning', 0);
        }
      }
    }

    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);

    try { console.log('Online Status Detection Initialized'); } catch(_){}
  }

  // =========================================================================
  // 7. Main Initialization
  // =========================================================================
  document.addEventListener('DOMContentLoaded', function() {
    try { console.log('Open CVE Report Base JS: DOM Content Loaded'); } catch(_){}

    selectElements();

    if (!checkRequiredElements()) {
      try { console.error('Open CVE Report Base JS: Required elements missing. Some functionality may not work.'); } catch(_){}
    }

    if (htmlEl && htmlEl.classList) { htmlEl.classList.add('js-enabled'); }

    initializeAccessibility();

    if (typeof bootstrap !== 'undefined') {
      initializeTooltips();
      setupDynamicTooltipObserver();
      initializeDropdowns();
      initializeAlertSystem();
      initializeOnlineStatusDetection();
      try { console.log('Bootstrap components initialized'); } catch(_){}
    } else {
      try { console.warn('Bootstrap JS not loaded. Some components may not function properly.'); } catch(_){}
    }

    document.addEventListener('paginationUpdated', function() {
      if (typeof bootstrap !== 'undefined') {
        initializeTooltips();
      }
    });

    try { console.log('Open CVE Report Base JS: Initialization Complete'); } catch(_){}
  });

})();