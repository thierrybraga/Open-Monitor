(function() {
  'use strict';

  // Legacy entry point: mirror of report_list.v2.js to ensure compatibility

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

      // Datas: de/até
      var dateFrom = filterForm.querySelector('input[name="date_from"]');
      var dateTo = filterForm.querySelector('input[name="date_to"]');
      var df = dateFrom && dateFrom.value ? dateFrom.value : '';
      var dt = dateTo && dateTo.value ? dateTo.value : '';
      if (df || dt) {
        addChip('Período', (df && dt) ? (df + ' a ' + dt) : (df ? ('Desde ' + df) : ('Até ' + dt)), function() {
          if (dateFrom) dateFrom.value = '';
          if (dateTo) dateTo.value = '';
        });
      }
      } catch(err) {
        try { console.error('Erro ao atualizar chips de filtros:', err); } catch(_e){}
      }
    }

    // Chamar updateChips ao carregar
    try { updateChips(); } catch(err) { try { console.error('updateChips init falhou:', err); } catch(_e){} }

    // Bind para inputs quando auto-aplicar estiver ativo
    if (autoToggle) {
      autoToggle.addEventListener('change', function() {
        if (autoToggle.checked) {
          bindDebounce(400);
        } else {
          unbindDebounce();
        }
      });
      if (autoToggle.checked) bindDebounce(400);
    }

    // Intervalos rápidos
    if (quickRange) {
      quickRange.addEventListener('change', function() {
        var v = quickRange.value || ''; if (!v) return;
        var dateFrom = filterForm.querySelector('input[name="date_from"]');
        var dateTo = filterForm.querySelector('input[name="date_to"]');
        var now = new Date(); var start;
        try {
          if (v === '7d') start = new Date(now.getTime() - 7*24*60*60*1000);
          else if (v === '30d') start = new Date(now.getTime() - 30*24*60*60*1000);
          else if (v === '90d') start = new Date(now.getTime() - 90*24*60*60*1000);
          else start = null;
        } catch(_e) { start = null; }
        function fmt(d){
          try {
            var y = d.getFullYear(); var m = String(d.getMonth()+1).padStart(2,'0'); var da = String(d.getDate()).padStart(2,'0');
            return y + '-' + m + '-' + da;
          } catch(_e){ return ''; }
        }
        if (start && dateFrom) dateFrom.value = fmt(start);
        if (dateTo) dateTo.value = fmt(now);
        try { updateChips(); } catch(err) { try { console.error('updateChips após quickRange falhou:', err); } catch(_e){} }
        if (autoToggle && autoToggle.checked) submitForm();
      });
    }
  });

  // Otimizações para dispositivos móveis
  document.addEventListener('DOMContentLoaded', function() {
    try {
      // Colapsar filtros em mobile
      var filtersToggle = document.getElementById('filtersToggle');
      if (filtersToggle) {
        filtersToggle.addEventListener('click', function() {
          var filters = document.getElementById('filtersSection');
          if (filters) {
            var isHidden = filters.classList.contains('d-none');
            filters.classList.toggle('d-none');
            filtersToggle.setAttribute('aria-expanded', String(!isHidden));
          }
        });
      }

      // Melhorar acessibilidade
      var reportsTable = document.querySelector('.table.table-modern');
      if (reportsTable) {
        reportsTable.setAttribute('role', 'table');
        Array.prototype.forEach.call(reportsTable.querySelectorAll('thead th'), function(th){ th.setAttribute('role', 'columnheader'); });
        Array.prototype.forEach.call(reportsTable.querySelectorAll('tbody td'), function(td){ td.setAttribute('role', 'cell'); });
      }

    } catch(err) {
      try { console.debug('Mobile optimizations: fallback sem ajuste de auto-refresh', err); } catch(_e){}
    }
  });

})();