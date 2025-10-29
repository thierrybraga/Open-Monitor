// Polyfill for CustomEvent in older browsers
(function() {
  if (typeof window.CustomEvent !== 'function') {
    function CustomEvent(event, params) {
      params = params || { bubbles: false, cancelable: false, detail: undefined };
      var evt = document.createEvent('CustomEvent');
      evt.initCustomEvent(event, params.bubbles, params.cancelable, params.detail);
      return evt;
    }
    CustomEvent.prototype = window.Event.prototype;
    window.CustomEvent = CustomEvent;
  }
})();

(function() {
  function SidebarManager() {
    // Elementos DOM
    this.sidebar = null;
    this.sidebarToggle = null;
    this.sidebarScrim = null;
    this.sidebarOverlay = null;
    this.sidebarLinks = null;
    this.mainContent = null;
    this.body = document.body;

    // Estado
    this.isOpen = false;
    this.isInitialized = false;

    // Configurações
    this.config = {
      breakpoints: { mobile: 768, tablet: 992 },
      animation: { duration: 400, easing: 'cubic-bezier(0.4, 0, 0.2, 1)', staggerDelay: 50 },
      classes: {
        expanded: 'expanded',
        show: 'show',
        visible: 'visible',
        active: 'active',
        hovering: 'sidebar-hovering',
        overflowHidden: 'overflow-hidden'
      }
    };

    // Bind methods
    this.handleToggle = this.handleToggle.bind(this);
    this.handleOverlayClick = this.handleOverlayClick.bind(this);
    this.handleResize = this.handleResize.bind(this);
    this.handleKeydown = this.handleKeydown.bind(this);
    this.handleLinkClick = this.handleLinkClick.bind(this);
  }

  SidebarManager.prototype.init = function() {
    if (this.isInitialized) return;
    this.findElements();
    if (!this.validateElements()) return;
    this.createOverlay();
    this.setupEventListeners();
    this.setupHoverEffects();
    this.setupAccessibility();
    this.restoreState();
    this.adjustForScreenSize();
    this.isInitialized = true;
    try { console.log('Sidebar Manager initialized successfully'); } catch (e) {}
  };

  SidebarManager.prototype.findElements = function() {
    this.sidebar = document.getElementById('sidebar');
    this.sidebarToggle = document.getElementById('sidebarToggle') ||
                         document.querySelector('.sidebar-toggle') ||
                         document.querySelector('[data-bs-target="#sidebar"]');
    this.sidebarScrim = document.querySelector('.sidebar-scrim');
    this.sidebarOverlay = document.querySelector('.sidebar-overlay');
    this.sidebarLinks = document.querySelectorAll('.sidebar-link');
    this.mainContent = document.querySelector('.main-content') ||
                       document.querySelector('.main-content-area-wrapper');
  };

  SidebarManager.prototype.validateElements = function() {
    if (!this.sidebar) { try { console.warn('Sidebar element not found'); } catch (e) {} return false; }
    if (!this.sidebarToggle) { try { console.warn('Sidebar toggle button not found'); } catch (e) {} return false; }
    return true;
  };

  SidebarManager.prototype.createOverlay = function() {
    if (!this.sidebarOverlay && !this.sidebarScrim) {
      this.sidebarOverlay = document.createElement('div');
      this.sidebarOverlay.className = 'sidebar-overlay';
      this.sidebarOverlay.setAttribute('aria-hidden', 'true');
      document.body.appendChild(this.sidebarOverlay);
    }
  };

  SidebarManager.prototype.setupEventListeners = function() {
    var self = this;
    if (this.sidebarToggle) { this.sidebarToggle.addEventListener('click', this.handleToggle); }
    var overlay = this.sidebarOverlay || this.sidebarScrim;
    if (overlay) { overlay.addEventListener('click', this.handleOverlayClick); }
    Array.prototype.forEach.call(this.sidebarLinks, function(link) {
      link.addEventListener('click', self.handleLinkClick);
    });
    window.addEventListener('resize', Utils.debounce(this.handleResize, 150));
    document.addEventListener('keydown', this.handleKeydown);
    window.addEventListener('sidebarToggle', this.handleToggle);
  };

  SidebarManager.prototype.setupHoverEffects = function() {
    if (!this.sidebar) return;
    var self = this;
    var hoverTimeout;
    this.sidebar.addEventListener('mouseenter', function() {
      clearTimeout(hoverTimeout);
      self.sidebar.classList.add(self.config.classes.hovering);
      self.animateLabelsIn();
    });
    this.sidebar.addEventListener('mouseleave', function() {
      hoverTimeout = setTimeout(function() {
        self.sidebar.classList.remove(self.config.classes.hovering);
        self.animateLabelsOut();
      }, 100);
    });
    Array.prototype.forEach.call(this.sidebarLinks, function(link, index) {
      self.setupLinkHoverEffects(link, index);
    });
  };

  SidebarManager.prototype.setupLinkHoverEffects = function(link, index) {
    var icon = link.querySelector('i');
    link.addEventListener('mouseenter', function() {
      if (icon) {
        icon.style.transform = 'scale(1.1) rotate(5deg)';
        icon.style.transition = 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
      }
      link.style.boxShadow = 'inset 0 1px 0 rgba(255, 255, 255, 0.1), 0 4px 12px rgba(99, 102, 241, 0.15)';
      if (navigator.vibrate) { navigator.vibrate(10); }
    });
    link.addEventListener('mouseleave', function() {
      if (icon) { icon.style.transform = ''; }
      link.style.boxShadow = '';
    });
  };

  SidebarManager.prototype.setupAccessibility = function() {
    this.sidebar.setAttribute('role', 'navigation');
    this.sidebar.setAttribute('aria-label', 'Navegação principal');
    if (this.sidebarToggle) {
      this.sidebarToggle.setAttribute('aria-controls', 'sidebar');
      this.sidebarToggle.setAttribute('aria-expanded', 'false');
    }
    this.sidebar.setAttribute('tabindex', '-1');
  };

  SidebarManager.prototype.handleToggle = function(event) {
    if (event) event.preventDefault();
    if (this.isOpen) { this.close(); } else { this.open(); }
  };

  SidebarManager.prototype.open = function() {
    if (!this.sidebar) return;
    this.isOpen = true;
    this.sidebar.classList.add(this.config.classes.expanded);
    if (this.isMobile()) {
      this.sidebar.classList.add(this.config.classes.show);
      this.showOverlay();
      this.body.classList.add(this.config.classes.overflowHidden);
      var self = this;
      setTimeout(function() { self.sidebar.focus(); }, 100);
    }
    if (this.sidebarToggle) { this.sidebarToggle.setAttribute('aria-expanded', 'true'); }
    this.saveState();
    try { window.dispatchEvent(new CustomEvent('sidebarOpened', { detail: { sidebar: this.sidebar } })); } catch (e) {}
  };

  SidebarManager.prototype.close = function() {
    if (!this.sidebar) return;
    this.isOpen = false;
    this.sidebar.classList.remove(this.config.classes.expanded, this.config.classes.show);
    this.hideOverlay();
    this.body.classList.remove(this.config.classes.overflowHidden);
    if (this.sidebarToggle) { this.sidebarToggle.setAttribute('aria-expanded', 'false'); }
    this.saveState();
    try { window.dispatchEvent(new CustomEvent('sidebarClosed', { detail: { sidebar: this.sidebar } })); } catch (e) {}
  };

  SidebarManager.prototype.showOverlay = function() {
    var overlay = this.sidebarOverlay || this.sidebarScrim;
    if (overlay) { overlay.classList.add(this.config.classes.visible); }
  };

  SidebarManager.prototype.hideOverlay = function() {
    var overlay = this.sidebarOverlay || this.sidebarScrim;
    if (overlay) { overlay.classList.remove(this.config.classes.visible); }
  };

  SidebarManager.prototype.handleOverlayClick = function() {
    if (this.isOpen && this.isMobile()) { this.close(); }
  };

  SidebarManager.prototype.handleResize = function() { this.adjustForScreenSize(); };

  SidebarManager.prototype.adjustForScreenSize = function() {
    if (this.isMobile()) {
      if (this.isOpen) { this.close(); }
    } else {
      this.sidebar.classList.remove(this.config.classes.show);
      this.hideOverlay();
      this.body.classList.remove(this.config.classes.overflowHidden);
    }
  };

  SidebarManager.prototype.handleKeydown = function(event) {
    if (event.key === 'Escape' && this.isOpen && this.isMobile()) { this.close(); }
  };

  SidebarManager.prototype.handleLinkClick = function(event) {
    var link = event.currentTarget;
    this.createRippleEffect(event, link);
    this.updateActiveState(link);
    this.animateClickFeedback(link);
    var self = this;
    if (this.isOpen && this.isMobile()) { setTimeout(function() { self.close(); }, 100); }
  };

  SidebarManager.prototype.createRippleEffect = function(event, element) {
    var ripple = document.createElement('span');
    var rect = element.getBoundingClientRect();
    var size = Math.max(rect.width, rect.height);
    var x = event.clientX - rect.left - size / 2;
    var y = event.clientY - rect.top - size / 2;
    var css = '' +
      'position: absolute;' +
      'width: ' + size + 'px;' +
      'height: ' + size + 'px;' +
      'left: ' + x + 'px;' +
      'top: ' + y + 'px;' +
      'background: rgba(99, 102, 241, 0.3);' +
      'border-radius: 50%;' +
      'transform: scale(0);' +
      'animation: ripple 0.6s ease-out;' +
      'pointer-events: none;' +
      'z-index: 10;';
    ripple.style.cssText = css;
    element.style.position = 'relative';
    element.appendChild(ripple);
    setTimeout(function() { if (ripple && ripple.parentNode) { ripple.parentNode.removeChild(ripple); } }, 600);
  };

  SidebarManager.prototype.updateActiveState = function(activeLink) {
    var self = this;
    Array.prototype.forEach.call(this.sidebarLinks, function(link) {
      link.classList.remove(self.config.classes.active);
    });
    activeLink.classList.add(this.config.classes.active);
    var href = activeLink.getAttribute('href');
    if (href) { try { localStorage.setItem('activeSidebarLink', href); } catch (e) {} }
  };

  SidebarManager.prototype.animateClickFeedback = function(link) {
    var originalTransform = link.style.transform;
    link.style.transform = 'scale(0.95)';
    link.style.transition = 'transform 0.1s ease-out';
    setTimeout(function() {
      link.style.transform = originalTransform;
      link.style.transition = 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
    }, 100);
  };

  SidebarManager.prototype.animateLabelsIn = function() {
    var self = this;
    var labels = this.sidebar.querySelectorAll('.sidebar-label');
    Array.prototype.forEach.call(labels, function(label, index) {
      setTimeout(function() {
        label.style.opacity = '1';
        label.style.transform = 'translateX(0)';
        label.style.transition = 'all ' + self.config.animation.duration + 'ms ' + self.config.animation.easing;
      }, index * self.config.animation.staggerDelay);
    });
  };

  SidebarManager.prototype.animateLabelsOut = function() {
    var self = this;
    var labels = this.sidebar.querySelectorAll('.sidebar-label');
    Array.prototype.forEach.call(labels, function(label, index) {
      setTimeout(function() {
        label.style.opacity = '0';
        label.style.transform = 'translateX(-10px)';
      }, index * (self.config.animation.staggerDelay / 2));
    });
  };

  SidebarManager.prototype.isMobile = function() { return window.innerWidth < this.config.breakpoints.mobile; };

  SidebarManager.prototype.isTablet = function() {
    return window.innerWidth >= this.config.breakpoints.mobile && window.innerWidth < this.config.breakpoints.tablet;
  };

  SidebarManager.prototype.saveState = function() {
    try { localStorage.setItem('sidebarState', JSON.stringify({ isOpen: this.isOpen, timestamp: Date.now() })); } catch (e) {}
  };

  SidebarManager.prototype.restoreState = function() {
    try {
      var saved = null;
      try { saved = localStorage.getItem('sidebarState'); } catch (e) {}
      if (saved) {
        var state = JSON.parse(saved);
        if (!this.isMobile() && (Date.now() - state.timestamp) < 3600000) {
          if (state.isOpen) { this.open(); }
        }
      }
      var activeHref = null;
      try { activeHref = localStorage.getItem('activeSidebarLink'); } catch (e) {}
      if (activeHref) {
        var selector = '.sidebar-link[href="' + activeHref + '"]';
        var activeLink = document.querySelector(selector);
        if (activeLink) { this.updateActiveState(activeLink); }
      }
    } catch (error) {
      try { console.warn('Error restoring sidebar state:', error); } catch (e) {}
    }
  };

  SidebarManager.prototype.toggle = function() { this.handleToggle(); };
  SidebarManager.prototype.show = function() { this.open(); };
  SidebarManager.prototype.hide = function() { this.close(); };
  SidebarManager.prototype.isVisible = function() { return this.isOpen; };

  SidebarManager.prototype.destroy = function() {
    if (this.sidebarToggle) { this.sidebarToggle.removeEventListener('click', this.handleToggle); }
    var overlay = this.sidebarOverlay || this.sidebarScrim;
    if (overlay) { overlay.removeEventListener('click', this.handleOverlayClick); }
    var self = this;
    Array.prototype.forEach.call(this.sidebarLinks, function(link) {
      link.removeEventListener('click', self.handleLinkClick);
    });
    window.removeEventListener('resize', this.handleResize);
    document.removeEventListener('keydown', this.handleKeydown);
    if (this.sidebarOverlay && this.sidebarOverlay.parentNode) {
      this.sidebarOverlay.parentNode.removeChild(this.sidebarOverlay);
    }
    this.isInitialized = false;
  };

  // CSS para animações (injetado dinamicamente)
  var sidebarStyles = '' +
    '@keyframes ripple\n' +
    '{\n' +
    '  to {\n' +
    '    transform: scale(4);\n' +
    '    opacity: 0;\n' +
    '  }\n' +
    '}\n';

  // Injeta estilos se não existirem
  if (!document.querySelector('#sidebar-dynamic-styles')) {
    var styleSheet = document.createElement('style');
    styleSheet.id = 'sidebar-dynamic-styles';
    styleSheet.textContent = sidebarStyles;
    document.head.appendChild(styleSheet);
  }

  // Instância global
  var sidebarManager = null;

  // Inicialização automática
  document.addEventListener('DOMContentLoaded', function() {
    sidebarManager = new SidebarManager();
    sidebarManager.init();
  });

  // Exportar para uso global
  window.SidebarManager = SidebarManager;
  window.sidebarManager = sidebarManager;

  // API de compatibilidade para código existente
  window.SidebarController = {
    toggle: function() { if (sidebarManager) { sidebarManager.toggle(); } },
    open: function() { if (sidebarManager) { sidebarManager.show(); } },
    close: function() { if (sidebarManager) { sidebarManager.hide(); } },
    isOpen: function() { return sidebarManager ? sidebarManager.isVisible() : false; }
  };
})();