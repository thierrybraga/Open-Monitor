(function() {
  'use strict';

  // Auto-refresh quando há relatórios em processamento
  document.addEventListener('DOMContentLoaded', function() {
    try {
      var content = document.getElementById('reportsContent');
      var hasProcessing = content && content.getAttribute('data-has-processing') === 'true';
      if (hasProcessing) {
        setTimeout(function() { location.reload(); }, 30000);
      }
    } catch (_e) { /* noop */ }
  });

  // Elementos do loading
  document.addEventListener('DOMContentLoaded', function() {
    var loadingSkeleton = document.getElementById('reportsLoadingSkeleton');
    var reportsContent = document.getElementById('reportsContent');
    
    // Função para mostrar loading
    function showLoading() {
      if (loadingSkeleton && reportsContent) {
        loadingSkeleton.classList.remove('d-none');
        reportsContent.classList.add('d-none');
      }
    }
    
    // Função para esconder loading
    function hideLoading() {
      if (loadingSkeleton && reportsContent) {
        loadingSkeleton.classList.add('d-none');
        reportsContent.classList.remove('d-none');
      }
    }
    
    // Interceptar cliques em links de paginação para loading assíncrono
    Array.prototype.forEach.call(document.querySelectorAll('.pagination a'), function(link) {
      link.addEventListener('click', function(e) {
        e.preventDefault();
        showLoading();
        
        // Simular delay mínimo para mostrar o skeleton
        setTimeout(function() {
          window.location.href = link.href;
        }, 300);
      });
    });
    
    // Interceptar submissão de formulários de filtro
    var filterForm = document.querySelector('form[method="GET"]');
    if (filterForm) {
      filterForm.addEventListener('submit', function(_e) {
        showLoading();
        // Permitir que o formulário seja submetido normalmente
      });
    }
    
    
    // Confirmação para ações destrutivas
    Array.prototype.forEach.call(document.querySelectorAll('form[action*="delete"]'), function(form) {
      form.addEventListener('submit', function(e) {
        if (!confirm('Tem certeza que deseja deletar este relatório?')) {
          e.preventDefault();
        } else {
          showLoading();
        }
      });
    });
    
    Array.prototype.forEach.call(document.querySelectorAll('form[action*="regenerate"]'), function(form) {
      form.addEventListener('submit', function(e) {
        if (!confirm('Tem certeza que deseja regenerar este relatório?')) {
          e.preventDefault();
        } else {
          showLoading();
        }
      });
    });
    
    // Lazy loading para imagens e conteúdo pesado
    if ('IntersectionObserver' in window) {
      var lazyElements = document.querySelectorAll('[data-lazy]');
      var lazyObserver = new IntersectionObserver(function(entries) {
        Array.prototype.forEach.call(entries, function(entry) {
          if (entry.isIntersecting) {
            var element = entry.target;
            if (element.dataset.lazy === 'chart') {
              // Carregar gráficos sob demanda
              loadChart(element);
            }
            lazyObserver.unobserve(element);
          }
        });
      });
      
      Array.prototype.forEach.call(lazyElements, function(element) {
        lazyObserver.observe(element);
      });
    }
    
    // Cache simples para relatórios
    var reportCache = new Map();
    
    // Função para cache de relatórios
    function cacheReport(reportId, data) {
      reportCache.set(reportId, {
        data: data,
        timestamp: Date.now()
      });
    }
    
    // Função para recuperar do cache (válido por 5 minutos)
    function getCachedReport(reportId) {
      var cached = reportCache.get(reportId);
      if (cached && (Date.now() - cached.timestamp) < 300000) {
        return cached.data;
      }
      return null;
    }
    
    // Indicador de progresso para relatórios em processamento
    var processingReports = document.querySelectorAll('.badge-warning');
    if (processingReports.length > 0) {
      // Adicionar indicador visual de progresso
      Array.prototype.forEach.call(processingReports, function(badge) {
        if (badge.textContent.indexOf('Processando') !== -1) {
          badge.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>Processando...';
          badge.classList.add('progress-indicator');
        }
      });
    }
  });

  // Função para carregar gráficos sob demanda
  function loadChart(element) {
    // Implementar carregamento de gráficos quando necessário
    try { console.log('Carregando gráfico para:', element); } catch(_e){}
  }

  // Melhorias de UX dos filtros: Auto aplicar, chips ativos e intervalo rápido
  document.addEventListener('DOMContentLoaded', function() {
    var filterForm = document.querySelector('form[method="GET"]');
    var autoToggle = document.getElementById('autoApplyToggle');
    var quickRange = document.getElementById('quickRange');
    var chips = document.getElementById('activeFiltersChips');

    if (!filterForm) return;

    var inputs = filterForm.querySelectorAll('input[type="text"], select, input[type="date"]');

    function submitForm() { filterForm.submit(); }

    function bindDebounce(wait) {
      Array.prototype.forEach.call(inputs, function(input) {
        var key = 'reports-filter-' + (input.name || input.id || 'field');
        var handler = (window.Utils && Utils.debounce) ? Utils.debounce(submitForm, wait, key) : function() {
          var self = this, args = arguments; setTimeout(function(){ submitForm.apply(self, args); }, wait);
        };
        if (input._debouncedSubmitHandler) {
          input.removeEventListener('input', input._debouncedSubmitHandler);
        }
        input.addEventListener('input', handler);
        input._debouncedSubmitHandler = handler;
      });
    }

    function unbindDebounce() {
      Array.prototype.forEach.call(inputs, function(input) {
        if (input._debouncedSubmitHandler) {
          input.removeEventListener('input', input._debouncedSubmitHandler);
          input._debouncedSubmitHandler = null;
        }
      });
    }

    function updateChips() {
      try {
      if (!chips) return;
      chips.innerHTML = '';
      function addChip(label, value, clearCallback) {
        if (!value) return;
        var chip = document.createElement('span');
        chip.className = 'badge bg-info text-dark d-flex align-items-center gap-1';
        chip.setAttribute('role', 'listitem');
        chip.setAttribute('aria-label', 'Filtro ativo: ' + label + ' - ' + value);
        chip.innerHTML = '<i class="bi bi-filter"></i>' + label + ': ' + value + ' <button type="button" class="btn btn-sm btn-link text-dark p-0 ms-1"><i class="bi bi-x"></i></button>';
        var btn = chip.querySelector('button');
        btn.setAttribute('aria-label', 'Remover filtro ' + label + ' (' + value + ')');
        btn.addEventListener('click', function() {
          if (clearCallback) clearCallback();
          if (autoToggle && autoToggle.checked) submitForm();
          updateChips();
        });
        chips.appendChild(chip);
      }

      // Helper removido: usar textos diretamente dos inputs/options ao montar chips

      // Report Type: suporta <select> e múltiplos checkboxes
      var typeSelect = filterForm.querySelector('select[name="report_type"]');
      var checkedTypes = filterForm.querySelectorAll('input[name="report_type"]:checked');
      if (typeSelect) {
        var typeTxt = '';
        if (typeSelect.multiple) {
          var tSelected = Array.prototype.filter.call(typeSelect.options || [], function(opt){ return opt.selected; });
          typeTxt = Array.prototype.map.call(tSelected, function(opt){ return opt.text; }).join(', ');
        } else {
          var tIdx = (typeof typeSelect.selectedIndex === 'number') ? typeSelect.selectedIndex : -1;
          typeTxt = (typeSelect.options && tIdx >= 0 && typeSelect.options[tIdx]) ? typeSelect.options[tIdx].text : (typeSelect.value || '');
        }
        if (typeTxt) {
          addChip('Tipo', typeTxt, function() {
            if (typeSelect.multiple) {
              Array.prototype.forEach.call(typeSelect.options || [], function(opt){ opt.selected = false; });
            } else {
              typeSelect.selectedIndex = -1;
              typeSelect.value = '';
            }
          });
        }
      } else if (checkedTypes.length) {
        var typeLabels = Array.prototype.map.call(checkedTypes, function(inp) { return (inp.value || inp.id || '').trim(); });
        addChip('Tipo', typeLabels.join(', '), function() { Array.prototype.forEach.call(checkedTypes, function(inp){ inp.checked = false; }); });
      }

      // Status: suporta <select> e múltiplos checkboxes
      var statusSelect = filterForm.querySelector('select[name="status"]');
      var checkedStatus = filterForm.querySelectorAll('input[name="status"]:checked');
      if (statusSelect) {
        var statusTxt = '';
        if (statusSelect.multiple) {
          var sSelected = Array.prototype.filter.call(statusSelect.options || [], function(opt){ return opt.selected; });
          statusTxt = Array.prototype.map.call(sSelected, function(opt){ return opt.text; }).join(', ');
        } else {
          var sIdx = (typeof statusSelect.selectedIndex === 'number') ? statusSelect.selectedIndex : -1;
          statusTxt = (statusSelect.options && sIdx >= 0 && statusSelect.options[sIdx]) ? statusSelect.options[sIdx].text : (statusSelect.value || '');
        }
        if (statusTxt) {
          addChip('Status', statusTxt, function() {
            if (statusSelect.multiple) {
              Array.prototype.forEach.call(statusSelect.options || [], function(opt){ opt.selected = false; });
            } else {
              statusSelect.selectedIndex = -1;
              statusSelect.value = '';
            }
          });
        }
      } else if (checkedStatus.length) {
        var sLabels = Array.prototype.map.call(checkedStatus, function(inp) { return (inp.value || inp.id || '').trim(); });
        addChip('Status', sLabels.join(', '), function() { Array.prototype.forEach.call(checkedStatus, function(inp){ inp.checked = false; }); });
      }

      var fromInput = filterForm.querySelector('[name="date_from"]');
      var toInput = filterForm.querySelector('[name="date_to"]');
      function formatDate(val) { return val ? new Date(val).toLocaleDateString() : ''; }
      if ((fromInput && fromInput.value) || (toInput && toInput.value)) {
        var label = 'Período';
        var val = (formatDate(fromInput ? fromInput.value : '') + (toInput && toInput.value ? ' → ' + formatDate(toInput.value) : '')).trim();
        addChip(label, val, function() { if (fromInput) fromInput.value = ''; if (toInput) toInput.value = ''; });
      }
      } catch (err) {
        try { console.warn('updateChips falhou:', err); } catch(_){}
      }
    }

    // Persistência do estado de Auto aplicar no localStorage
    var savedAuto = null;
    try { savedAuto = localStorage.getItem('reports:autoApply'); } catch(_e){}
    if (autoToggle && savedAuto !== null) {
      autoToggle.checked = (savedAuto === 'true');
    }

    // Inicialização conforme alternador Auto aplicar
    if (autoToggle && autoToggle.checked) { bindDebounce(500); } else { unbindDebounce(); }

    if (autoToggle) {
      autoToggle.addEventListener('change', function() {
        try { localStorage.setItem('reports:autoApply', String(autoToggle.checked)); } catch(_e){}
        if (autoToggle.checked) {
          bindDebounce(500);
          submitForm();
        } else {
          unbindDebounce();
        }
      });
    }

    // Intervalo rápido
    if (quickRange) {
      quickRange.addEventListener('change', function() {
        var fromInput = filterForm.querySelector('[name="date_from"]');
        var toInput = filterForm.querySelector('[name="date_to"]');
        var now = new Date();
        var start = null, end = null;
        function toISODate(d) { return [d.getFullYear(), String(d.getMonth()+1).padStart(2,'0'), String(d.getDate()).padStart(2,'0')].join('-'); }
        switch (quickRange.value) {
          case 'today':
            start = new Date(now); end = new Date(now); break;
          case 'last7':
            start = new Date(now); start.setDate(start.getDate()-7); end = new Date(now); break;
          case 'last30':
            start = new Date(now); start.setDate(start.getDate()-30); end = new Date(now); break;
          case 'thisMonth':
            start = new Date(now.getFullYear(), now.getMonth(), 1);
            end = new Date(now.getFullYear(), now.getMonth()+1, 0);
            break;
          case 'last90':
            start = new Date(now); start.setDate(start.getDate()-90); end = new Date(now); break;
          default:
            start = null; end = null;
        }
        if (fromInput) fromInput.value = start ? toISODate(start) : '';
        if (toInput) toInput.value = end ? toISODate(end) : '';
        try { updateChips(); } catch(e) { try { console.warn('updateChips falhou (quickRange):', e); } catch(_e){} }
        if (autoToggle && autoToggle.checked) submitForm();
      });
    }

    Array.prototype.forEach.call(inputs, function(input) {
      input.addEventListener('change', function(){ try { updateChips(); } catch(e) { try { console.warn('updateChips falhou (input change):', e); } catch(_e){} } });
    });
    try { updateChips(); } catch(e) { try { console.warn('updateChips falhou (init):', e); } catch(_e){} }

    // Atualizar ícone de collapse no cabeçalho
    var collapseBtn = document.querySelector('[data-bs-target="#advancedFiltersBody"]');
    var collapseArea = document.getElementById('advancedFiltersBody');
    if (collapseBtn && collapseArea) {
      collapseArea.addEventListener('shown.bs.collapse', function() {
        var icon = collapseBtn.querySelector('i');
        if (icon && icon.classList) { icon.classList.replace('bi-chevron-down','bi-chevron-up'); }
        // Foco adequado ao expandir: primeiro campo do formulário
        var firstInput = filterForm.querySelector('select, input');
        if (firstInput) firstInput.focus();
      });
      collapseArea.addEventListener('hidden.bs.collapse', function() {
        var icon = collapseBtn.querySelector('i');
        if (icon && icon.classList) { icon.classList.replace('bi-chevron-up','bi-chevron-down'); }
        // Foco retorna para o botão de colapsar
        collapseBtn.focus();
      });
    }

    // Botão: Limpar apenas datas
    var clearDateBtn = document.getElementById('clearDateBtn');
    if (clearDateBtn) {
      clearDateBtn.addEventListener('click', function() {
        var fromInput2 = filterForm.querySelector('[name="date_from"]');
        var toInput2 = filterForm.querySelector('[name="date_to"]');
        if (fromInput2) fromInput2.value = '';
        if (toInput2) toInput2.value = '';
        if (quickRange) quickRange.value = '';
        try { updateChips(); } catch(e) { try { console.warn('updateChips falhou (clear dates):', e); } catch(_e){} }
        if (autoToggle && autoToggle.checked) submitForm();
      });
    }
  });

  // Otimizações para mobile e performance
  function initMobileOptimizations() {
    // Detectar se é dispositivo móvel
    var isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    
    if (isMobile) {
      // Otimizar touch events
      document.addEventListener('touchstart', function() {}, { passive: true });
      document.addEventListener('touchmove', function() {}, { passive: true });
      
      // Reduzir frequência de auto-refresh em mobile (verificação segura)
      try {
        var scripts = Array.prototype.slice.call(document.querySelectorAll('script'));
        var autoRefreshScript = scripts.find(function(s) {
          var txt = s.textContent || '';
          return txt.indexOf('setTimeout') !== -1 && txt.indexOf('location.reload') !== -1;
        });
        if (autoRefreshScript && autoRefreshScript.textContent.indexOf('30000') !== -1) {
          // Nota: alterar o conteúdo do script após execução não reprograma o timer já agendado,
          // mas evita erro de seletor e mantém compatibilidade.
          autoRefreshScript.textContent = autoRefreshScript.textContent.replace(/30000/g, '60000');
        }
      } catch (err) {
        // Ignorar silenciosamente para evitar erros em navegadores sem suporte
        try { console.debug('Mobile optimizations: fallback sem ajuste de auto-refresh', err); } catch(_e){}
      }
    }
    
    // Detectar conexão lenta
    if ('connection' in navigator) {
      var connection = navigator.connection;
      if (connection.effectiveType === 'slow-2g' || connection.effectiveType === '2g') {
        // Desabilitar animações em conexões lentas
        document.documentElement.style.setProperty('--animation-duration', '0s');
        
        // Aumentar debounce para filtros (apenas quando Auto aplicar estiver ativo)
        var autoToggle = document.getElementById('autoApplyToggle');
        var filterForm = document.querySelector('form[method="GET"]');
        if (autoToggle && autoToggle.checked && filterForm) {
          var inputs = filterForm.querySelectorAll('input[type="text"], select, input[type="date"]');
          Array.prototype.forEach.call(inputs, function(input) {
            var slowKey = 'reports-filter-slow-' + (input.name || input.id || 'field');
            var slowHandler = (window.Utils && Utils.debounce) ? Utils.debounce(function() { filterForm.submit(); }, 1000, slowKey) : function() {
              var self = this, args = arguments; setTimeout(function(){ filterForm.submit.apply(self, args); }, 1000);
            };
            if (input._debouncedSubmitHandler) {
              input.removeEventListener('input', input._debouncedSubmitHandler);
            }
            input.addEventListener('input', slowHandler);
            input._debouncedSubmitHandler = slowHandler;
          });
        }
      }
    }
    
    // Otimizar scroll performance
    var ticking = false;
    function updateScrollPosition() {
      // Implementar virtual scrolling se necessário
      ticking = false;
    }
    
    document.addEventListener('scroll', function() {
      if (!ticking) {
        requestAnimationFrame(updateScrollPosition);
        ticking = true;
      }
    }, { passive: true });
  }

  // Inicializar otimizações mobile
  initMobileOptimizations();
})();