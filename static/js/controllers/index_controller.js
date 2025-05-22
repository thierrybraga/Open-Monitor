export class IndexController {
  constructor() {
    this.apiBaseUrl = '/api/v1/vulnerabilities';
    this.tableBody = document.querySelector('#vulnerabilities-table tbody');
    this.modalEl = document.getElementById('vulnerabilityModal');
    this.toastEl = document.getElementById('liveToast');
    this.csrfToken = this._getCsrfToken();
    this._bindEvents();
  }

  _bindEvents() {
    // Event delegation na tabela
    this.tableBody.addEventListener('click', (e) => {
      const viewBtn = e.target.closest('[data-action="view"]');
      const mitBtn  = e.target.closest('[data-action="mitigate"]');
      if (viewBtn) {
        this._onViewClick(viewBtn.dataset.cveId);
      } else if (mitBtn) {
        this._onMitigateClick(mitBtn.dataset.cveId, mitBtn);
      }
    });

    // Botões estáticos do modal
    this.modalEl.querySelector('[data-action="modal-mitigate"]')
      .addEventListener('click', () => {
        const cveId = this.modalEl.querySelector('#modal-cve-id').textContent;
        this._onMitigateClick(cveId);
      });

    // Tooltips do Bootstrap
    document.querySelectorAll('[data-bs-toggle="tooltip"]')
      .forEach(el => new bootstrap.Tooltip(el));
  }

  async _onViewClick(cveId) {
    try {
      const res = await fetch(`${this.apiBaseUrl}/${cveId}`, {
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) throw new Error(res.statusText);
      const data = await res.json();
      this._populateModal(data);
      new bootstrap.Modal(this.modalEl).show();
    } catch (err) {
      console.error(err);
      this._showToast('Erro', `Falha ao carregar ${cveId}.`, 'danger');
    }
  }

  async _onMitigateClick(cveId, buttonEl = null) {
    const btn = buttonEl
      || this.tableBody.querySelector(`[data-action="mitigate"][data-cve-id="${cveId}"]`);
    if (btn) btn.disabled = true;

    try {
      const res = await fetch(
        `${this.apiBaseUrl}/${cveId}/mitigate`,
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': this.csrfToken
          }
        }
      );
      if (!res.ok) throw new Error(res.statusText);

      this._updateRowAsMitigated(cveId);
      this._showToast('Sucesso', `Vulnerabilidade ${cveId} mitigada.`, 'success');
      // Fechar modal se estiver aberto
      const modalInstance = bootstrap.Modal.getInstance(this.modalEl);
      if (modalInstance) modalInstance.hide();

    } catch (err) {
      console.error(err);
      this._showToast('Erro', `Não foi possível mitigar ${cveId}.`, 'danger');
      if (btn) btn.disabled = false;
    }
  }

  _populateModal(data) {
    this.modalEl.querySelector('#modal-cve-id').textContent = data.cve_id || 'N/A';
    this.modalEl.querySelector('#modal-severity').innerHTML =
      this._getSeverityBadge(data.base_severity);
    this.modalEl.querySelector('#modal-cvss-score').textContent =
      data.cvss_score ?? 'N/A';
    this.modalEl.querySelector('#modal-description').textContent =
      data.description || 'Sem descrição.';
    this.modalEl.querySelector('#modal-published').textContent =
      this._formatDate(data.published_date) || 'N/A';
    this.modalEl.querySelector('#modal-modified').textContent =
      this._formatDate(data.last_modified) || 'N/A';

    const refs = this.modalEl.querySelector('#modal-references');
    refs.innerHTML = '';
    if (Array.isArray(data.references) && data.references.length) {
      data.references.forEach(r => {
        const li = document.createElement('li');
        li.innerHTML = `<a href="${r.url}" target="_blank" rel="noopener">${r.url}</a>`;
        refs.appendChild(li);
      });
    } else {
      refs.innerHTML = '<li>Sem referências.</li>';
    }
  }

  _updateRowAsMitigated(cveId) {
    const row = document.querySelector(`tr[data-cve-id="${cveId}"]`);
    if (!row) return;
    // Atualiza badge
    const badge = row.querySelector('.severity-badge');
    badge.textContent = 'MITIGATED';
    badge.className = 'badge bg-secondary';
    // Desabilita botão de mitigar
    const btn = row.querySelector(`[data-action="mitigate"]`);
    if (btn) btn.disabled = true;
  }

  _getSeverityBadge(sev) {
    const classes = {
      'CRITICAL': 'bg-danger',
      'HIGH':     'bg-warning',
      'MEDIUM':   'bg-info',
      'LOW':      'bg-secondary'
    };
    return `<span class="badge ${classes[sev] || 'bg-secondary'}">${sev || 'N/A'}</span>`;
  }

  _formatDate(dateStr) {
    if (!dateStr) return '';
    return new Date(dateStr).toISOString().split('T')[0];
  }

  _getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
  }

  _showToast(title, message, type='info') {
    this.toastEl.querySelector('.toast-header strong').textContent = title;
    this.toastEl.querySelector('.toast-body').innerHTML = message;
    // Ajusta classe do corpo (alert-*) se quiser um fundo colorido
    this.toastEl.querySelector('.toast-body')
      .className = `toast-body alert alert-${type} m-0`;
    new bootstrap.Toast(this.toastEl).show();
  }
}

// Inicialização
document.addEventListener('DOMContentLoaded', () => new IndexController());
