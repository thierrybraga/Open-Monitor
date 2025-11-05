// home.js - Entry consolidado da Home
// Unifica lógica de:
// - Aplicar vendor_ids da seleção salva à URL (se ausente)
// - Carregar dashboard.js quando Chart.js estiver disponível
// - Controlar mudança de itens por página
// - Popular "Vulnerabilidades Recentes" com filtro por vendors

(function () {
  // ===== Vendor IDs na URL a partir do localStorage (se não houver na URL) =====
  function applySavedVendorIdsToUrlIfMissing() {
    try {
      var url = new URL(window.location.href);
      var hasVendorParam = url.searchParams.has('vendor_ids');
      if (hasVendorParam) return;
      var raw = localStorage.getItem('vendorSelection.selectedVendorIds');
      if (!raw) return;
      var ids = [];
      try { ids = JSON.parse(raw) || []; } catch (e) { ids = []; }
      ids = ids.map(function (x) { return parseInt(x, 10); }).filter(function (n) { return Number.isFinite(n); });
      if (!ids.length) return;
      url.searchParams.set('vendor_ids', ids.join(','));
      window.location.replace(url.toString());
    } catch (e) {
      console.warn('Falha ao aplicar vendor_ids da seleção salva:', e);
    }
  }

  // ===== Dashboard loader (dependente de Chart.js) =====
  function loadDashboardIfChartAvailable() {
    try {
      if (typeof Chart !== 'undefined') {
        var dashboardScript = document.createElement('script');
        dashboardScript.src = '/static/js/pages/dashboard.js';
        dashboardScript.onload = function () { console.log('Dashboard.js carregado com sucesso'); };
        dashboardScript.onerror = function () { console.error('Erro ao carregar dashboard.js'); };
        document.head.appendChild(dashboardScript);
      } else {
        console.error('Chart.js não está disponível');
      }
    } catch (e) {
      console.error('Falha ao avaliar/ carregar dashboard:', e);
    }
  }

  // ===== Handler de mudança de itens por página =====
  function setupPageSizeHandler() {
    var pageSizeSelect = document.getElementById('vulnerabilities-page-size');
    if (!pageSizeSelect) return;
    pageSizeSelect.addEventListener('change', function () {
      var params = new URLSearchParams(window.location.search);
      params.set('per_page', this.value);
      params.set('page', 1);
      window.location.search = params.toString();
    });
  }

  // ===== Helpers de vendor_ids =====
  function getVendorIdsFromUrl() {
    try {
      var params = new URLSearchParams(window.location.search || '');
      var multi = params.getAll('vendor_ids');
      var ids = [];
      if (multi && multi.length) {
        multi.forEach(function (v) {
          String(v).split(',').forEach(function (p) {
            var n = parseInt(p.trim(), 10);
            if (!isNaN(n)) ids.push(n);
          });
        });
      }
      var single = params.get('vendor');
      if (single) {
        String(single).split(',').forEach(function (p) {
          var n = parseInt(p.trim(), 10);
          if (!isNaN(n)) ids.push(n);
        });
      }
      return Array.from(new Set(ids)).sort(function (a, b) { return a - b; });
    } catch (_) { return []; }
  }

  function getVendorIdsFromLocalStorage() {
    try {
      var raw = localStorage.getItem('vendorSelection.selectedVendorIds');
      if (!raw) return [];
      var arr = JSON.parse(raw);
      if (!Array.isArray(arr)) return [];
      var ids = [];
      arr.forEach(function (v) {
        var n = parseInt(String(v).trim(), 10);
        if (!isNaN(n)) ids.push(n);
      });
      return Array.from(new Set(ids)).sort(function (a, b) { return a - b; });
    } catch (_) { return []; }
  }

  function buildVendorParam(prefix) {
    var urlVendorIds = getVendorIdsFromUrl();
    var effectiveIds = (urlVendorIds && urlVendorIds.length) ? urlVendorIds : getVendorIdsFromLocalStorage();
    return (effectiveIds && effectiveIds.length) ? String(prefix || '?') + 'vendor_ids=' + effectiveIds.join(',') : '';
  }

  function appendVendorToUrl(href) {
    try {
      var ids = getVendorIdsFromUrl();
      var eff = ids.length ? ids : getVendorIdsFromLocalStorage();
      if (!eff.length) return href;
      var url = new URL(href, window.location.origin);
      url.searchParams.set('vendor_ids', eff.join(','));
      return url.toString();
    } catch (_) { return href; }
  }

  // ===== UI helpers =====
  function severityBadge(severity) {
    var sev = String(severity || '').toUpperCase();
    var map = {
      'CRITICAL': { cls: 'critical', text: 'CRITICAL', icon: 'bi-exclamation-octagon-fill' },
      'HIGH': { cls: 'high', text: 'HIGH', icon: 'bi-exclamation-triangle-fill' },
      'MEDIUM': { cls: 'medium', text: 'MEDIUM', icon: 'bi-info-circle-fill' },
      'LOW': { cls: 'low', text: 'LOW', icon: 'bi-info-circle' },
      'N/A': { cls: 'n/a', text: 'Não Avaliado', icon: 'bi-question-circle-fill' },
      'NONE': { cls: 'none', text: 'Nenhuma', icon: 'bi-dash-circle' }
    };
    var m = map[sev] || map['N/A'];
    return '<span class="severity-badge ' + m.cls + '" title="Severidade: ' + m.text + '"><i class="bi ' + m.icon + '"></i> ' + m.text + '</span>';
  }

  function cvssBadge(score) {
    if (score == null || isNaN(parseFloat(score))) {
      return '<span class="cvss-score unknown" title="Pontuação CVSS: Não Avaliado" aria-label="Pontuação CVSS não avaliada">N/A</span>';
    }
    var s = parseFloat(score);
    var cls = (s >= 9.0) ? 'critical' : (s >= 7.0) ? 'high' : (s >= 4.0) ? 'medium' : 'low';
    return '<span class="cvss-score ' + cls + '" title="Pontuação CVSS: ' + s + '" aria-label="Pontuação CVSS ' + s + '">' + s + '</span>';
  }

  function formatDate(iso) {
    try { var d = new Date(iso); return d.toLocaleDateString('pt-BR'); } catch (_) { return '-'; }
  }

  // ===== Carregamento de CVEs recentes =====
  async function loadLatestCVEs() {
    // Suporta dois layouts diferentes da Home (page.html e pages/index.html)
    var tbody = document.getElementById('home-latest-cves-body');
    var layout = 'rich'; // 6 colunas, com descrição e ações
    if (!tbody) {
      var altTbody = document.querySelector('#vulnerabilities-table tbody');
      if (!altTbody) return;
      tbody = altTbody;
      layout = 'compact'; // 4 colunas, sem descrição e ações
    }
    var apiUrl = new URL('/api/analytics/latest-cves', window.location.origin);
    apiUrl.searchParams.set('page', '1');
    apiUrl.searchParams.set('per_page', '10');
    // Determinar vendor_ids efetivos a partir da URL ou do localStorage
    var effectiveIds = getVendorIdsFromUrl();
    if (!effectiveIds || !effectiveIds.length) {
      effectiveIds = getVendorIdsFromLocalStorage();
    }
    // Renderiza um hint visual do escopo de vendors ativo
    try {
      var subtitleEl = document.querySelector('.recent-vulnerabilities-section .section-subtitle');
      if (subtitleEl) {
        var existing = document.getElementById('vendor-scope-hint');
        var hintText = (effectiveIds && effectiveIds.length)
          ? 'Filtrando por vendors (IDs): ' + effectiveIds.join(', ')
          : 'Sem filtro de vendors ativo';
        var html = '<span id="vendor-scope-hint" class="text-muted small ms-2">' + hintText + '</span>';
        if (existing) { existing.outerHTML = html; } else { subtitleEl.insertAdjacentHTML('beforeend', html); }
      }
    } catch (_e) { /* noop */ }
    // Logs de debug para diagnóstico
    try {
      console.debug('[Home] vendor_ids efetivos:', effectiveIds);
    } catch (_e2) { /* noop */ }
    if (effectiveIds && effectiveIds.length) {
      apiUrl.searchParams.set('vendor_ids', effectiveIds.join(','));
    }
    try { console.debug('[Home] URL da API latest-cves:', apiUrl.toString()); } catch (_e3) { /* noop */ }

    async function fetchOnce(urlObj) {
      var resp = await fetch(urlObj.toString(), { credentials: 'include' });
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      return resp.json();
    }

    try {
      var result = await fetchOnce(apiUrl);
      var data = Array.isArray(result.data) ? result.data : [];
      if (!data.length) {
        var colspanEmpty = (layout === 'rich') ? 6 : 4;
        tbody.innerHTML = '<tr><td colspan="' + colspanEmpty + '" class="text-center text-muted">Nenhuma CVE encontrada para os vendors selecionados</td></tr>';
        // Atualiza link "Ver todas" para propagar vendor_ids
        var allLinkEmpty = document.querySelector('.recent-vulnerabilities-section .section-action') ||
                           document.querySelector('section[aria-labelledby="recent-title"] a.btn.btn-sm.btn-outline-secondary');
        if (allLinkEmpty) {
          allLinkEmpty.setAttribute('href', appendVendorToUrl(allLinkEmpty.getAttribute('href') || '/vulnerabilities/'));
        }
        return;
      }
      var rowsHtml = '';
      if (layout === 'rich') {
        rowsHtml = data.map(function (item) {
          var refUrl = item.reference_url || '#';
          var cveId = item.cve_id || '';
          var desc = String(item.description || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
          var pub = formatDate(item.published_date);
          var sev = severityBadge(item.base_severity);
          var cvss = cvssBadge(item.cvss_score);
          var detailsHref = appendVendorToUrl('/vulnerabilities/' + cveId);
          return (
            '<tr>\n' +
            '  <th scope="row">\n' +
            '    <a href="' + refUrl + '" target="_blank" rel="noopener noreferrer" class="cve-link" aria-label="Abrir referência ' + cveId + ' em nova aba">\n' +
            '      <span class="cve-badge">' + cveId + '</span>\n' +
            '    </a>\n' +
            '  </th>\n' +
            '  <td>' + sev + '</td>\n' +
            '  <td class="d-none d-md-table-cell">\n' +
            '    <p class="vulnerability-description mb-0">' + desc + '</p>\n' +
            '  </td>\n' +
            '  <td><span class="date-text">' + pub + '</span></td>\n' +
            '  <td>' + cvss + '</td>\n' +
            '  <td class="text-center">\n' +
            '    <a href="' + detailsHref + '" class="btn btn-sm btn-outline-primary" title="Ver detalhes" aria-label="Ver detalhes de ' + cveId + '">\n' +
            '      <i class="bi bi-eye"></i>\n' +
            '    </a>\n' +
            '  </td>\n' +
            '</tr>'
          );
        }).join('');
      } else {
        // compact: 4 colunas (CVE, Severidade, CVSS, Publicado)
        rowsHtml = data.map(function (item) {
          var cveId = item.cve_id || '';
          var sev = severityBadge(item.base_severity);
          var cvss = cvssBadge(item.cvss_score);
          var pub = formatDate(item.published_date);
          var detailsHref = appendVendorToUrl('/vulnerabilities/' + cveId);
          return (
            '<tr>\n' +
            '  <td><a href="' + detailsHref + '" class="text-decoration-none">' + cveId + '</a></td>\n' +
            '  <td>' + sev + '</td>\n' +
            '  <td>' + cvss + '</td>\n' +
            '  <td>' + pub + '</td>\n' +
            '</tr>'
          );
        }).join('');
      }
      tbody.innerHTML = rowsHtml;
      var allLink = document.querySelector('.recent-vulnerabilities-section .section-action') ||
                    document.querySelector('section[aria-labelledby="recent-title"] a.btn.btn-sm.btn-outline-secondary');
      if (allLink) {
        allLink.setAttribute('href', appendVendorToUrl(allLink.getAttribute('href') || '/vulnerabilities/'));
      }
    } catch (e) {
      console.warn('Falha ao carregar CVEs na Home:', e);
      try {
        await new Promise(function (res) { return setTimeout(res, 300); });
        var result2 = await fetchOnce(apiUrl);
        var data2 = Array.isArray(result2.data) ? result2.data : [];
        if (!data2.length) {
          var colspanRetry = (layout === 'rich') ? 6 : 4;
          tbody.innerHTML = '<tr><td colspan="' + colspanRetry + '" class="text-center text-muted">Nenhuma CVE encontrada para os vendors selecionados</td></tr>';
          var allLinkRetryEmpty = document.querySelector('.recent-vulnerabilities-section .section-action') ||
                                  document.querySelector('section[aria-labelledby="recent-title"] a.btn.btn-sm.btn-outline-secondary');
          if (allLinkRetryEmpty) {
            allLinkRetryEmpty.setAttribute('href', appendVendorToUrl(allLinkRetryEmpty.getAttribute('href') || '/vulnerabilities/'));
          }
          return;
        }
        var rowsHtml2 = '';
        if (layout === 'rich') {
          rowsHtml2 = data2.map(function (item) {
            var refUrl = item.reference_url || '#';
            var cveId = item.cve_id || '';
            var desc = String(item.description || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            var pub = formatDate(item.published_date);
            var sev = severityBadge(item.base_severity);
            var cvss = cvssBadge(item.cvss_score);
            var detailsHref = appendVendorToUrl('/vulnerabilities/' + cveId);
            return (
              '<tr>\n' +
              '  <th scope="row">\n' +
              '    <a href="' + refUrl + '" target="_blank" rel="noopener noreferrer" class="cve-link" aria-label="Abrir referência ' + cveId + ' em nova aba">\n' +
              '      <span class="cve-badge">' + cveId + '</span>\n' +
              '    </a>\n' +
              '  </th>\n' +
              '  <td>' + sev + '</td>\n' +
              '  <td class="d-none d-md-table-cell">\n' +
              '    <p class="vulnerability-description mb-0">' + desc + '</p>\n' +
              '  </td>\n' +
              '  <td><span class="date-text">' + pub + '</span></td>\n' +
              '  <td>' + cvss + '</td>\n' +
              '  <td class="text-center">\n' +
              '    <a href="' + detailsHref + '" class="btn btn-sm btn-outline-primary" title="Ver detalhes" aria-label="Ver detalhes de ' + cveId + '">\n' +
              '      <i class="bi bi-eye"></i>\n' +
              '    </a>\n' +
              '  </td>\n' +
              '</tr>'
            );
          }).join('');
        } else {
          rowsHtml2 = data2.map(function (item) {
            var cveId = item.cve_id || '';
            var sev = severityBadge(item.base_severity);
            var cvss = cvssBadge(item.cvss_score);
            var pub = formatDate(item.published_date);
            var detailsHref = appendVendorToUrl('/vulnerabilities/' + cveId);
            return (
              '<tr>\n' +
              '  <td><a href="' + detailsHref + '" class="text-decoration-none">' + cveId + '</a></td>\n' +
              '  <td>' + sev + '</td>\n' +
              '  <td>' + cvss + '</td>\n' +
              '  <td>' + pub + '</td>\n' +
              '</tr>'
            );
          }).join('');
        }
        tbody.innerHTML = rowsHtml2;
        var allLink2 = document.querySelector('.recent-vulnerabilities-section .section-action') ||
                       document.querySelector('section[aria-labelledby="recent-title"] a.btn.btn-sm.btn-outline-secondary');
        if (allLink2) {
          allLink2.setAttribute('href', appendVendorToUrl(allLink2.getAttribute('href') || '/vulnerabilities/'));
        }
      } catch (e2) {
        console.warn('Retry falhou ao carregar CVEs na Home:', e2);
      }
    }
  }

  // ===== Init =====
  document.addEventListener('DOMContentLoaded', function () {
    // Evitar carregar antes de possível redirecionamento por vendor_ids
    setTimeout(function () {
      loadLatestCVEs();
      loadDashboardIfChartAvailable();
      setupPageSizeHandler();
    }, 200);
  });

  // Aplicar vendor_ids imediatamente (antes do restante)
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { applySavedVendorIdsToUrlIfMissing(); }, { once: true });
  } else {
    applySavedVendorIdsToUrlIfMissing();
  }
})();