'use strict';

/**
 * Card Navigation Enhancement (ES5 Compatible)
 * Navegação simples e direta dos cards da página inicial
 */
(function() {
  function CardNavigationEnhancer() {
    this.init();
  }

  CardNavigationEnhancer.prototype.init = function() {
    this.setupCardClickHandlers();
    this.preloadCriticalResources();
  };

  /**
   * Configura os manipuladores de clique para os cards
   */
  CardNavigationEnhancer.prototype.setupCardClickHandlers = function() {
    var cardLinks = document.querySelectorAll('.metric-card-link');
    var self = this;
    Array.prototype.forEach.call(cardLinks, function(link) {
      link.addEventListener('click', function(e) {
        self.handleCardClick(e, link);
      });
    });
  };

  /**
   * Manipula o clique nos cards - navegação direta
   */
  CardNavigationEnhancer.prototype.handleCardClick = function(event, link) {
    var href = link.getAttribute('href');
    if (!href) {
      if (event && event.preventDefault) event.preventDefault();
      return;
    }
    // Navegação direta sem animações
    // O evento segue seu curso normal
  };

  /**
   * Pré-carrega recursos críticos para melhorar performance
   */
  CardNavigationEnhancer.prototype.preloadCriticalResources = function() {
    // Pré-carrega Chart.js (UMD) se não estiver carregado
    if (typeof window.Chart === 'undefined') {
      this.preloadScript('https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js');
    }
    // Pré-carrega CSS da página de detalhes
    this.preloadStylesheet('/static/css/pages/vulnerability-details.css');
    // Pré-carrega JavaScript de charts de detalhes
    this.preloadScript('/static/js/features/vulnerability-charts.js');
  };

  /**
   * Pré-carrega um script
   */
  CardNavigationEnhancer.prototype.preloadScript = function(src) {
    var link = document.createElement('link');
    link.rel = 'preload';
    link.as = 'script';
    link.href = src;
    // Garantir CORS ao pré-carregar scripts de CDN
    link.setAttribute('crossorigin', 'anonymous');
    document.head.appendChild(link);
  };

  /**
   * Pré-carrega uma folha de estilo
   */
  CardNavigationEnhancer.prototype.preloadStylesheet = function(href) {
    var link = document.createElement('link');
    link.rel = 'preload';
    link.as = 'style';
    link.href = href;
    document.head.appendChild(link);
  };

  // Inicialização quando o DOM estiver pronto
  document.addEventListener('DOMContentLoaded', function() {
    // Inicializa a navegação simples dos cards
    window.cardNavigationEnhancer = new CardNavigationEnhancer();
    try { console.log('Card Navigation Enhancer initialized'); } catch (_){ }
  });

  // Exporta para uso global
  window.CardNavigationEnhancer = CardNavigationEnhancer;
})();