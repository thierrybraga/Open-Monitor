/**
 * Footer JavaScript (ES5 Compatible)
 * - Back to Top, footer navigation, animations
 * - Removes class/arrow/functions shorthand and adds fallbacks
 */
(function() {
  'use strict';

  function FooterManager() {
    this.backToTopBtn = null;
    this.footer = null;
    this.showThreshold = 300;
    this.animationDuration = 800;
    this.scrollTimeout = null;
    this.isInitialized = false;

    this.handleScroll = this.handleScroll.bind(this);
    this.scrollToTop = this.scrollToTop.bind(this);
    this.handleKeydown = this.handleKeydown.bind(this);
  }

  FooterManager.prototype.init = function() {
    if (this.isInitialized) {
      try { console.warn('FooterManager já foi inicializado'); } catch (_) {}
      return;
    }

    this.selectElements();
    this.addDynamicStyles();
    this.initBackToTopButton();
    this.initFooterNavigation();
    this.setupEventListeners();
    this.isInitialized = true;
    try { console.log('FooterManager inicializado com sucesso'); } catch (_) {}
  };

  FooterManager.prototype.selectElements = function() {
    this.backToTopBtn = document.getElementById('back-to-top');
    this.footer = document.querySelector('footer.footer');
    if (!this.footer) {
      try { console.warn('Footer não encontrado'); } catch (_) {}
    }
  };

  FooterManager.prototype.initBackToTopButton = function() {
    if (!this.backToTopBtn) {
      try { console.warn('Botão "Voltar ao topo" não encontrado'); } catch (_) {}
      return;
    }
    this.setBackToTopVisibility(false);
    this.backToTopBtn.style.transition = 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
    this.toggleBackToTopBtn();
  };

  FooterManager.prototype.toggleBackToTopBtn = function() {
    if (!this.backToTopBtn) return;
    var scrollPosition = window.pageYOffset || document.documentElement.scrollTop;
    var shouldShow = scrollPosition > this.showThreshold;
    this.setBackToTopVisibility(shouldShow);
  };

  FooterManager.prototype.setBackToTopVisibility = function(visible) {
    if (!this.backToTopBtn) return;
    if (visible) {
      this.backToTopBtn.style.opacity = '1';
      this.backToTopBtn.style.visibility = 'visible';
      this.backToTopBtn.style.transform = 'translateY(0)';
      this.backToTopBtn.setAttribute('aria-hidden', 'false');
      this.backToTopBtn.classList.add('show');
    } else {
      this.backToTopBtn.style.opacity = '0';
      this.backToTopBtn.style.visibility = 'hidden';
      this.backToTopBtn.style.transform = 'translateY(20px)';
      this.backToTopBtn.setAttribute('aria-hidden', 'true');
      this.backToTopBtn.classList.remove('show');
    }
  };

  FooterManager.prototype.scrollToTop = function(e) {
    if (e && e.preventDefault) e.preventDefault();
    if (!this.backToTopBtn) return;
    this.backToTopBtn.classList.add('loading');
    var behavior = this.prefersReducedMotion() ? 'auto' : 'smooth';
    try {
      window.scrollTo({ top: 0, behavior: behavior });
    } catch (_) {
      window.scrollTo(0, 0);
    }
    var self = this;
    setTimeout(function() {
      if (self.backToTopBtn) { self.backToTopBtn.classList.remove('loading'); }
    }, this.animationDuration);
    setTimeout(function() {
      var topElement = document.getElementById('top') || document.body;
      if (topElement && topElement.focus) { topElement.focus(); }
    }, this.animationDuration / 2);
  };

  FooterManager.prototype.initFooterNavigation = function() {
    if (!this.footer) return;
    var footerLinks = this.footer.querySelectorAll('.footer-nav a, .footer-actions a');
    var self = this;
    Array.prototype.forEach.call(footerLinks, function(link) {
      if (!link.getAttribute('aria-label') && link.textContent && link.textContent.trim) {
        link.setAttribute('aria-label', 'Ir para ' + link.textContent.trim());
      }
      link.addEventListener('mouseenter', self.handleLinkHover.bind(self));
      link.addEventListener('mouseleave', self.handleLinkLeave.bind(self));
    });
    this.initSocialLinks();
    this.initIconAnimations();
    this.initFooterVisibilityAnimation();
  };

  FooterManager.prototype.initSocialLinks = function() {
    if (!this.footer) return;
    var socialLinks = this.footer.querySelectorAll('.footer-social-link');
    var self = this;
    Array.prototype.forEach.call(socialLinks, function(link) {
      link.addEventListener('click', self.createRippleEffect.bind(self));
      link.addEventListener('mouseenter', function(e) {
        var icon = (e.target ? e.target.querySelector('i') : null);
        if (icon) {
          icon.style.transform = 'scale(1.2) rotate(5deg)';
          icon.style.transition = 'transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)';
        }
        e.target.style.transform = 'translateY(-3px)';
        e.target.style.boxShadow = 'var(--shadow-lg)';
      });
      link.addEventListener('mouseleave', function(e) {
        var icon2 = (e.target ? e.target.querySelector('i') : null);
        if (icon2) { icon2.style.transform = ''; }
        e.target.style.transform = '';
        e.target.style.boxShadow = '';
      });
      link.addEventListener('click', function(e) {
        var platform = (e.target && e.target.getAttribute('aria-label')) ? e.target.getAttribute('aria-label') : 'Unknown';
        try { console.log('Social link clicked: ' + platform); } catch (_){ }
        self.addClickFeedback(e.target);
      });
    });
  };

  FooterManager.prototype.initIconAnimations = function() {
    if (!this.footer) return;
    var iconElements = this.footer.querySelectorAll('i[class*="bi-"]');
    Array.prototype.forEach.call(iconElements, function(icon) {
      icon.style.opacity = '0';
      icon.style.transform = 'scale(0.8)';
      if (window.IntersectionObserver) {
        var observer = new IntersectionObserver(function(entries) {
          Array.prototype.forEach.call(entries, function(entry) {
            if (entry.isIntersecting) {
              setTimeout(function() {
                icon.style.transition = 'all 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)';
                icon.style.opacity = '1';
                icon.style.transform = 'scale(1)';
              }, Math.floor(Math.random() * 300));
              observer.unobserve(icon);
            }
          });
        }, { threshold: 0.1 });
        observer.observe(icon);
      } else {
        setTimeout(function() {
          icon.style.transition = 'all 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)';
          icon.style.opacity = '1';
          icon.style.transform = 'scale(1)';
        }, 100);
      }
    });
  };

  FooterManager.prototype.initFooterVisibilityAnimation = function() {
    if (!this.footer) return;
    var footerSections = this.footer.querySelectorAll('.footer-brand, .footer-nav, .footer-social, .footer-actions, .footer-copyright');
    Array.prototype.forEach.call(footerSections, function(section) {
      section.style.opacity = '0';
      section.style.transform = 'translateY(30px)';
    });
    var self = this;
    if (window.IntersectionObserver) {
      var observer = new IntersectionObserver(function(entries) {
        if (entries && entries.length) {
          Array.prototype.forEach.call(footerSections, function(section, index) {
            setTimeout(function() {
              section.style.transition = 'all 0.8s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
              section.style.opacity = '1';
              section.style.transform = 'translateY(0)';
            }, 150 * index);
          });
        }
      }, { threshold: 0.15 });
      observer.observe(self.footer);
    } else {
      Array.prototype.forEach.call(footerSections, function(section, index) {
        setTimeout(function() {
          section.style.transition = 'all 0.8s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
          section.style.opacity = '1';
          section.style.transform = 'translateY(0)';
        }, 150 * index);
      });
    }
  };

  FooterManager.prototype.handleLinkHover = function(e) {
    var t = e.target;
    if (t) {
      t.style.transform = 'translateY(-1px)';
      t.style.transition = 'transform 0.2s ease';
    }
  };

  FooterManager.prototype.handleLinkLeave = function(e) {
    var t = e.target;
    if (t) { t.style.transform = ''; }
  };

  FooterManager.prototype.createRippleEffect = function(e) {
    var target = e.currentTarget || e.target;
    if (!target || !target.getBoundingClientRect) return;
    var rect = target.getBoundingClientRect();
    var x = (e.clientX || 0) - rect.left;
    var y = (e.clientY || 0) - rect.top;
    var ripple = document.createElement('span');
    ripple.className = 'ripple-effect';
    ripple.style.left = x + 'px';
    ripple.style.top = y + 'px';
    ripple.style.position = 'absolute';
    target.appendChild(ripple);
    setTimeout(function() {
      try { target.removeChild(ripple); } catch (_) {}
    }, 600);
  };

  FooterManager.prototype.addClickFeedback = function(element) {
    if (!element) return;
    element.classList.add('clicked');
    setTimeout(function() { element.classList.remove('clicked'); }, 300);
  };

  FooterManager.prototype.addDynamicStyles = function() {
    var styleId = 'footer-dynamic-styles';
    var existing = document.getElementById(styleId);
    if (existing) return;
    var style = document.createElement('style');
    style.id = styleId;
    style.textContent = '.ripple-effect{position:absolute;border-radius:50%;transform:scale(0);animation:ripple .6s linear;background:rgba(0,0,0,.3);width:100px;height:100px;pointer-events:none}.footer .clicked{filter:brightness(1.1)}@keyframes ripple{to{transform:scale(4);opacity:0}}';
    document.head.appendChild(style);
  };

  FooterManager.prototype.setupEventListeners = function() {
    var self = this;
    if (this.backToTopBtn) {
      this.backToTopBtn.addEventListener('click', this.scrollToTop);
      this.backToTopBtn.addEventListener('keydown', this.handleKeydown);
    }
    window.addEventListener('scroll', function() {
      clearTimeout(self.scrollTimeout);
      self.scrollTimeout = setTimeout(function() { self.toggleBackToTopBtn(); }, 100);
    });
  };

  FooterManager.prototype.handleScroll = function() {
    this.toggleBackToTopBtn();
  };

  FooterManager.prototype.handleKeydown = function(e) {
    var key = e.key || e.keyCode;
    if (key === 'Enter' || key === 13 || key === ' ') {
      if (e && e.preventDefault) e.preventDefault();
      this.scrollToTop(e);
    }
  };

  FooterManager.prototype.prefersReducedMotion = function() {
    try {
      var mq = window.matchMedia('(prefers-reduced-motion: reduce)');
      return mq && mq.matches;
    } catch (_) {
      return false;
    }
  };

  FooterManager.prototype.destroy = function() {
    if (this.backToTopBtn) {
      this.backToTopBtn.removeEventListener('click', this.scrollToTop);
      this.backToTopBtn.removeEventListener('keydown', this.handleKeydown);
    }
    window.removeEventListener('scroll', this.handleScroll);
    this.isInitialized = false;
  };

  FooterManager.prototype.showBackToTop = function() { this.setBackToTopVisibility(true); };
  FooterManager.prototype.hideBackToTop = function() { this.setBackToTopVisibility(false); };
  FooterManager.prototype.scrollToTopProgrammatically = function() { this.scrollToTop({ preventDefault: function(){}, target: this.backToTopBtn }); };

  var footerManager = null;
  document.addEventListener('DOMContentLoaded', function() {
    try {
      footerManager = new FooterManager();
      footerManager.init();
      window.footerManager = footerManager;
      window.FooterManager = FooterManager;
    } catch (e) {
      try { console.warn('FooterManager init failed:', e); } catch (_) {}
    }
  });

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { FooterManager: FooterManager, footerManager: footerManager };
  }
})();