// home-latest-cves.js
// Popula a tabela de "Vulnerabilidades Recentes" na Home com CVEs
// filtradas pelos vendors selecionados (URL tem prioridade; fallback localStorage)

(function () {
  function getVendorIdsFromUrl() {
    try {
      const params = new URLSearchParams(window.location.search || '');
      const multi = params.getAll('vendor_ids');
      let ids = [];
      if (multi && multi.length) {
        multi.forEach(v => {
          const parts = String(v).split(',');
          parts.forEach(p => {
            const n = parseInt(p.trim(), 10);
            if (!isNaN(n)) ids.push(n);
          });
        });
      }
      const single = params.get('vendor');
      if (single) {
        const parts2 = String(single).split(',');
        parts2.forEach(p => {
          const n = parseInt(p.trim(), 10);
          if (!isNaN(n)) ids.push(n);
        });
      }
      return Array.from(new Set(ids)).sort((a, b) => a - b);
    } catch (_) {
      return [];
    }
  }

  function getVendorIdsFromLocalStorage() {
    try {
      const raw = localStorage.getItem('vendorSelection.selectedVendorIds');
      if (!raw) return [];
      const arr = JSON.parse(raw);
      if (!Array.isArray(arr)) return [];
      const ids = [];
      arr.forEach(v => {
        const n = parseInt(String(v).trim(), 10);
        if (!isNaN(n)) ids.push(n);
      });
      return Array.from(new Set(ids)).sort((a, b) => a - b);
    } catch (_) {
      return [];
    }
  }

  function buildVendorParam(prefix = '?') {
    const urlVendorIds = getVendorIdsFromUrl();
    const effectiveIds = (urlVendorIds && urlVendorIds.length)
      ? urlVendorIds
      : getVendorIdsFromLocalStorage();
    return (effectiveIds && effectiveIds.length)
      ? `${prefix}vendor_ids=${effectiveIds.join(',')}`
      : '';
  }

  function severityBadge(severity) {
    const sev = String(severity || '').toUpperCase();
    const map = {
      'CRITICAL': { cls: 'critical', text: 'CRITICAL', icon: 'bi-exclamation-octagon-fill' },
      'HIGH': { cls: 'high', text: 'HIGH', icon: 'bi-exclamation-triangle-fill' },
      'MEDIUM': { cls: 'medium', text: 'MEDIUM', icon: 'bi-info-circle-fill' },
      'LOW': { cls: 'low', text: 'LOW', icon: 'bi-info-circle' },
      'N/A': { cls: 'n/a', text: 'Não Avaliado', icon: 'bi-question-circle-fill' },
      'NONE': { cls: 'none', text: 'Nenhuma', icon: 'bi-dash-circle' }
    };
    const m = map[sev] || map['N/A'];
    return `<span class="severity-badge ${m.cls}" title="Severidade: ${m.text}"><i class="bi ${m.icon}"></i> ${m.text}</span>`;
  }

  function cvssBadge(score) {
    if (score == null || isNaN(parseFloat(score))) {
      return `<span class="cvss-score unknown" title="Pontuação CVSS: Não Avaliado" aria-label="Pontuação CVSS não avaliada">N/A</span>`;
    }
    const s = parseFloat(score);
    const cls = (s >= 9.0) ? 'critical' : (s >= 7.0) ? 'high' : (s >= 4.0) ? 'medium' : 'low';
    return `<span class="cvss-score ${cls}" title="Pontuação CVSS: ${s}" aria-label="Pontuação CVSS ${s}">${s}</span>`;
  }

  function formatDate(iso) {
    try {
      const d = new Date(iso);
      return d.toLocaleDateString('pt-BR');
    } catch (_) { return '-'; }
  }

  function appendVendorToUrl(href) {
    try {
      const ids = getVendorIdsFromUrl();
      const eff = ids.length ? ids : getVendorIdsFromLocalStorage();
      if (!eff.length) return href;
      const url = new URL(href, window.location.origin);
      url.searchParams.set('vendor_ids', eff.join(','));
      return url.toString();
    } catch (_) { return href; }
  }

  async function loadLatestCVEs() {
    const tbody = document.getElementById('home-latest-cves-body');
    if (!tbody) return;
    const vendorParam = buildVendorParam('?');
    const apiUrl = new URL('/api/analytics/latest-cves', window.location.origin);
    apiUrl.searchParams.set('page', '1');
    apiUrl.searchParams.set('per_page', '10');
    if (vendorParam) {
      // vendorParam começa com '?vendor_ids=...'
      const ids = vendorParam.replace('?vendor_ids=', '');
      apiUrl.searchParams.set('vendor_ids', ids);
    }

    async function fetchOnce(urlObj) {
      const resp = await fetch(urlObj.toString(), { credentials: 'include' });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return resp.json();
    }

    try {
      const result = await fetchOnce(apiUrl);
      const data = Array.isArray(result.data) ? result.data : [];

      // Só limpar a tabela quando tivermos dados ou confirmação de vazio
      if (!data.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">Nenhuma CVE encontrada para os vendors selecionados</td></tr>`;
        return;
      }

      const rowsHtml = data.map(item => {
        const refUrl = item.reference_url || '#';
        const cveId = item.cve_id || '';
        const desc = (item.description || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        const pub = formatDate(item.published_date);
        const sev = severityBadge(item.severity);
        const cvss = cvssBadge(item.cvss_score);
        const detailsHref = appendVendorToUrl(`/vulnerabilities/${cveId}`);
        return (
          `<tr>
            <th scope="row">
              <a href="${refUrl}" target="_blank" rel="noopener noreferrer" class="cve-link" aria-label="Abrir referência ${cveId} em nova aba">
                <span class="cve-badge">${cveId}</span>
              </a>
            </th>
            <td>${sev}</td>
            <td class="d-none d-md-table-cell">
              <p class="vulnerability-description mb-0">${desc}</p>
            </td>
            <td><span class="date-text">${pub}</span></td>
            <td>${cvss}</td>
            <td class="text-center">
              <a href="${detailsHref}" class="btn btn-sm btn-outline-primary" title="Ver detalhes" aria-label="Ver detalhes de ${cveId}">
                <i class="bi bi-eye"></i>
              </a>
            </td>
          </tr>`
        );
      }).join('');

      tbody.innerHTML = rowsHtml;

      // Atualizar link "Ver todas" para propagar vendor_ids
      const allLink = document.querySelector('.recent-vulnerabilities-section .section-action');
      if (allLink) {
        allLink.setAttribute('href', appendVendorToUrl(allLink.getAttribute('href') || '/vulnerabilities/'));
      }
    } catch (e) {
      // Retry rápido em caso de abort ou erro transitório
      const isAbort = (typeof DOMException !== 'undefined') && e instanceof DOMException && e.name === 'AbortError';
      console.warn('Falha ao carregar CVEs na Home:', e);
      try {
        await new Promise(res => setTimeout(res, 300));
        const result = await fetchOnce(apiUrl);
        const data = Array.isArray(result.data) ? result.data : [];
        if (!data.length) {
          tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">Nenhuma CVE encontrada para os vendors selecionados</td></tr>`;
          return;
        }
        const rowsHtml = data.map(item => {
          const refUrl = item.reference_url || '#';
          const cveId = item.cve_id || '';
          const desc = (item.description || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
          const pub = formatDate(item.published_date);
          const sev = severityBadge(item.severity);
          const cvss = cvssBadge(item.cvss_score);
          const detailsHref = appendVendorToUrl(`/vulnerabilities/${cveId}`);
          return (
            `<tr>
              <th scope="row">
                <a href="${refUrl}" target="_blank" rel="noopener noreferrer" class="cve-link" aria-label="Abrir referência ${cveId} em nova aba">
                  <span class="cve-badge">${cveId}</span>
                </a>
              </th>
              <td>${sev}</td>
              <td class="d-none d-md-table-cell">
                <p class="vulnerability-description mb-0">${desc}</p>
              </td>
              <td><span class="date-text">${pub}</span></td>
              <td>${cvss}</td>
              <td class="text-center">
                <a href="${detailsHref}" class="btn btn-sm btn-outline-primary" title="Ver detalhes" aria-label="Ver detalhes de ${cveId}">
                  <i class="bi bi-eye"></i>
                </a>
              </td>
            </tr>`
          );
        }).join('');
        tbody.innerHTML = rowsHtml;
        const allLink = document.querySelector('.recent-vulnerabilities-section .section-action');
        if (allLink) {
          allLink.setAttribute('href', appendVendorToUrl(allLink.getAttribute('href') || '/vulnerabilities/'));
        }
      } catch (e2) {
        console.warn('Retry falhou ao carregar CVEs na Home:', e2);
        // Não limpa conteúdo estático em caso de falha dupla
      }
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    // Evitar carregar antes de possível redirecionamento por vendor_ids
    setTimeout(loadLatestCVEs, 200);
  });
})();