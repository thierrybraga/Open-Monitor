/**
 * Utilitários Consolidados - Open Monitor (ES5 Compat)
 * Arquivo centralizado com funções utilitárias comuns
 * Versão: 1.0 - Consolidação de duplicações
 * 
 * Funcionalidades:
 * - Performance (debounce, throttle)
 * - Formatação (datas, tempo)
 * - Validação (email, formulários)
 * - DOM helpers
 */

(function() {
  function Utils() {}

  // Debounce
  Utils._debounceTimers = Utils._debounceTimers || {};
  Utils.debounce = function(func, wait, key) {
    if (typeof key === 'undefined') key = 'default';
    if (!Utils._debounceTimers) { Utils._debounceTimers = {}; }

    return function() {
      var args = Array.prototype.slice.call(arguments);
      var self = this;
      var later = function() {
        clearTimeout(Utils._debounceTimers[key]);
        try { delete Utils._debounceTimers[key]; } catch(_){}
        func.apply(self, args);
      };

      clearTimeout(Utils._debounceTimers[key]);
      Utils._debounceTimers[key] = setTimeout(later, wait);
    };
  };

  // Throttle
  Utils.throttle = function(func, limit) {
    var inThrottle = false;
    return function() {
      if (!inThrottle) {
        func.apply(this, arguments);
        inThrottle = true;
        setTimeout(function() { inThrottle = false; }, limit);
      }
    };
  };

  // Formata data
  Utils.formatDate = function(dateInput, options) {
    if (!dateInput) return 'N/A';
    options = options || {};
    try {
      var date = (typeof dateInput === 'string') ? new Date(dateInput) : dateInput;
      if (!date || isNaN(date.getTime())) { return 'Data inválida'; }

      var defaultOptions = { year: 'numeric', month: 'short', day: 'numeric' };
      for (var k in options) { if (Object.prototype.hasOwnProperty.call(options, k)) { defaultOptions[k] = options[k]; } }

      return date.toLocaleDateString(Utils.getLocale(), defaultOptions);
    } catch (error) {
      try { console.error('Erro ao formatar data:', error); } catch(_){}
      return 'Erro na data';
    }
  };

  // Formata tempo
  Utils.formatTime = function(time) {
    if (typeof time !== 'number' || time < 0) { return '0ms'; }
    if (time < 1000) {
      return String(Math.round(time)) + 'ms';
    } else if (time < 60000) {
      return (time / 1000).toFixed(2) + 's';
    } else {
      var minutes = Math.floor(time / 60000);
      var seconds = ((time % 60000) / 1000).toFixed(0);
      return String(minutes) + 'm ' + String(seconds) + 's';
    }
  };

  // Valida email
  Utils.validateEmail = function(email) {
    if (!email || typeof email !== 'string') { return false; }
    var emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email.trim());
  };

  // Valida campo de formulário
  Utils.validateField = function(field) {
    if (!field) return false;
    var isValid = true;
    var value = (field.value || '').trim();
    var type = field.type;

    switch (type) {
      case 'email':
        isValid = Utils.validateEmail(value);
        break;
      case 'password':
        isValid = value.length >= 6;
        break;
      case 'text':
      case 'textarea':
        isValid = value.length > 0;
        break;
      default:
        if (typeof field.checkValidity === 'function') { isValid = field.checkValidity(); }
    }

    if (field.classList) {
      field.classList.remove('is-valid', 'is-invalid');
      field.classList.add(isValid ? 'is-valid' : 'is-invalid');
    }
    field.setAttribute('aria-invalid', isValid ? 'false' : 'true');
    return isValid;
  };

  // Valida formulário
  Utils.validateForm = function(form) {
    if (!form) return false;
    var isValid = true;
    var inputs = form.querySelectorAll('input, textarea, select');
    Array.prototype.forEach.call(inputs, function(input) {
      if (!Utils.validateField(input)) { isValid = false; }
    });
    return isValid;
  };

  // Limpa timers de debounce
  Utils.clearDebounceTimers = function() {
    if (Utils._debounceTimers) {
      for (var k in Utils._debounceTimers) {
        if (Object.prototype.hasOwnProperty.call(Utils._debounceTimers, k)) {
          clearTimeout(Utils._debounceTimers[k]);
        }
      }
      Utils._debounceTimers = {};
    }
  };

  // Add event listener com tracking
  Utils._trackedListeners = Utils._trackedListeners || [];
  Utils.addEventListenerTracked = function(element, event, handler, options) {
    if (!element || !event || !handler) return;
    options = options || {};
    element.addEventListener(event, handler, options);
    Utils._trackedListeners.push({ element: element, event: event, handler: handler, options: options });
  };

  // Remove listeners trackados
  Utils.removeTrackedListeners = function() {
    if (Utils._trackedListeners && Utils._trackedListeners.length) {
      for (var i = 0; i < Utils._trackedListeners.length; i++) {
        var item = Utils._trackedListeners[i];
        if (item && item.element && item.element.removeEventListener) {
          item.element.removeEventListener(item.event, item.handler, item.options);
        }
      }
      Utils._trackedListeners = [];
    }
  };

  // Elemento visível
  Utils.isElementVisible = function(element) {
    if (!element) return false;
    var rect = element.getBoundingClientRect();
    return (
      rect.top >= 0 &&
      rect.left >= 0 &&
      rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
      rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
  };

  // Scroll suave
  Utils.smoothScrollTo = function(target, options) {
    var element = (typeof target === 'string') ? document.querySelector(target) : target;
    if (!element) return;
    options = options || {};
    var defaultOptions = { behavior: 'smooth', block: 'start', inline: 'nearest' };
    for (var k2 in options) { if (Object.prototype.hasOwnProperty.call(options, k2)) { defaultOptions[k2] = options[k2]; } }
    try { element.scrollIntoView(defaultOptions); } catch (e) { try { element.scrollIntoView(true); } catch(_){} }
  };

  // Gera ID único
  Utils.generateUniqueId = function(prefix) {
    prefix = (typeof prefix === 'undefined') ? 'id' : prefix;
    return prefix + '-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
  };

  // Cleanup
  Utils.cleanup = function() {
    Utils.clearDebounceTimers();
    Utils.removeTrackedListeners();
    try { console.log('Utils cleanup completed'); } catch(_){}
  };

  // Fetch com retry e backoff exponencial simples (ES5 compat)
  // Disponibiliza window.fetchWithRetry para uso em páginas diversas
  function delay(ms) {
    return new Promise(function(resolve) { setTimeout(resolve, ms); });
  }

  function isRetryableStatus(status) {
    return status === 429 || (status >= 500 && status <= 599);
  }

  function fetchWithRetry(url, options, retries, backoffMs) {
    options = options || {};
    retries = (typeof retries === 'number') ? retries : 2;
    backoffMs = (typeof backoffMs === 'number') ? backoffMs : 300;

    var attempt = 0;

    function exec() {
      // Se fetch não existir, falha controlada
      if (typeof window.fetch !== 'function') {
        return Promise.reject(new Error('fetch indisponível no navegador'));
      }

      return window.fetch(url, options).then(function(response) {
        if (!response) {
          if (attempt < retries) {
            attempt += 1;
            return delay(backoffMs * attempt).then(exec);
          }
          return Promise.reject(new Error('Resposta indefinida no fetch'));
        }

        if (!response.ok && isRetryableStatus(response.status) && attempt < retries) {
          attempt += 1;
          return delay(backoffMs * attempt).then(exec);
        }

        return response;
      }).catch(function(err) {
        // Erros de rede/abort/timeouts: tenta novamente até o limite
        if (attempt < retries) {
          attempt += 1;
          return delay(backoffMs * attempt).then(exec);
        }
        throw err;
      });
    }

    return exec();
  }

  // Obtém locale do UI ou do documento
  Utils.getLocale = function() {
    try {
      var lang = (typeof window !== 'undefined' && window.UI_LANGUAGE) ? window.UI_LANGUAGE : (document && document.documentElement ? document.documentElement.lang : 'pt-BR');
      if (!lang) lang = 'pt-BR';
      var lower = String(lang).toLowerCase();
      if (lower === 'pt') return 'pt-BR';
      if (lower === 'en') return 'en-US';
      return lang;
    } catch (e) {
      return 'pt-BR';
    }
  };

  // ChartLoader: garante que Chart.js esteja disponível e evita duplicação de script
  Utils.ChartLoader = {
    ensure: function(src) {
      return new Promise(function(resolve, reject) {
        if (typeof window.Chart !== 'undefined') { resolve(window.Chart); return; }
        var existing = document.querySelector('script[src*="chart.js"]');
        if (existing) {
          // Se já houver script, aguarda carregamento
          existing.addEventListener('load', function() {
            resolve(window.Chart);
          });
          existing.addEventListener('error', function() {
            reject(new Error('Falha ao carregar Chart.js'));
          });
          return;
        }
        var script = document.createElement('script');
        script.src = src || 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js';
        script.crossOrigin = 'anonymous';
        script.referrerPolicy = 'no-referrer';
        script.onload = function() { resolve(window.Chart); };
        script.onerror = function() { reject(new Error('Falha ao carregar Chart.js')); };
        document.head.appendChild(script);
      });
    }
  };

  // Inicialização e cleanup automático
  document.addEventListener('DOMContentLoaded', function() {
    try { console.log('Utils loaded successfully'); } catch(_){}
  });

  window.addEventListener('beforeunload', function() {
    Utils.cleanup();
  });

  // Exportar para uso global
  window.Utils = Utils;
  // Expor fetchWithRetry globalmente, sem sobrescrever se já existir
  if (typeof window.fetchWithRetry !== 'function') {
    window.fetchWithRetry = fetchWithRetry;
  }
  if (typeof module !== 'undefined' && module.exports) { module.exports = Utils; }
})();