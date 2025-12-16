// analytics.js - Analytics page functionality
// Handles data loading and table population for the analytics dashboard

// Polyfill for Element.closest() for older browsers
if (!Element.prototype.closest) {
    Element.prototype.closest = function(s) {
        var el = this;
        do {
            if (el.matches(s)) return el;
            el = el.parentElement || el.parentNode;
        } while (el !== null && el.nodeType === 1);
        return null;
    };
}

class AnalyticsDashboard {
    constructor() {
        this.apiBase = '/api/analytics';
        this.charts = {};
        this.currentPage = 1;
        this.perPage = 10;
        this.currentSort = { field: 'total_cves', direction: 'desc' };
        this.currentFilters = { severity: '', risk: '', search: '' };
        // Estado de preferências de vendors
        this.selectedVendorIds = [];
        this.isAuthenticated = false;
        this.originalProductsData = [];
        this.filteredProductsData = [];
        // CVE filtering and sorting
        this.currentCVESort = { field: 'published_date', direction: 'desc' };
        this.currentCVEFilters = { severity: '', patch: '', search: '' };
        this.originalCVEsData = [];
        this.filteredCVEsData = [];
        // CWE filtering and sorting
        this.currentCWESort = { field: 'count', direction: 'desc' };
        this.currentCWEFilters = { severity: '', risk: '', search: '' };
        this.originalCWEsData = [];
        this.filteredCWEsData = [];
        this.currentCWEsPage = 1;
        this.totalCWEsPages = 1;
        this.currentCWEsPerPage = 10;
        // Loading state management
        this.isLoadingProducts = false;
        this.isLoadingCWEs = false;
        this.isLoadingCVEs = false;
        // Fallback: garantir que fetchWithRetry esteja disponível
        if (typeof this.fetchWithRetry !== 'function') {
            if (typeof window !== 'undefined' && typeof window.fetchWithRetry === 'function') {
                this.fetchWithRetry = window.fetchWithRetry.bind(this);
            } else {
                this.fetchWithRetry = async (url, options = {}) => fetch(url, options);
            }
        }
        // Feature flags configuráveis para comportamento sem vendors
        const featuresFromWindow = (typeof window !== 'undefined' && window.__analyticsFeatures) ? window.__analyticsFeatures : {};
        this.features = Object.assign({
            // Carregar CWEs globalmente quando não há vendors selecionados
            allowGlobalCWEs: true,
            // Carregar Latest CVEs globalmente quando não há vendors selecionados
            allowGlobalLatestCVEs: true,
            // Carregar métricas de Overview globalmente quando não há vendors selecionados
            allowGlobalOverview: true
        }, featuresFromWindow);
        this.init();
    }

    async init() {
        try {
            // Wait a bit to ensure DOM is fully ready
            await new Promise(resolve => setTimeout(resolve, 100));
            // Buscar preferências de vendors antes de carregar dados
            await this.fetchVendorPreferences();

            // Atualizar aviso de escopo de vendors na UI
            try {
                const el = document.getElementById('vendor-scope-text');
                if (el) {
                    if (this.selectedVendorIds && this.selectedVendorIds.length > 0) {
                        el.textContent = `Filtrando por ${this.selectedVendorIds.length} vendor(s) selecionado(s)`;
                    } else {
                        el.textContent = 'Nenhum vendor selecionado. Dados globais exibidos.';
                    }
                }
            } catch(_) {}

            // Fallback: se não houver preferências salvas, tentar obter da URL ou do localStorage
            if (!this.selectedVendorIds || this.selectedVendorIds.length === 0) {
                const fromUrl = this.getVendorIdsFromUrl();
                const fromLocal = this.getVendorIdsFromLocalStorage();
                const fallbackIds = (fromUrl && fromUrl.length ? fromUrl : fromLocal);
                if (fallbackIds && fallbackIds.length) {
                    this.selectedVendorIds = fallbackIds;
                    // Persistir no backend para que os endpoints de analytics apliquem o filtro
                    await this.persistVendorPreferences(this.selectedVendorIds);
                    // Aviso de sincronização automática
                    if (typeof window.safeNotify === 'function') {
                        window.safeNotify('success', 'Preferências', 'Preferências de vendor sincronizadas automaticamente.', 2500);
                    }
                }
            }
            if (!this.selectedVendorIds || this.selectedVendorIds.length === 0) {
                this.showVendorNotice('Nenhum vendor selecionado. Vá em Conta → Preferências de Vendor e selecione pelo menos um vendor para visualizar os dados.');
            } else {
                this.hideVendorNotice();
            }
            
            // Initialize pagination controls
            this.initializeProductsPagination();
            this.initializeCWEsPagination();
            this.initializeCVEsPagination();
            
            // Load overview data quando houver vendors selecionados OU se permitido globalmente
            if ((this.selectedVendorIds && this.selectedVendorIds.length > 0) || this.features.allowGlobalOverview) {
                await this.loadOverviewData();
            }

            // Carregar CWEs (tabela) quando houver vendors ou flag global ativa
            if ((this.selectedVendorIds && this.selectedVendorIds.length > 0) || this.features.allowGlobalCWEs) {
                await this.loadTopCWEs(1, 10, true);
            }

            // Carregar Top Products apenas quando houver vendors selecionados
            // Otimização: lazy load da tabela Top Products quando entrar na viewport
            // Evita custo inicial no carregamento da página
            // A tabela será carregada quando seu container for visível
            // Eager fallback: garantir primeira carga quando vendors existem OU visão global está habilitada
            if (((this.selectedVendorIds && this.selectedVendorIds.length > 0) || this.features.allowGlobalOverview) && !this._productsLoadedOnce) {
                try {
                    this._productsLoadedOnce = true;
                    await this.loadTopProducts(this.currentProductsPage || 1, this.currentProductsPerPage || 10, false);
                } catch (e) {
                    console.warn('Eager load top products failed:', e);
                    this._productsLoadedOnce = false;
                }
            }
            // Carregar Latest CVEs quando houver vendors ou flag global ativa
            if ((this.selectedVendorIds && this.selectedVendorIds.length > 0) || this.features.allowGlobalLatestCVEs) {
                await this.loadLatestCVEs();
            }

            // Garantir Chart.js e carregar todos os gráficos iniciais
            if (typeof Chart === 'undefined') {
                await this.loadChartJS();
                await new Promise(resolve => setTimeout(resolve, 500));
            }
            // Carregar todos os gráficos assim que Chart.js estiver disponível
            if (typeof Chart !== 'undefined') {
                await this.loadCharts();
                this.applyTooltips();
            }
            // Otimização: lazy load de gráficos pesados (ex.: Product Chart)
            // Em vez de carregar todos os gráficos imediatamente, configurar observadores
            this.setupLazyLoadObservers();
            
            // Setup event listeners
            this.setupEventListeners();
            
            console.log('Analytics dashboard initialized successfully');
        } catch (error) {
            const msg = String(error && (error.message || error)).toLowerCase();
            const isAbort = (error && error.name === 'AbortError') || msg.includes('abort');
            const isTransientFetchFail = (error instanceof TypeError) && /failed to fetch/i.test(String(error.message || ''));
            if (isAbort || isTransientFetchFail) {
                return;
            }
            console.error('Failed to initialize analytics dashboard:', error);
            this.showError('Failed to load analytics data');
        }
    }

    // Helpers reutilizáveis de UI/Charts
    createEmptyState(container, message) {
        if (!container) return;
        const prev = container.querySelector('.chart-empty');
        if (prev) prev.remove();
        const emptyMsg = document.createElement('div');
        emptyMsg.className = 'chart-empty text-muted small d-flex align-items-center justify-content-center';
        emptyMsg.style.minHeight = '120px';
        emptyMsg.innerHTML = `<i class="bi bi-info-circle me-2"></i>${message || 'Sem dados disponíveis'}`;
        container.appendChild(emptyMsg);
    }

    ensureChart(key, ctx, config, { container, hasData }) {
        try {
            if (!ctx) { return; }
            if (this.charts[key]) { this.charts[key].destroy(); }
            if (!hasData) {
                this.createEmptyState(container || (ctx && ctx.closest && ctx.closest('.chart-container')), 'Sem dados para exibir');
                return;
            }
            this.charts[key] = new Chart(ctx, config);
        } catch (e) {
            console.error(`Failed to render chart '${key}':`, e);
        }
    }

    applyTooltips(root) {
        try {
            const r = root || document.body;
            const list = [].slice.call(r.querySelectorAll('[data-bs-toggle="tooltip"]'));
            list.forEach(function (el) { try { new bootstrap.Tooltip(el); } catch(_) {} });
        } catch(_) {}
    }

    applyCommonOptions(options) {
        try {
            if (!options) return options;
            options.responsive = true;
            options.maintainAspectRatio = false;
            if (!options.interaction) { options.interaction = { intersect: false, mode: 'index' }; }
            return options;
        } catch(_) { return options; }
    }

    async fetchVendorPreferences() {
        try {
            const resp = await fetch('/api/v1/account/vendor-preferences', { credentials: 'include' });
            if (!resp.ok) {
                throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
            }
            const pref = await resp.json();
            this.selectedVendorIds = Array.isArray(pref.vendor_ids) ? pref.vendor_ids : [];
            this.isAuthenticated = !!pref.authenticated;
            console.log('Vendor preferences loaded:', this.selectedVendorIds);
            return pref;
        } catch (e) {
            console.warn('Failed to fetch vendor preferences:', e);
            this.selectedVendorIds = [];
            this.isAuthenticated = false;
        }
    }

    // Obtém vendor_ids da query string (suporta vendor_ids=1,2,3 e múltiplos vendor_ids)
    getVendorIdsFromUrl() {
        try {
            // Ignorar vendor_ids quando vendor_scope=all estiver ativo (URL ou localStorage)
            const paramsForScope = new URLSearchParams(window.location.search || '');
            const scopeUrl = String(paramsForScope.get('vendor_scope') || '').trim().toLowerCase();
            if (scopeUrl === 'all') return [];
            try {
                const scopeSaved = String(localStorage.getItem('vendorSelection.scope') || '').trim().toLowerCase();
                if (scopeSaved === 'all') return [];
            } catch (_) { /* ignore */ }
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
            // Suporte também a parâmetro singular 'vendor'
            const vendorParam = params.get('vendor');
            if (vendorParam) {
                const parts2 = String(vendorParam).split(',');
                parts2.forEach(p => {
                    const n = parseInt(p.trim(), 10);
                    if (!isNaN(n)) ids.push(n);
                });
            }
            // Deduplicar e ordenar
            ids = Array.from(new Set(ids)).sort((a, b) => a - b);
            return ids;
        } catch (_) {
            return [];
        }
    }

    // Obtém vendor_ids salvos no localStorage pela página de seleção de vendors
    getVendorIdsFromLocalStorage() {
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

    // Constrói vendor_ids priorizando URL, com prefixo configurável ('?' ou '&')
    buildVendorParam(prefix = '?') {
        try {
            const paramsForScope = new URLSearchParams(window.location.search || '');
            const scopeUrl = String(paramsForScope.get('vendor_scope') || '').trim().toLowerCase();
            if (scopeUrl === 'all') {
                return `${prefix}vendor_scope=all`;
            }
            try {
                const scopeSaved = String(localStorage.getItem('vendorSelection.scope') || '').trim().toLowerCase();
                if (scopeSaved === 'all') {
                    return `${prefix}vendor_scope=all`;
                }
            } catch (_) { /* ignore */ }
            const urlVendorIds = this.getVendorIdsFromUrl();
            const effectiveIds = (urlVendorIds && urlVendorIds.length)
                ? urlVendorIds
                : (this.selectedVendorIds || []);
            return (effectiveIds && effectiveIds.length)
                ? `${prefix}vendor_ids=${effectiveIds.join(',')}`
                : '';
        } catch (_) {
            return '';
        }
    }

    // Persiste vendor_ids no backend para alinhar filtros dos endpoints
    async persistVendorPreferences(ids) {
        try {
            if (!ids || !ids.length) return;
            // Evitar ruído de logs e chamadas desnecessárias quando não autenticado
            if (!this.isAuthenticated) {
                console.debug('Skipping vendor preferences persistence: user not authenticated');
                return;
            }
            await fetch('/api/v1/account/vendor-preferences', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ vendor_ids: ids })
            });
            console.log('Vendor preferences persisted from fallback:', ids);
        } catch (e) {
            console.warn('Failed to persist vendor preferences:', e);
        }
    }

    showVendorNotice(message) {
        const container = document.querySelector('.analytics-dashboard');
        if (!container) return;
        let notice = document.getElementById('vendor-pref-notice');
        if (!notice) {
            notice = document.createElement('div');
            notice.id = 'vendor-pref-notice';
            notice.className = 'alert alert-warning';
            notice.setAttribute('role', 'alert');
            container.insertBefore(notice, container.firstChild);
        }
        notice.textContent = message;
    }

    hideVendorNotice() {
        const notice = document.getElementById('vendor-pref-notice');
        if (notice) notice.remove();
    }

    async loadOverviewData() {
        try {
            const vendorParam = this.buildVendorParam('?');
            // Cache cliente curto em sessionStorage para evitar chamadas repetidas
            try {
                const cacheKey = `analytics:overview${vendorParam}`;
                const cachedRaw = sessionStorage.getItem(cacheKey);
                if (cachedRaw) {
                    const cached = JSON.parse(cachedRaw);
                    if (cached && cached.ts && (Date.now() - cached.ts) < 120000 && cached.data) {
                        this.updateOverviewMetrics(cached.data);
                        return;
                    }
                }
            } catch (_) {}
            const response = await this.fetchWithRetry(`${this.apiBase}/overview${vendorParam}`, { credentials: 'include' }, 2, 300);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            this.updateOverviewMetrics(data);
            // Salvar em cache de sessão
            try {
                const cacheKey = `analytics:overview${vendorParam}`;
                sessionStorage.setItem(cacheKey, JSON.stringify({ ts: Date.now(), data }));
            } catch (_) {}
        } catch (error) {
            // Ignore fetch aborts caused by navigation transitions
            const msg = String(error && (error.message || error)).toLowerCase();
            if (error && (error.name === 'AbortError' || msg.includes('abort'))) {
                return;
            }
            const isTransientFetchFail = (error instanceof TypeError) && /failed to fetch/i.test(String(error.message || ''));
            if (isTransientFetchFail) {
                return;
            }
            console.error('Error loading overview data:', error);
            throw error;
        }
    }

    updateOverviewMetrics(data) {
        // Update metric cards with real data
        const metrics = {
            'total-cves': data.total_cves,
            'critical-severity-cves': data.critical_cves,
            'high-severity-cves': data.high_cves,
            'medium-severity-cves': data.medium_cves,
            'patched-cves': data.patched_cves,
            'unpatched-cves': data.unpatched_cves,
            'active-threats': data.active_threats || 0,
            'avg-cvss-score': data.avg_cvss_score || 0.0,
            'avg-exploit-score': data.avg_exploit_score || 0.0,
            'patch-coverage': `${data.patch_coverage}%`,
            'vendor-count': data.vendor_count,
            'product-count': data.product_count,
            'cwe-count': data.cwe_count
        };

        Object.entries(metrics).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
                console.log(`Updated ${id}: ${value}`);
            } else {
                console.warn(`Element with id '${id}' not found`);
            }
        });
    }

    async loadTopProducts(page = 1, perPage = 10, refresh = false) {
        // Prevent multiple simultaneous calls
        if (this.isLoadingProducts) {
            return;
        }
        
        try {
            this.isLoadingProducts = true;
            // Sempre fazer requisição para o servidor com paginação correta
            this.showLoading(true);
            
            // Priorizar vendor_ids da URL para permitir escopo temporário na página
            const urlVendorIds = this.getVendorIdsFromUrl();
            const vendorIdsForRequest = (urlVendorIds && urlVendorIds.length)
                ? urlVendorIds
                : (this.selectedVendorIds || []);
            const vendorParam = vendorIdsForRequest.length
                ? `&vendor_ids=${vendorIdsForRequest.join(',')}`
                : '';
            // Cache cliente (sessionStorage) por vendor/page/perPage
            try {
                if (!refresh) {
                    const cacheKey = `analytics:top_products:${vendorParam}:p${page}:pp${perPage}`;
                    const cachedRaw = sessionStorage.getItem(cacheKey);
                    if (cachedRaw) {
                        const cached = JSON.parse(cachedRaw);
                        if (cached && cached.ts && (Date.now() - cached.ts) < 120000 && cached.data && cached.pagination) {
                            this.currentProductsData = cached.data || [];
                            this.populateProductTable(this.currentProductsData);
                            this.originalProductsData = this.currentProductsData.slice();
                            this.applyFiltersAndSort();
                            this.updateProductsPagination(cached.pagination);
                            this.showLoading(false);
                            return;
                        }
                    }
                }
            } catch (_) {}
            const url = `${this.apiBase}/details/top_products?page=${page}&per_page=${perPage}${vendorParam}`;
            const response = await this.fetchWithRetry(url, { credentials: 'include' }, 2, 300);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            try {
                const src = result && (result.source || (result.metadata && result.metadata.data_source));
                this.updateSourceBadge('products', src);
            } catch (_) {}
            
            // Atualizar dados e tabela
            this.currentProductsData = result.data || [];
            this.populateProductTable(this.currentProductsData);
            // Definir dados originais para que filtros e busca funcionem
            this.originalProductsData = this.currentProductsData.slice();
            // Aplicar filtros/ordenação locais com base nos controles do usuário
            this.applyFiltersAndSort();
            
            // Atualizar controles de paginação
            if (result.pagination) {
                this.updateProductsPagination(result.pagination);
            }
            // Salvar em cache de sessão
            try {
                const cacheKey = `analytics:top_products:${vendorParam}:p${page}:pp${perPage}`;
                sessionStorage.setItem(cacheKey, JSON.stringify({ ts: Date.now(), data: this.currentProductsData, pagination: result.pagination || null }));
            } catch (_) {}
            
            this.showLoading(false);
        } catch (error) {
            // Ignore fetch aborts caused by navigation transitions
            const msg = String(error && (error.message || error)).toLowerCase();
            if (error && (error.name === 'AbortError' || msg.includes('abort'))) {
                this.showLoading(false);
                return;
            }
            const isTransientFetchFail = (error instanceof TypeError) && /failed to fetch/i.test(String(error.message || ''));
            if (isTransientFetchFail) {
                this.showLoading(false);
                return;
            }
            console.error('Error loading top products:', error);
            this.showTableError('product-table-body', 'Failed to load products data');
            this.showLoading(false);
        } finally {
            this.isLoadingProducts = false;
        }
    }

    // Lazy loading: carregar gráficos e tabela pesada quando entram na viewport
    setupLazyLoadObservers() {
        try {
            // Product Chart
            const productCanvas = document.getElementById('productChart');
            if (productCanvas && !this._productChartLoadedOnce) {
                const chartObserver = new IntersectionObserver(async (entries, observer) => {
                    entries.forEach(async entry => {
                        if (entry.isIntersecting && !this._productChartLoadedOnce) {
                            this._productChartLoadedOnce = true;
                            observer.disconnect();
                            try {
                                if (typeof Chart === 'undefined') {
                                    await this.loadChartJS();
                                    await new Promise(r => setTimeout(r, 300));
                                }
                                if (typeof Chart !== 'undefined') {
                                    await this.loadProductChart(Chart);
                                }
                            } catch (e) {
                                console.warn('Lazy load product chart failed:', e);
                            }
                        }
                    });
                }, { root: null, rootMargin: '0px', threshold: 0.2 });
                chartObserver.observe(productCanvas);
            }

            // Top Products table section
            const tableBody = document.getElementById('product-table-body');
            const tableContainer = tableBody ? (tableBody.closest('.table-card') || tableBody.closest('section') || tableBody) : null;
            // Remover dependência de vendors para registrar o observer.
            // O endpoint suporta retorno global; quando vendors forem selecionados, o filtro será aplicado via URL.
            if (tableContainer && !this._productsLoadedOnce) {
                const tableObserver = new IntersectionObserver(async (entries, observer) => {
                    entries.forEach(async entry => {
                        if (entry.isIntersecting && !this._productsLoadedOnce) {
                            this._productsLoadedOnce = true;
                            observer.disconnect();
                            try {
                                await this.loadTopProducts(this.currentProductsPage || this.currentPage || 1, this.currentProductsPerPage || this.perPage || 10, false);
                            } catch (e) {
                                console.warn('Lazy load top products failed:', e);
                            }
                        }
                    });
                }, { root: null, rootMargin: '0px', threshold: 0.15 });
                tableObserver.observe(tableContainer);
            }
        } catch (e) {
            console.warn('setupLazyLoadObservers failed, falling back to eager load:', e);
        }
    }

    populateProductTable(products) {
        const tbody = document.getElementById('product-table-body');
        if (!tbody) return;

        if (!products || products.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">No products data available</td></tr>';
            return;
        }

        tbody.innerHTML = products.map(product => {
            // Helper functions for formatting
            const formatCVSS = (score) => score ? parseFloat(score).toFixed(1) : 'N/A';
            const formatPercentage = (percentage) => percentage ? `${parseFloat(percentage).toFixed(1)}%` : '0%';
            const formatCount = (count) => count || 0;
            const formatRiskScore = (score) => score ? parseFloat(score).toFixed(1) : 'N/A';
            
            // Risk score badge color
            const getRiskBadgeClass = (riskLevel) => {
                switch(riskLevel) {
                    case 'Extremo': return 'danger';
                    case 'Alto': return 'warning';
                    case 'Médio': return 'info';
                    case 'Baixo': return 'success';
                    default: return 'secondary';
                }
            };
            
            // Enhanced patch status with visual indicators
            const patchPercentage = product.patch_percentage || 0;
            const patchedCount = product.patched_cves || 0;
            const totalCves = product.total_cves || 0;
            const unpatchedCount = totalCves - patchedCount;
            
            const getPatchStatusInfo = (percentage) => {
                if (percentage >= 90) return { class: 'success', icon: 'fas fa-shield-alt', status: 'Excellent', color: '#28a745' };
                if (percentage >= 75) return { class: 'info', icon: 'fas fa-shield-alt', status: 'Good', color: '#17a2b8' };
                if (percentage >= 50) return { class: 'warning', icon: 'fas fa-exclamation-triangle', status: 'Fair', color: '#ffc107' };
                if (percentage >= 25) return { class: 'danger', icon: 'fas fa-exclamation-circle', status: 'Poor', color: '#dc3545' };
                return { class: 'dark', icon: 'fas fa-times-circle', status: 'Critical', color: '#6c757d' };
            };
            
            const patchInfo = getPatchStatusInfo(patchPercentage);

            // Build link to vulnerabilities list filtered by product (and current vendor_ids when available)
            const productName = String(product.product || 'Unknown');
            const vendorParam = this.buildVendorParam('?');
            const sep = vendorParam ? '&' : '?';
            const productHref = `/vulnerabilities/${vendorParam}${sep}product=${encodeURIComponent(productName)}`;
            
            return `
                <tr>
                    <td>
                        <div class="d-flex flex-column">
                            <a href="${productHref}" class="text-decoration-none" aria-label="Ver CVEs do produto ${this.escapeHtml(product.product || 'Unknown')}">
                                <strong title="Nome original: ${this.escapeHtml(product.product_original || product.product || 'Unknown')}">
                                    ${this.escapeHtml(product.product || 'Unknown')}
                                </strong>
                            </a>
                            ${product.product_category && product.product_category !== 'Software' ? 
                                `<span class="badge bg-secondary mt-1" style="font-size: 0.7em;">${this.escapeHtml(product.product_category)}</span>` : 
                                ''
                            }
                        </div>
                    </td>
                    <td>
                        <div class="d-flex align-items-center">
                            <i class="fas fa-building me-2 text-muted"></i>
                            <a href="/reports/quick-create?auto=1&report_type=tecnico&vendor_name=${encodeURIComponent(product.vendor || 'Unknown')}" class="text-muted text-decoration-none" title="Gerar relatório técnico consolidado para o vendor ${this.escapeHtml(product.vendor || 'Unknown')}">
                                ${this.escapeHtml(product.vendor || 'Unknown')}
                            </a>
                        </div>
                    </td>
                    <td>
                        <div data-bs-toggle="tooltip" title="Total de CVEs encontradas para este produto">
                            <span class="analytics-badge total-cves">${formatCount(product.total_cves)}</span>
                        </div>
                    </td>
                    <td>
                        <div class="risk-score-container" data-bs-toggle="tooltip" title="Score de risco calculado baseado em CVSS, criticidade e atividade recente (0-100)">
                            <div class="d-flex align-items-center justify-content-center">
                                <span class="me-1">${product.risk_icon || ''}</span>
                                <span class="analytics-badge risk-level-${getRiskBadgeClass(product.risk_level)}">
                                    ${formatRiskScore(product.risk_score)}
                                </span>
                            </div>
                            <div class="risk-level-text text-muted">${product.risk_level || 'N/A'}</div>
                        </div>
                    </td>
                    <td>
                        <div class="critical-cves-container" data-bs-toggle="tooltip" title="CVEs críticas (CVSS ≥ 9.0) e sua porcentagem do total">
                            <span class="analytics-badge severity-critical">${formatCount(product.critical_count)}</span>
                            <div class="critical-percentage">${formatPercentage(product.critical_percentage)}</div>
                        </div>
                    </td>
                    <td>
                        <div class="cvss-container" data-bs-toggle="tooltip" title="Score CVSS médio e faixa (mín-máx) das vulnerabilidades">
                            <span class="cvss-score">${formatCVSS(product.avg_cvss)}</span>
                            <div class="cvss-range">${formatCVSS(product.min_cvss)}-${formatCVSS(product.max_cvss)}</div>
                        </div>
                    </td>
                    <td>
                        <div class="recent-activity-container" data-bs-toggle="tooltip" title="CVEs descobertas nos últimos 30 dias e sua porcentagem">
                            <span class="analytics-badge recent-activity">${formatCount(product.recent_cves)}</span>
                            <div class="recent-percentage">${formatPercentage(product.recent_percentage)}</div>
                        </div>
                    </td>
                    <td>
                        <div class="patch-status-container" data-bs-toggle="tooltip" title="Porcentagem de CVEs com patches disponíveis e status de correção">
                            <div class="patch-status-header">
                                <i class="${patchInfo.icon} patch-icon" style="color: ${patchInfo.color};"></i>
                                <span class="analytics-badge patch-status-${patchInfo.class}">${formatPercentage(patchPercentage)}</span>
                            </div>
                            <div class="patch-details">
                                <div class="patch-count">
                                    <i class="fas fa-check-circle text-success"></i>
                                    <span>${formatCount(patchedCount)} corrigidas</span>
                                </div>
                                ${unpatchedCount > 0 ? 
                                    `<div class="patch-count">
                                        <i class="fas fa-exclamation-circle text-danger"></i>
                                        <span>${formatCount(unpatchedCount)} pendentes</span>
                                    </div>` : 
                                    ''
                                }
                            </div>
                            <div class="patch-status-label">${patchInfo.status}</div>
                        </div>
                    </td>
                    <td>
                        <div class="trend-container" data-bs-toggle="tooltip" title="Tendência de crescimento/redução de CVEs nos últimos períodos">
                            ${this.getTrendIndicator(product.trend_indicator)} <small class="text-muted">${product.trend_status || 'N/A'}</small>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        // Reinitialize Bootstrap tooltips for newly injected elements
        document.dispatchEvent(new Event('paginationUpdated'));
    }

    updateProductsPagination(pagination) {
        // Store current pagination state
        this.currentProductsPage = pagination.page;
        this.totalProductsPages = pagination.pages;
        this.currentProductsPerPage = pagination.per_page;
        
        // Update pagination info
        const paginationInfo = document.getElementById('products-pagination-info');
        if (paginationInfo) {
            const start = (pagination.page - 1) * pagination.per_page + 1;
            const end = Math.min(pagination.page * pagination.per_page, pagination.total);
            paginationInfo.textContent = `Showing ${start}-${end} of ${pagination.total} products`;
        }
        
        // Update page numbers
        const currentPageSpan = document.getElementById('products-current-page');
        const totalPagesSpan = document.getElementById('products-total-pages');
        if (currentPageSpan) currentPageSpan.textContent = pagination.page;
        if (totalPagesSpan) totalPagesSpan.textContent = pagination.pages;
        
        // Update button states
        const prevBtn = document.getElementById('products-prev-btn');
        const nextBtn = document.getElementById('products-next-btn');
        if (prevBtn) prevBtn.disabled = !pagination.has_prev;
        if (nextBtn) nextBtn.disabled = !pagination.has_next;

        // Ensure tooltips are initialized after pagination updates
        document.dispatchEvent(new Event('paginationUpdated'));
    }

    initializeProductsPagination() {
        // Initialize pagination state
        this.currentProductsPage = 1;
        this.totalProductsPages = 1;
        this.currentProductsPerPage = 10;
        this.currentProductsData = [];
        
        // Previous button
        const prevBtn = document.getElementById('products-prev-btn');
        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                if (this.currentProductsPage > 1) {
                    this.loadTopProducts(this.currentProductsPage - 1, this.currentProductsPerPage, true);
                }
            });
        }
        
        // Next button
        const nextBtn = document.getElementById('products-next-btn');
        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                if (this.currentProductsPage < this.totalProductsPages) {
                    this.loadTopProducts(this.currentProductsPage + 1, this.currentProductsPerPage, true);
                }
            });
        }
        
        // Page size selector
        const pageSizeSelect = document.getElementById('products-page-size');
        if (pageSizeSelect) {
            pageSizeSelect.addEventListener('change', (e) => {
                this.currentProductsPerPage = parseInt(e.target.value);
                this.loadTopProducts(1, this.currentProductsPerPage, true); // Reset to page 1
            });
        }
    }

    async loadTopCWEs(page = 1, perPage = 10, refresh = false) {
        try {
            const vendorParam = this.buildVendorParam('&');
            // Build query params with pagination, filters and sorting
            const params = new URLSearchParams();
            params.set('page', String(page));
            params.set('per_page', String(perPage));
            // Filters
            if (this.currentCWEFilters?.severity) params.set('severity', this.currentCWEFilters.severity);
            if (this.currentCWEFilters?.risk) params.set('risk', String(this.currentCWEFilters.risk));
            if (this.currentCWEFilters?.search) params.set('search', this.currentCWEFilters.search);
            // Sorting
            if (this.currentCWESort?.field) params.set('sort_by', this.currentCWESort.field);
            if (this.currentCWESort?.direction) params.set('sort_order', this.currentCWESort.direction);

            const url = `${this.apiBase}/top-cwes?${params.toString()}${vendorParam}`;
            const response = await this.fetchWithRetry(url, { credentials: 'include' }, 2, 300);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();
            try {
                const src = result && ((result.metadata && result.metadata.data_source) || result.source);
                this.updateSourceBadge('cwes', src);
            } catch (_) {}

            // Store the data and pagination info
            this.originalCWEsData = result.data || [];
            this.filteredCWEsData = [...this.originalCWEsData];

            // Update pagination state from API response if present
            if (result.pagination) {
                this.currentCWEsPage = result.pagination.page;
                this.totalCWEsPages = result.pagination.total_pages || result.pagination.pages;
                this.currentCWEsPerPage = result.pagination.per_page;
                this.updateCWEsPagination(result.pagination);
            } else {
                // Fallback pagination based on available data
                this.currentCWEsPage = page;
                this.currentCWEsPerPage = perPage;
                this.totalCWEsPages = 1;
            }

            // Populate the table with current page data
            this.populateCWETable(this.originalCWEsData);

        } catch (error) {
            // Ignore fetch aborts caused by navigation transitions
            const msg = String(error && (error.message || error)).toLowerCase();
            if (error && (error.name === 'AbortError' || msg.includes('abort'))) {
                return;
            }
            const isTransientFetchFail = (error instanceof TypeError) && /failed to fetch/i.test(String(error.message || ''));
            if (isTransientFetchFail) {
                return;
            }
            console.error('Error loading top CWEs:', error);
            this.showTableError('cwe-table-body', 'Falha ao carregar dados de CWEs');
        }
    }

    populateCWETable(cwes) {
        const tbody = document.getElementById('cwe-table-body');
        if (!tbody) return;

        if (!cwes || cwes.length === 0) {
            tbody.innerHTML = '<tr><td colspan="13" class="text-center text-muted">Nenhum dado de CWE disponível</td></tr>';
            return;
        }

        tbody.innerHTML = cwes.map(cwe => {
            // Helper functions for formatting
            const formatCVSS = (score) => score ? parseFloat(score).toFixed(1) : 'N/A';
            const formatPercentage = (percentage) => percentage ? `${parseFloat(percentage).toFixed(1)}%` : '0%';
            const formatCount = (count) => count || 0;
            const formatRiskScore = (score) => score ? parseFloat(score).toFixed(2) : 'N/A';
            
            // Severity badge colors
            const getSeverityBadge = (count, type) => {
                return `<span class="analytics-badge severity-${type}">${formatCount(count)}</span>`;
            };
            
            // Risk score badge
            const getRiskBadge = (score) => {
                if (!score) return '<span class="analytics-badge risk-level-secondary">N/A</span>';
                const numScore = parseFloat(score);
                let riskLevel = 'success';
                if (numScore >= 8) riskLevel = 'danger';
                else if (numScore >= 6) riskLevel = 'warning';
                else if (numScore >= 4) riskLevel = 'info';
                return `<span class="analytics-badge risk-level-${riskLevel}">${formatRiskScore(score)}</span>`;
            };
            
            return `
                <tr>
                    <td><code>${this.escapeHtml(cwe.cwe || 'Unknown')}</code></td>
                    <td><span class="analytics-badge total-cves">${formatCount(cwe.count)}</span></td>
                    <td><strong>${formatCVSS(cwe.avg_cvss)}</strong></td>
                    <td><strong class="text-danger">${formatCVSS(cwe.max_cvss)}</strong></td>
                    <td>${getSeverityBadge(cwe.severity_distribution?.critical, 'critical')}</td>
                    <td>${getSeverityBadge(cwe.severity_distribution?.high, 'high')}</td>
                    <td>${getSeverityBadge(cwe.severity_distribution?.medium, 'medium')}</td>
                    <td>${getSeverityBadge(cwe.severity_distribution?.low, 'low')}</td>
                    <td><strong class="text-danger">${formatPercentage(cwe.critical_percentage)}</strong></td>
                    <td><span class="analytics-badge recent-activity">${formatCount(cwe.recent_cves)}</span></td>
                    <td><span class="analytics-badge active-years">${formatCount(cwe.active_years)}</span></td>
                    <td>${this.getTrendIndicator(cwe.trend_indicator)} <small class="text-muted">${cwe.trend_status || 'N/A'}</small></td>
                    <td>${getRiskBadge(cwe.risk_score)}</td>
                </tr>
            `;
        }).join('');

        // Reinitialize Bootstrap tooltips for any newly injected elements
        document.dispatchEvent(new Event('paginationUpdated'));
    }

    updateCWEsPagination(pagination) {
        // Store current pagination state
        this.currentCWEsPage = pagination.page;
        this.totalCWEsPages = pagination.total_pages || pagination.pages;
        this.currentCWEsPerPage = pagination.per_page;
        
        // Update pagination info
        const paginationInfo = document.getElementById('cwes-pagination-info');
        if (paginationInfo) {
            const start = (pagination.page - 1) * pagination.per_page + 1;
            const end = Math.min(pagination.page * pagination.per_page, pagination.total_items || pagination.total);
            paginationInfo.textContent = `Exibindo ${start}-${end} de ${pagination.total_items || pagination.total} CWEs`;
        }
        
        // Update page numbers
        const currentPageSpan = document.getElementById('cwes-current-page');
        const totalPagesSpan = document.getElementById('cwes-total-pages');
        if (currentPageSpan) currentPageSpan.textContent = pagination.page;
        if (totalPagesSpan) totalPagesSpan.textContent = pagination.total_pages || pagination.pages;
        
        // Update button states
        const prevBtn = document.getElementById('cwes-prev-btn');
        const nextBtn = document.getElementById('cwes-next-btn');
        if (prevBtn) prevBtn.disabled = !pagination.has_prev;
        if (nextBtn) nextBtn.disabled = !pagination.has_next;
    }

    initializeCWEsPagination() {
        // Initialize pagination state
        this.currentCWEsPage = 1;
        this.totalCWEsPages = 1;
        this.currentCWEsPerPage = 10;
        
        // Previous button
        const prevBtn = document.getElementById('cwes-prev-btn');
        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                if (this.currentCWEsPage > 1) {
                    this.loadTopCWEs(this.currentCWEsPage - 1, this.currentCWEsPerPage);
                }
            });
        }
        
        // Next button
        const nextBtn = document.getElementById('cwes-next-btn');
        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                if (this.currentCWEsPage < this.totalCWEsPages) {
                    this.loadTopCWEs(this.currentCWEsPage + 1, this.currentCWEsPerPage);
                }
            });
        }
        
        // Page size selector
        const pageSizeSelect = document.getElementById('cwes-page-size');
        if (pageSizeSelect) {
            pageSizeSelect.addEventListener('change', (e) => {
                this.currentCWEsPerPage = parseInt(e.target.value);
                this.loadTopCWEs(1, this.currentCWEsPerPage); // Reset to page 1
            });
        }
    }

    async loadLatestCVEs(page = 1, perPage = 20, refresh = false) {
        try {
            const vendorParam = this.buildVendorParam('&');
            const response = await this.fetchWithRetry(`${this.apiBase}/latest-cves?page=${page}&per_page=${perPage}${vendorParam}`, { credentials: 'include' }, 2, 300);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            // Store the data and pagination info
            this.originalCVEsData = result.data || [];
            this.filteredCVEsData = [...this.originalCVEsData];
            
            // Update pagination state from API response
            if (result.pagination) {
                this.cvesCurrentPage = result.pagination.page;
                this.cvesTotalPages = result.pagination.pages;
                this.cvesPerPage = result.pagination.per_page;
                this.updateCVEsPagination(result.pagination);
            }
            
            // Populate the table with current page data
            this.populateCVETable(this.originalCVEsData);
            
        } catch (error) {
            // Ignore fetch aborts caused by navigation transitions
            const msg = String(error && (error.message || error)).toLowerCase();
            if (error && (error.name === 'AbortError' || msg.includes('abort'))) {
                return;
            }
            const isTransientFetchFail = (error instanceof TypeError) && /failed to fetch/i.test(String(error.message || ''));
            if (isTransientFetchFail) {
                return;
            }
            console.error('Error loading latest CVEs:', error);
            this.showTableError('cve-table-body', 'Failed to load CVEs data');
        }
    }

    populateCVETable(cves) {
        const tbody = document.getElementById('cve-table-body');
        if (!tbody) return;

        if (!cves || cves.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No CVEs data available</td></tr>';
            return;
        }

        tbody.innerHTML = cves.map(cve => {
            const severityClass = this.getSeverityClass(cve.base_severity);
            
            // Enhanced patch status with visual indicators
            const getPatchStatusInfo = (available) => {
                if (available === true) {
                    return {
                        status: 'Available',
                        class: 'success',
                        icon: 'fas fa-shield-alt',
                        color: '#28a745',
                        bgClass: 'success'
                    };
                } else if (available === false) {
                    return {
                        status: 'Not Available',
                        class: 'danger',
                        icon: 'fas fa-exclamation-triangle',
                        color: '#dc3545',
                        bgClass: 'danger'
                    };
                } else {
                    return {
                        status: 'Pending',
                        class: 'warning',
                        icon: 'fas fa-clock',
                        color: '#ffc107',
                        bgClass: 'warning'
                    };
                }
            };
            
            const patchInfo = getPatchStatusInfo(cve.patch_available);
            const publishedDate = cve.published_date ? new Date(cve.published_date).toLocaleDateString() : 'N/A';
            const cvssScore = cve.cvss_score ? cve.cvss_score.toFixed(1) : 'N/A';
            
            // Create clickable CVE link if reference URL is available
            const cveDisplay = cve.reference_url ? 
                `<a href="${this.escapeHtml(cve.reference_url)}" target="_blank" class="cve-link"><code>${this.escapeHtml(cve.cve_id || 'N/A')}</code></a>` :
                `<code>${this.escapeHtml(cve.cve_id || 'N/A')}</code>`;
            
            return `
                <tr>
                    <td class="text-nowrap">${cveDisplay}</td>
                    <td class="d-none d-md-table-cell text-truncate" style="max-width: 250px;" title="${this.escapeHtml(cve.description || '')}">
                        ${this.escapeHtml(cve.description || 'No description available')}
                    </td>
                    <td class="text-nowrap">${publishedDate}</td>
                    <td><span class="analytics-badge severity-${severityClass}">${this.escapeHtml(cve.base_severity || 'Unknown')}</span></td>
                    <td class="text-nowrap">${cvssScore}</td>
                    <td>
                        <div class="d-flex align-items-center">
                            <i class="${patchInfo.icon} me-2 d-none d-sm-inline" style="color: ${patchInfo.color}; font-size: 0.9em;"></i>
                            <span class="analytics-badge patch-status-${patchInfo.class}">${patchInfo.status}</span>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }

    updateCVEsPagination(pagination) {
        if (!pagination) return;

        const { page, pages, total, has_prev, has_next, per_page } = pagination;
        
        // Update internal state variables
        this.cvesCurrentPage = page;
        this.cvesPerPage = per_page;
        this.cvesTotalPages = pages;
        
        // Update pagination info
        const paginationInfo = document.getElementById('cves-pagination-info');
        if (paginationInfo) {
            const start = ((page - 1) * per_page) + 1;
            const end = Math.min(page * per_page, total);
            paginationInfo.textContent = `Showing ${start}-${end} of ${total} CVEs`;
        }
        
        // Update page numbers
        const currentPageSpan = document.getElementById('cves-current-page');
        const totalPagesSpan = document.getElementById('cves-total-pages');
        if (currentPageSpan) currentPageSpan.textContent = page;
        if (totalPagesSpan) totalPagesSpan.textContent = pages;
        
        // Update button states
        const prevBtn = document.getElementById('cves-prev-btn');
        const nextBtn = document.getElementById('cves-next-btn');
        if (prevBtn) prevBtn.disabled = !has_prev;
        if (nextBtn) nextBtn.disabled = !has_next;

        // Reinitialize tooltips for any newly injected elements
        document.dispatchEvent(new Event('paginationUpdated'));
    }

    initializeCVEsPagination() {
        this.cvesCurrentPage = 1;
        this.cvesPerPage = 20;
        this.cvesTotalPages = 1;
        
        // Previous button
        const prevBtn = document.getElementById('cves-prev-btn');
        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                if (this.cvesCurrentPage > 1) {
                    this.loadLatestCVEs(this.cvesCurrentPage - 1, this.cvesPerPage);
                }
            });
        }
        
        // Next button
        const nextBtn = document.getElementById('cves-next-btn');
        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                if (this.cvesCurrentPage < this.cvesTotalPages) {
                    this.loadLatestCVEs(this.cvesCurrentPage + 1, this.cvesPerPage);
                }
            });
        }
        
        // Page size selector
        const pageSizeSelect = document.getElementById('cves-page-size');
        if (pageSizeSelect) {
            pageSizeSelect.addEventListener('change', (e) => {
                this.cvesPerPage = parseInt(e.target.value);
                this.loadLatestCVEs(1, this.cvesPerPage); // Reset to page 1
            });
        }
    }

    updateSourceBadge(section, source) {
        try {
            const isFallback = String(source || '').toLowerCase().includes('nvd');
            const text = isFallback ? 'dados NVD brutos' : 'dados normalizados';
            const cls = isFallback ? 'bg-warning text-dark' : 'bg-success';
            const id = section === 'products' ? 'products-source-badge' : 'cwes-source-badge';
            const anchorId = section === 'products' ? 'products-pagination-info' : 'cwes-pagination-info';
            const header = document.getElementById(anchorId)?.closest('.card-header');
            if (!header) return;
            let badge = header.querySelector('#' + id);
            if (!badge) {
                badge = document.createElement('span');
                badge.id = id;
                badge.style.fontSize = '0.75em';
                badge.className = 'badge ' + cls + ' ms-2';
                badge.innerHTML = `<i class="bi bi-database me-1"></i>${this.escapeHtml(text)}`;
                const rightGroup = header.querySelector('.d-flex.gap-2, .d-flex.align-items-center');
                if (rightGroup) {
                    rightGroup.prepend(badge);
                } else {
                    header.appendChild(badge);
                }
            } else {
                badge.className = 'badge ' + cls + ' ms-2';
                badge.innerHTML = `<i class="bi bi-database me-1"></i>${this.escapeHtml(text)}`;
            }
            badge.setAttribute('title', isFallback ? 'Exibindo dados por fallback (NVD bruto)' : 'Exibindo dados normalizados');
        } catch (_) {}
    }

    updatePagination(pagination) {
        const paginationContainer = document.getElementById('pagination');
        if (!paginationContainer || !pagination) return;

        const { page, pages, total } = pagination;
        
        if (pages <= 1) {
            paginationContainer.innerHTML = '';
            return;
        }

        let paginationHTML = '';
        
        // Previous button
        if (page > 1) {
            paginationHTML += `<button class="btn btn-sm btn-outline-primary" onclick="analytics.loadLatestCVEs(${page - 1})">&laquo; Previous</button>`;
        }
        
        // Page numbers
        const startPage = Math.max(1, page - 2);
        const endPage = Math.min(pages, page + 2);
        
        for (let i = startPage; i <= endPage; i++) {
            const activeClass = i === page ? 'btn-primary' : 'btn-outline-primary';
            paginationHTML += `<button class="btn btn-sm ${activeClass}" onclick="analytics.loadLatestCVEs(${i})">${i}</button>`;
        }
        
        // Next button
        if (page < pages) {
            paginationHTML += `<button class="btn btn-sm btn-outline-primary" onclick="analytics.loadLatestCVEs(${page + 1})">Next &raquo;</button>`;
        }
        
        paginationContainer.innerHTML = paginationHTML;
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = document.getElementById('refresh-data');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.refreshAllData();
            });
        }
        
        // Top Products filters and controls
        this.setupProductsEventListeners();
        
        // CVE filters and controls
        this.setupCVEEventListeners();
        
        // CWE filters and controls
        this.setupCWEEventListeners();
    }
    
    setupProductsEventListeners() {
        // Filtros de severidade
        const severityFilter = document.getElementById('severity-filter');
        if (severityFilter) {
            severityFilter.addEventListener('change', (e) => {
                this.currentFilters.severity = e.target.value;
                this.applyFiltersAndSort();
            });
        }
        
        // Filtro de risco
        const riskFilter = document.getElementById('risk-filter');
        if (riskFilter) {
            riskFilter.addEventListener('change', (e) => {
                this.currentFilters.risk = e.target.value;
                this.applyFiltersAndSort();
            });
        }
        
        // Busca
        const searchInput = document.getElementById('product-search');
        if (searchInput) {
            let searchTimeout;
            searchInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    this.currentFilters.search = e.target.value.toLowerCase();
                    this.applyFiltersAndSort();
                }, 300);
            });
        }
        
        // Limpar filtros
        const clearFiltersBtn = document.getElementById('clear-filters');
        if (clearFiltersBtn) {
            clearFiltersBtn.addEventListener('click', () => {
                this.clearAllFilters();
            });
        }
        
        // Botão de atualizar
        const refreshProductsBtn = document.getElementById('refresh-products');
        if (refreshProductsBtn) {
            refreshProductsBtn.addEventListener('click', () => {
                this.loadTopProducts(1, this.perPage, true);
            });
        }
        
        // Botão de exportar
        const exportBtn = document.getElementById('export-products');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => {
                this.exportProductsData();
            });
        }
        
        // Ordenação por colunas
        const sortableHeaders = document.querySelectorAll('.enhanced-products-table .sortable');
        sortableHeaders.forEach(header => {
            header.addEventListener('click', () => {
                const sortField = header.dataset.sort;
                if (this.currentSort.field === sortField) {
                    this.currentSort.direction = this.currentSort.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    this.currentSort.field = sortField;
                    this.currentSort.direction = 'desc';
                }
                this.updateSortIcons();
                this.applyFiltersAndSort();
            });
        });
    }
    
    setupCVEEventListeners() {
        // Filtro de severidade
        const severityFilter = document.getElementById('cve-severity-filter');
        if (severityFilter) {
            severityFilter.addEventListener('change', (e) => {
                this.currentCVEFilters.severity = e.target.value;
                this.applyCVEFiltersAndSort();
            });
        }
        
        // Filtro de patch status
        const patchFilter = document.getElementById('cve-patch-filter');
        if (patchFilter) {
            patchFilter.addEventListener('change', (e) => {
                this.currentCVEFilters.patch = e.target.value;
                this.applyCVEFiltersAndSort();
            });
        }
        
        // Busca
        const searchInput = document.getElementById('cve-search');
        if (searchInput) {
            let searchTimeout;
            searchInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    this.currentCVEFilters.search = e.target.value.toLowerCase();
                    this.applyCVEFiltersAndSort();
                }, 300);
            });
        }
        
        // Limpar filtros
        const clearFiltersBtn = document.getElementById('clear-cve-filters');
        if (clearFiltersBtn) {
            clearFiltersBtn.addEventListener('click', () => {
                this.clearAllCVEFilters();
            });
        }
        
        // Botão de atualizar
        const refreshCVEsBtn = document.getElementById('refresh-cves');
        if (refreshCVEsBtn) {
            refreshCVEsBtn.addEventListener('click', () => {
                this.loadLatestCVEs(1, 20, true);
            });
        }
        
        // Botão de exportar
        const exportCVEsBtn = document.getElementById('export-cves');
        if (exportCVEsBtn) {
            exportCVEsBtn.addEventListener('click', () => {
                this.exportCVEsData();
            });
        }
        
        // Ordenação por colunas (com proteção para elementos ausentes)
        const cveTableBody = document.querySelector('#cve-table-body');
        if (cveTableBody) {
            const cveTable = cveTableBody.closest('table');
            if (cveTable) {
                const sortableHeaders = cveTable.querySelectorAll('.sortable');
                sortableHeaders.forEach(header => {
                    header.addEventListener('click', () => {
                        const sortField = header.dataset.sort;
                        if (this.currentCVESort.field === sortField) {
                            this.currentCVESort.direction = this.currentCVESort.direction === 'asc' ? 'desc' : 'asc';
                        } else {
                            this.currentCVESort.field = sortField;
                            this.currentCVESort.direction = 'desc';
                        }
                        this.updateCVESortIcons();
                        this.applyCVEFiltersAndSort();
                    });
                });
            } else {
                console.warn('Tabela de CVEs não encontrada para ordenação');
            }
        } else {
            console.warn('Elemento #cve-table-body não encontrado para ordenação');
        }
    }

    setupCWEEventListeners() {
        // Severity filter
        const severityFilter = document.getElementById('cwe-severity-filter');
        if (severityFilter) {
            severityFilter.addEventListener('change', (e) => {
                this.currentCWEFilters.severity = e.target.value;
                this.applyCWEFiltersAndSort();
            });
        }

        // Risk filter
        const riskFilter = document.getElementById('cwe-risk-filter');
        if (riskFilter) {
            riskFilter.addEventListener('change', (e) => {
                this.currentCWEFilters.risk = e.target.value;
                this.applyCWEFiltersAndSort();
            });
        }

        // Search input
        const searchInput = document.getElementById('cwe-search');
        if (searchInput) {
            let searchTimeout;
            searchInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    this.currentCWEFilters.search = e.target.value;
                    this.applyCWEFiltersAndSort();
                }, 300);
            });
        }

        // Clear filters button
        const clearFiltersBtn = document.getElementById('clear-cwe-filters');
        if (clearFiltersBtn) {
            clearFiltersBtn.addEventListener('click', () => {
                this.clearAllCWEFilters();
            });
        }

        // Export button
        const exportBtn = document.getElementById('export-cwes');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => {
                this.exportCWEsData();
            });
        }

        // Refresh button
        const refreshBtn = document.getElementById('refresh-cwes');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadTopCWEs(1, this.currentCWEsPerPage);
            });
        }

        // Table sorting
        document.querySelectorAll('#cwe-table th[data-sort]').forEach(header => {
            header.addEventListener('click', () => {
                const field = header.getAttribute('data-sort');
                if (this.currentCWESort.field === field) {
                    this.currentCWESort.direction = this.currentCWESort.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    this.currentCWESort.field = field;
                    this.currentCWESort.direction = 'desc';
                }
                this.updateCWESortIcons();
                this.applyCWEFiltersAndSort();
            });
        });

        // Pagination controls are handled by initializeCWEsPagination()
        // Removed duplicate event listeners to avoid conflicts
    }

    async refreshAllData() {
        try {
            this.showLoading(true);
            await this.fetchVendorPreferences();
            // Fallback novamente em refresh
            if (!this.selectedVendorIds || this.selectedVendorIds.length === 0) {
                const fromUrl = this.getVendorIdsFromUrl();
                const fromLocal = this.getVendorIdsFromLocalStorage();
                const fallbackIds = (fromUrl && fromUrl.length ? fromUrl : fromLocal);
                if (fallbackIds && fallbackIds.length) {
                    this.selectedVendorIds = fallbackIds;
                    await this.persistVendorPreferences(this.selectedVendorIds);
                    if (typeof window.safeNotify === 'function') {
                        window.safeNotify('success', 'Preferências', 'Preferências de vendor sincronizadas automaticamente.', 2500);
                    }
                }
            }
            if (!this.selectedVendorIds || this.selectedVendorIds.length === 0) {
                this.showVendorNotice('Nenhum vendor selecionado. Atualize suas preferências para visualizar os dados.');
                this.showLoading(false);
                return;
            } else {
                this.hideVendorNotice();
            }
            await this.loadOverviewData();
            await this.loadTopProducts();
            await this.loadTopCWEs(1, this.currentCWEsPerPage, true);
            await this.loadLatestCVEs(this.currentPage);
            await this.loadCharts();
            this.showLoading(false);
            try {
                var el = document.getElementById('last-update');
                if (el) {
                    var now = new Date();
                    el.textContent = now.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
                }
            } catch (e) {}
        } catch (error) {
            console.error('Error refreshing data:', error);
            this.showError('Failed to refresh data');
            this.showLoading(false);
        }
    }

    showLoading(show) {
        const spinner = document.getElementById('loading-spinner');
        if (spinner) {
            spinner.classList.toggle('d-none', !show);
            spinner.classList.toggle('d-flex', show);
        }
    }

    showError(message) {
        const errorElement = document.getElementById('error-message');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.classList.remove('d-none');
            setTimeout(() => {
                errorElement.classList.add('d-none');
            }, 5000);
        }
    }

    showTableError(tableBodyId, message) {
        const tbody = document.getElementById(tableBodyId);
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="100%" class="text-center text-danger">${message}</td></tr>`;
        }
    }

    getSeverityClass(severity) {
        const severityMap = {
            'CRITICAL': 'danger',
            'HIGH': 'warning',
            'MEDIUM': 'info',
            'LOW': 'success',
            'NONE': 'secondary'
        };
        return severityMap[severity?.toUpperCase()] || 'secondary';
    }

    getProductSeverityClass(count) {
        if (count >= 1000) return 'danger';
        if (count >= 500) return 'warning';
        if (count >= 100) return 'info';
        if (count >= 10) return 'success';
        return 'secondary';
    }

    getProductSeverityLabel(count) {
        if (count >= 1000) return 'Very High';
        if (count >= 500) return 'High';
        if (count >= 100) return 'Medium';
        if (count >= 10) return 'Low';
        return 'Minimal';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    getTrendIndicator(indicator) {
        const icons = {
            '↑': '<i class="bi bi-arrow-up text-danger" title="Crescente"></i>',
            '→': '<i class="bi bi-arrow-right text-warning" title="Estável"></i>',
            '↓': '<i class="bi bi-arrow-down text-success" title="Decrescente"></i>'
        };
        return icons[indicator] || '<i class="bi bi-dash text-muted"></i>';
    }
    
    applyFiltersAndSort() {
        let filteredData = [...this.originalProductsData];
        
        // Aplicar filtros
        if (this.currentFilters.severity) {
            filteredData = filteredData.filter(product => {
                const criticalPercentage = parseFloat(product.critical_percentage) || 0;
                switch(this.currentFilters.severity) {
                    case 'CRITICAL': return criticalPercentage > 50;
                    case 'HIGH': return criticalPercentage > 25 && criticalPercentage <= 50;
                    case 'MEDIUM': return criticalPercentage > 10 && criticalPercentage <= 25;
                    case 'LOW': return criticalPercentage <= 10;
                    default: return true;
                }
            });
        }
        
        if (this.currentFilters.risk) {
            const riskThreshold = parseFloat(this.currentFilters.risk);
            filteredData = filteredData.filter(product => {
                const riskScore = parseFloat(product.risk_score) || 0;
                return riskScore >= riskThreshold;
            });
        }
        
        if (this.currentFilters.search) {
            filteredData = filteredData.filter(product => {
                const searchTerm = this.currentFilters.search;
                return (
                    (product.product || '').toLowerCase().includes(searchTerm) ||
                    (product.vendor || '').toLowerCase().includes(searchTerm) ||
                    (product.product_original || '').toLowerCase().includes(searchTerm) ||
                    (product.vendor_original || '').toLowerCase().includes(searchTerm)
                );
            });
        }
        
        // Aplicar ordenação
        filteredData.sort((a, b) => {
            const field = this.currentSort.field;
            let aVal = a[field];
            let bVal = b[field];
            
            // Converter para números se necessário
            if (typeof aVal === 'string' && !isNaN(parseFloat(aVal))) {
                aVal = parseFloat(aVal) || 0;
                bVal = parseFloat(bVal) || 0;
            }
            
            // Ordenação de strings
            if (typeof aVal === 'string') {
                aVal = aVal.toLowerCase();
                bVal = (bVal || '').toLowerCase();
            }
            
            let result = 0;
            if (aVal < bVal) result = -1;
            else if (aVal > bVal) result = 1;
            
            return this.currentSort.direction === 'asc' ? result : -result;
        });
        
        this.filteredProductsData = filteredData;
        this.populateProductTable(filteredData);
        this.updateFilteredPagination(filteredData.length);
        // Atualizar ícones de ordenação para refletir o estado atual
        this.updateSortIcons();
    }
    
    clearAllFilters() {
        this.currentFilters = { severity: '', risk: '', search: '' };
        
        // Limpar campos do formulário
        const severityFilter = document.getElementById('severity-filter');
        const riskFilter = document.getElementById('risk-filter');
        const searchInput = document.getElementById('product-search');
        
        if (severityFilter) severityFilter.value = '';
        if (riskFilter) riskFilter.value = '';
        if (searchInput) searchInput.value = '';
        
        this.applyFiltersAndSort();
    }
    
    updateSortIcons() {
        const productsTable = document.querySelector('.enhanced-products-table');
        if (!productsTable) return;

        // Reset all headers: icons and ARIA
        productsTable.querySelectorAll('th.sortable').forEach(th => {
            th.setAttribute('aria-sort', 'none');
            const icon = th.querySelector('i');
            if (icon) icon.className = 'fas fa-sort text-muted';
        });

        // Set active header icon and ARIA
        const activeTh = productsTable.querySelector(`th.sortable[data-sort="${this.currentSort.field}"]`);
        if (activeTh) {
            activeTh.setAttribute('aria-sort', this.currentSort.direction === 'asc' ? 'ascending' : 'descending');
            const icon = activeTh.querySelector('i');
            if (icon) icon.className = `fas ${this.currentSort.direction === 'asc' ? 'fa-sort-up' : 'fa-sort-down'} text-primary`;
        }
    }
    
    updateFilteredPagination(totalFiltered) {
        const paginationInfo = document.getElementById('products-pagination-info');
        if (paginationInfo) {
            paginationInfo.textContent = `Mostrando ${totalFiltered} de ${this.originalProductsData.length} produtos`;
        }
    }
    
    exportProductsData() {
        const dataToExport = this.filteredProductsData.length > 0 ? this.filteredProductsData : this.originalProductsData;
        
        // Preparar dados para CSV
        const csvData = [
            ['Product', 'Vendor', 'Total CVEs', 'Risk Score', 'Critical CVEs', 'CVSS Avg', 'Recent CVEs', 'Patch Percentage'],
            ...dataToExport.map(product => [
                product.product || '',
                product.vendor || '',
                product.total_cves || 0,
                product.risk_score || 0,
                product.critical_count || 0,
                product.avg_cvss || 0,
                product.recent_cves || 0,
                product.patch_percentage || 0
            ])
        ];
        
        // Converter para CSV
        const csvContent = csvData.map(row => row.map(field => `"${field}"`).join(',')).join('\n');
        
        // Download do arquivo
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', `top_products_${new Date().toISOString().split('T')[0]}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }



    async loadCharts() {
        try {
            // Check if Chart.js is already loaded
            if (typeof Chart !== 'undefined') {
                console.log('Chart.js already loaded');
                await this.loadSeverityChart(Chart);
                await this.loadPatchStatusChart(Chart);
                await this.loadProductChart(Chart);
                await this.loadCWEChart(Chart);
                await this.loadExploitImpactChart(Chart);
                await this.loadCVEHistoryChart(Chart);
                await this.loadAttackVectorChart(Chart);
                await this.loadAssigneeChart(Chart);
                return;
            }

            // Load Chart.js dynamically via CDN
            await this.loadChartJS();
            
            // Wait a bit for Chart.js to be available
            await new Promise(resolve => setTimeout(resolve, 500));
            console.log('Chart.js should be available now, typeof Chart:', typeof Chart);
            
            if (typeof Chart !== 'undefined') {
                console.log('Chart.js loaded successfully');
                // Load severity distribution chart
                await this.loadSeverityChart(Chart);
                
                // Load patch status chart
                await this.loadPatchStatusChart(Chart);
                
                // Load product pie chart
                await this.loadProductChart(Chart);
                
                // Load CWE pie chart
                await this.loadCWEChart(Chart);
                
                // Load exploit vs impact scatter chart
                await this.loadExploitImpactChart(Chart);
                
                // Load CVE history line chart
                await this.loadCVEHistoryChart(Chart);
                
                // Load attack vector pie chart
                await this.loadAttackVectorChart(Chart);
                
                // Load top assigners bar chart
                await this.loadAssigneeChart(Chart);
            } else {
                throw new Error('Chart.js failed to load');
            }
            
        } catch (error) {
            console.error('Error loading charts:', error);
        }
    }

    loadChartJS() {
        try {
            if (typeof window.Utils !== 'undefined' && Utils.ChartLoader && typeof Utils.ChartLoader.ensure === 'function') {
                return Utils.ChartLoader.ensure();
            }
        } catch (e) {
            console.warn('Utils.ChartLoader indisponível, fallback simples será usado.');
        }
        // Fallback simples: se Chart já estiver presente, resolve; caso contrário, tenta carregar via CDN
        return new Promise((resolve, reject) => {
            if (typeof window.Chart !== 'undefined') { resolve(window.Chart); return; }
            const existing = document.querySelector('script[src*="chart.js"]');
            if (existing) {
                existing.addEventListener('load', () => resolve(window.Chart));
                existing.addEventListener('error', () => reject(new Error('Failed to load Chart.js')));
                return;
            }
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js';
            script.onload = () => resolve(window.Chart);
            script.onerror = () => reject(new Error('Failed to load Chart.js'));
            document.head.appendChild(script);
        });
    }

    async loadSeverityChart(Chart) {
        try {
            const vendorParam = this.buildVendorParam('?');
            const response = await fetch(`${this.apiBase}/severity-distribution${vendorParam}`, { credentials: 'include' });
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            this.createSeverityChart(Chart, result.data);
        } catch (error) {
            console.error('Error loading severity chart:', error);
        }
    }

    async loadPatchStatusChart(Chart) {
        try {
            const vendorParam = this.buildVendorParam('?');
            const response = await this.fetchWithRetry(`${this.apiBase}/patch-status${vendorParam}`, { credentials: 'include' }, 2, 300);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            this.createPatchStatusChart(Chart, result.data);
        } catch (error) {
            const msg = String(error && (error.message || error)).toLowerCase();
            if (error && (error.name === 'AbortError' || msg.includes('abort'))) {
                return;
            }
            const isTransientFetchFail = (error instanceof TypeError) && /failed to fetch/i.test(String(error.message || ''));
            if (isTransientFetchFail) {
                return;
            }
            console.error('Error loading patch status chart:', error);
        }
    }

    createSeverityChart(Chart, data) {
        const ctx = document.getElementById('severityChart');
        if (!ctx) {
            console.warn('Severity chart canvas not found');
            return;
        }

        // Destroy existing chart if it exists
        if (this.charts.severityChart) {
            this.charts.severityChart.destroy();
        }

        const colors = {
            'Critical': '#dc3545',
            'High': '#fd7e14', 
            'Medium': '#ffc107',
            'Low': '#198754',
            'N/A': '#6c757d',
            'None': '#e9ecef'
        };

        // Process API data format: {data: [values], labels: [labels]}
        const chartLabels = data.labels || [];
        const chartData = data.data || [];

        this.charts.severityChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: chartLabels,
                datasets: [{
                    data: chartData,
                    backgroundColor: chartLabels.map(label => colors[label] || '#6c757d'),
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                aspectRatio: 1,
                devicePixelRatio: window.devicePixelRatio || 1,
                animation: {
                    animateRotate: true,
                    animateScale: true,
                    duration: 800,
                    easing: 'easeOutQuart'
                },
                layout: {
                    padding: {
                        top: 10,
                        bottom: 10,
                        left: 10,
                        right: 10
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true,
                            font: {
                                size: 12,
                                family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                            },
                            generateLabels: function(chart) {
                                const data = chart.data;
                                if (data.labels.length && data.datasets.length) {
                                    return data.labels.map((label, i) => {
                                        const dataset = data.datasets[0];
                                        const value = dataset.data[i];
                                        const total = dataset.data.reduce((a, b) => a + b, 0);
                                        const percentage = ((value / total) * 100).toFixed(1);
                                        return {
                                            text: `${label}: ${value} (${percentage}%)`,
                                            fillStyle: dataset.backgroundColor[i],
                                            strokeStyle: dataset.backgroundColor[i],
                                            lineWidth: 0,
                                            pointStyle: 'circle',
                                            hidden: false,
                                            index: i
                                        };
                                    });
                                }
                                return [];
                            }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.9)',
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff',
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 1,
                        cornerRadius: 8,
                        displayColors: true,
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((value / total) * 100).toFixed(1);
                                return `${label}: ${value} vulnerabilidades (${percentage}%)`;
                            }
                        }
                    }
                },
                cutout: '65%'
            }
        });
    }

    createPatchStatusChart(Chart, data) {
        const ctx = document.getElementById('patchStatusChart');
        if (!ctx) {
            console.warn('Patch status chart canvas not found');
            return;
        }

        // Destroy existing chart if it exists
        if (this.charts.patchStatusChart) {
            this.charts.patchStatusChart.destroy();
        }

        const colors = {
            'Patched': '#198754',
            'Unpatched': '#dc3545'
        };

        // Process API data format: {data: [values], labels: [labels]}
        const chartLabels = data.labels || [];
        const chartData = data.data || [];

        this.charts.patchStatusChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: chartLabels,
                datasets: [{
                    data: chartData,
                    backgroundColor: chartLabels.map(label => colors[label] || '#6c757d'),
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                aspectRatio: 1,
                devicePixelRatio: window.devicePixelRatio || 1,
                animation: {
                    animateRotate: true,
                    animateScale: true,
                    duration: 800,
                    easing: 'easeOutQuart'
                },
                layout: {
                    padding: {
                        top: 10,
                        bottom: 10,
                        left: 10,
                        right: 10
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true,
                            font: {
                                size: 12,
                                family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                            },
                            generateLabels: function(chart) {
                                const data = chart.data;
                                if (data.labels.length && data.datasets.length) {
                                    return data.labels.map((label, i) => {
                                        const dataset = data.datasets[0];
                                        const value = dataset.data[i];
                                        const total = dataset.data.reduce((a, b) => a + b, 0);
                                        const percentage = ((value / total) * 100).toFixed(1);
                                        return {
                                            text: `${label}: ${value} (${percentage}%)`,
                                            fillStyle: dataset.backgroundColor[i],
                                            strokeStyle: dataset.backgroundColor[i],
                                            lineWidth: 0,
                                            pointStyle: 'circle',
                                            hidden: false,
                                            index: i
                                        };
                                    });
                                }
                                return [];
                            }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.9)',
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff',
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 1,
                        cornerRadius: 8,
                        displayColors: true,
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((value / total) * 100).toFixed(1);
                                return `${label}: ${value} vulnerabilidades (${percentage}%)`;
                            }
                        }
                    }
                },
                cutout: '65%'
            }
        });
    }

    async loadProductChart(Chart) {
        try {
            // Respeitar escopo global
            const vendorParam = this.buildVendorParam('&');

            // Use relational details endpoint to ensure accurate vendor-scoped products
            const response = await this.fetchWithRetry(`/api/analytics/details/top_products?page=1&per_page=5${vendorParam}`, { credentials: 'include' }, 2, 300);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('Product chart data:', data);
            
            if (!data.data || !Array.isArray(data.data)) {
                console.warn('Invalid product data format');
                return;
            }
            
            // Take only top 5 products for better visualization
            const topProducts = data.data.slice(0, 5);
            
            const labels = topProducts.map(item => {
                const vendor = item.vendor && item.vendor !== 'Unknown' ? ` (${item.vendor})` : '';
                return `${item.product || 'Unknown'}${vendor}`;
            });
            const values = topProducts.map(item => (item.total_cves != null ? Number(item.total_cves) : Number(item.count || 0)));
            
            const colors = [
                '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
                '#FF9F40', '#FF6384', '#C9CBCF'
            ];
            
            const ctx = document.getElementById('productChart');
            if (!ctx) {
                console.warn('Product chart canvas not found');
                return;
            }
            
            // Destroy existing chart if it exists
            if (this.charts.productChart) {
                this.charts.productChart.destroy();
            }

            this.charts.productChart = new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: colors,
                        borderColor: colors.map(color => color + '80'),
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                padding: 15,
                                usePointStyle: true,
                                font: {
                                    size: 11
                                }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                title: function(context) {
                                    const dataIndex = context[0].dataIndex;
                                    const product = topProducts[dataIndex];
                                    return product.product || 'Unknown Product';
                                },
                                label: function(context) {
                                    const dataIndex = context.dataIndex;
                                    const product = topProducts[dataIndex] || {};
                                    const value = Number(context.parsed || 0);
                                    const datasetData = Array.isArray(context.dataset?.data) ? context.dataset.data : [];
                                    const total = datasetData.length ? datasetData.reduce((a, b) => a + b, 0) : 0;
                                    const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : '0.0';
                                    return [
                                        `Vendor: ${product.vendor || 'Unknown'}`,
                                        `CVEs: ${value} (${percentage}%)`,
                                        `Risk Level: ${this.getProductSeverityLabel(value)}`
                                    ];
                                }.bind(this)
                            }
                        }
                    }
                }
            });
            
        } catch (error) {
            // Ignore transient aborts
            const msg = String(error && (error.message || error)).toLowerCase();
            if (error && (error.name === 'AbortError' || msg.includes('abort'))) {
                return;
            }
            const isTransientFetchFail = (error instanceof TypeError) && /failed to fetch/i.test(String(error.message || ''));
            if (isTransientFetchFail) {
                return;
            }
            console.error('Error loading product chart:', error);
        }
    }

    async loadCWEChart(Chart) {
        try {
            const vendorParam = this.buildVendorParam('&');
            const params = new URLSearchParams();
            // Always show top 5 by count for chart, respecting current filters
            params.set('page', '1');
            params.set('per_page', '5');
            params.set('sort_by', 'count');
            params.set('sort_order', 'desc');
            if (this.currentCWEFilters?.severity) params.set('severity', this.currentCWEFilters.severity);
            if (this.currentCWEFilters?.risk) params.set('risk', String(this.currentCWEFilters.risk));
            if (this.currentCWEFilters?.search) params.set('search', this.currentCWEFilters.search);
            const response = await fetch(`/api/analytics/top-cwes?${params.toString()}${vendorParam}`, { credentials: 'include' });
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('CWE chart data:', data);
            
            if (!data.data || !Array.isArray(data.data)) {
                console.warn('Invalid CWE data format');
                return;
            }
            
            // The API already returned the top 5 due to per_page=5
            const top5CWEs = data.data;
            
            const labels = top5CWEs.map(item => item.cwe || 'Unknown');
            const values = top5CWEs.map(item => item.count || 0);
            
            const colors = [
                '#FF9F40', '#FF6384', '#4BC0C0', '#36A2EB', '#9966FF'
            ];
            
            const ctx = document.getElementById('cweChart');
            if (!ctx) {
                console.warn('CWE chart canvas not found');
                return;
            }
            
            // Destroy existing chart if it exists
            if (this.charts.cweChart) {
                this.charts.cweChart.destroy();
            }

            this.charts.cweChart = new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: colors,
                        borderColor: colors.map(color => color + '80'),
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                padding: 15,
                                usePointStyle: true,
                                font: {
                                    size: 11
                                }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.parsed || 0;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = ((value / total) * 100).toFixed(1);
                                    return `${label}: ${value} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
            
        } catch (error) {
            console.error('Error loading CWE chart:', error);
        }
    }

    async loadExploitImpactChart(Chart) {
        try {
            const vendorParam = this.buildVendorParam('?');
            const response = await fetch(`/api/analytics/exploit-impact${vendorParam}`, { credentials: 'include' });
            const result = await response.json();
            
            if (!result.success) {
                throw new Error(result.error || 'Failed to load exploit vs impact data');
            }
            
            const ctx = document.getElementById('exploitImpactChart');
            if (!ctx) {
                console.warn('Exploit Impact chart canvas not found');
                return;
            }
            
            // Destroy existing chart if it exists
            if (this.charts.exploitImpactChart) {
                this.charts.exploitImpactChart.destroy();
            }
            
            // Group data by severity for different datasets
            const severityGroups = {
                'CRITICAL': [],
                'HIGH': [],
                'MEDIUM': [],
                'LOW': []
            };
            
            result.data.forEach(point => {
                if (severityGroups[point.severity]) {
                    severityGroups[point.severity].push({
                        x: point.x,
                        y: point.y,
                        cve_id: point.cve_id
                    });
                }
            });
            
            const datasets = [];
            const severityConfig = {
                'CRITICAL': { color: '#dc3545', label: 'Crítico' },
                'HIGH': { color: '#fd7e14', label: 'Alto' },
                'MEDIUM': { color: '#ffc107', label: 'Médio' },
                'LOW': { color: '#28a745', label: 'Baixo' }
            };
            
            Object.keys(severityGroups).forEach(severity => {
                if (severityGroups[severity].length > 0) {
                    datasets.push({
                        label: severityConfig[severity].label,
                        data: severityGroups[severity],
                        backgroundColor: severityConfig[severity].color,
                        borderColor: severityConfig[severity].color,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    });
                }
            });
            
            this.charts.exploitImpactChart = new Chart(ctx, {
                type: 'scatter',
                data: {
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        title: {
                            display: false
                        },
                        legend: {
                            display: true,
                            position: 'bottom',
                            labels: {
                                usePointStyle: true,
                                padding: 15,
                                font: {
                                    size: 11
                                }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                title: function(context) {
                                    const point = context[0].raw;
                                    return point.cve_id || 'CVE';
                                },
                                label: function(context) {
                                    const point = context.raw;
                                    return [
                                        `Exploitabilidade: ${point.x.toFixed(1)}`,
                                        `Impacto: ${point.y.toFixed(1)}`
                                    ];
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            type: 'linear',
                            position: 'bottom',
                            title: {
                                display: true,
                                text: 'Score de Exploitabilidade'
                            },
                            min: 0,
                            max: 10
                        },
                        y: {
                            title: {
                                display: true,
                                text: 'Score de Impacto'
                            },
                            min: 0,
                            max: 10
                        }
                    }
                }
            });
            
        } catch (error) {
            console.error('Error loading Exploit vs Impact chart:', error);
        }
    }

    async loadCVEHistoryChart(Chart) {
        try {
            console.log('Loading CVE History chart...');
            
            // Fetch CVE history data from API
            const vendorParam = this.buildVendorParam('?');
            const response = await fetch(`/api/analytics/timeseries/cve_history${vendorParam}`, { credentials: 'include' });
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            console.log('CVE History data received:', result);
            
            if (!result.data || result.data.length === 0) {
                console.warn('No CVE history data available');
                return;
            }
            
            const ctx = document.getElementById('cveHistoryChart');
            if (!ctx) {
                console.error('CVE History chart canvas not found');
                return;
            }
            
            // Prepare data for line chart
            const labels = result.data.map(item => {
                const date = new Date(item.date);
                return date.toLocaleDateString('pt-BR', { 
                    month: 'short', 
                    day: 'numeric' 
                });
            });
            
            const values = result.data.map(item => item.value);
            
            const hasData = Array.isArray(result.data) && result.data.length > 0;
            const config = {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'CVEs Publicados',
                        data: values,
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#3b82f6',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            titleColor: '#ffffff',
                            bodyColor: '#ffffff',
                            borderColor: '#3b82f6',
                            borderWidth: 1,
                            callbacks: {
                                title: function(context) {
                                    const dataIndex = context[0].dataIndex;
                                    return result.data[dataIndex].date;
                                },
                                label: function(context) {
                                    return `CVEs: ${context.parsed.y}`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                maxTicksLimit: 8,
                                color: '#6b7280'
                            }
                        },
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(107, 114, 128, 0.1)'
                            },
                            ticks: {
                                color: '#6b7280',
                                callback: function(value) {
                                    return Math.floor(value);
                                }
                            }
                        }
                    },
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    }
                }
            };
            config.options = this.applyCommonOptions(config.options);
            this.ensureChart('cveHistoryChart', ctx, config, { container: ctx.closest('.chart-container'), hasData });
            
            console.log('CVE History chart loaded successfully');
            
        } catch (error) {
            console.error('Error loading CVE History chart:', error);
        }
    }

    async loadAttackVectorChart(Chart) {
        try {
            const vendorParam = this.buildVendorParam('?');
            const response = await fetch(`/api/analytics/attack-vector${vendorParam}`, { credentials: 'include' });
            const data = await response.json();
            
            if (!data.success) {
                throw new Error(data.error || 'Failed to fetch attack vector data');
            }
            
            const ctx = document.getElementById('attackVectorChart');
            if (!ctx) {
                console.warn('Attack Vector chart canvas not found');
                return;
            }
            
            // Destroy existing chart if it exists
            if (this.charts.attackVectorChart) {
                this.charts.attackVectorChart.destroy();
            }
            
            // Prepare data for pie chart
            const chartData = {
                labels: data.data.map(item => item.label),
                datasets: [{
                    data: data.data.map(item => item.value),
                    backgroundColor: data.data.map(item => item.color),
                    borderColor: '#ffffff',
                    borderWidth: 2,
                    hoverBorderWidth: 3
                }]
            };
            
            // Create pie chart
            this.charts.attackVectorChart = new Chart(ctx, {
                type: 'pie',
                data: chartData,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                padding: 20,
                                usePointStyle: true,
                                font: {
                                    size: 12
                                }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.parsed;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = ((value / total) * 100).toFixed(1);
                                    return `${label}: ${value} (${percentage}%)`;
                                }
                            }
                        }
                    },
                    animation: {
                        animateRotate: true,
                        animateScale: true
                    }
                }
            });
            
            console.log('Attack Vector chart loaded successfully');
            
        } catch (error) {
            console.error('Error loading Attack Vector chart:', error);
        }
    }

    async loadAssigneeChart(Chart) {
        try {
            console.log('Starting loadAssigneeChart function');
            const vendorParam = this.buildVendorParam('?');
            const response = await fetch(`/api/analytics/top-assigners${vendorParam}`, { credentials: 'include' });
            if (!response.ok) {
                const ctxErr = document.getElementById('assigneeChart');
                if (ctxErr) {
                    const containerErr = ctxErr.closest('.chart-container');
                    if (containerErr) {
                        const prevEmpty = containerErr.querySelector('.chart-empty');
                        if (prevEmpty) prevEmpty.remove();
                        const emptyMsg = document.createElement('div');
                        emptyMsg.className = 'chart-empty text-muted small';
                        emptyMsg.style.display = 'flex';
                        emptyMsg.style.alignItems = 'center';
                        emptyMsg.style.justifyContent = 'center';
                        emptyMsg.style.height = '100%';
                        emptyMsg.textContent = `Falha ao carregar dados (HTTP ${response.status}).`;
                        containerErr.appendChild(emptyMsg);
                    }
                }
                console.warn('Top Assigners chart degraded:', `HTTP ${response.status}`, response.statusText);
                return;
            }
            
            const data = await response.json();
            console.log('Top Assigners data received:', data);
            
            const ctx = document.getElementById('assigneeChart');
            if (!ctx) { console.warn('Assignee chart canvas not found'); return; }
            const hasData = Array.isArray(data.labels) && data.labels.length > 0 && Array.isArray(data.values) && data.values.length > 0;
            const container = ctx.closest('.chart-container');
            const config = {
                type: 'bar',
                data: {
                    labels: Array.isArray(data.labels) ? data.labels : [],
                    datasets: [{
                        label: 'CVEs Atribuídos',
                        data: Array.isArray(data.values) ? data.values : [],
                        backgroundColor: Array.isArray(data.colors) ? data.colors : [],
                        borderColor: (Array.isArray(data.colors) ? data.colors : []).map(color => color + '80'),
                        borderWidth: 1,
                        borderRadius: 4,
                        borderSkipped: false
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            titleColor: '#fff',
                            bodyColor: '#fff',
                            borderColor: '#333',
                            borderWidth: 1,
                            callbacks: {
                                label: function(context) {
                                    return `CVEs: ${context.parsed.y.toLocaleString()}`;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return value.toLocaleString();
                                }
                            },
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            }
                        },
                        x: {
                            ticks: {
                                maxRotation: 45,
                                minRotation: 45,
                                font: {
                                    size: 10
                                }
                            },
                            grid: {
                                display: false
                            }
                        }
                    },
                    animation: {
                        duration: 1000,
                        easing: 'easeInOutQuart'
                    }
                }
            };
            config.options = this.applyCommonOptions(config.options);
            this.ensureChart('assigneeChart', ctx, config, { container, hasData });
            console.log('Top Assigners chart loaded successfully');
            
        } catch (error) {
            console.warn('Top Assigners chart degraded:', error);
        }
    }
    
    // CVE filtering and sorting functions
    applyCVEFiltersAndSort() {
        // Since we're now using server-side pagination, we need to reload data with filters
        // For now, we'll reload the first page with current filters
        this.loadLatestCVEs(1, this.cvesPerPage);
    }
    
    clearAllCVEFilters() {
        // Reset filter inputs
        const severityFilter = document.getElementById('cve-severity-filter');
        const patchFilter = document.getElementById('cve-patch-filter');
        const searchInput = document.getElementById('cve-search');
        
        if (severityFilter) severityFilter.value = '';
        if (patchFilter) patchFilter.value = '';
        if (searchInput) searchInput.value = '';
        
        // Reset filter state
        this.currentCVEFilters = { severity: '', patch: '', search: '' };
        
        // Reapply filters (which will show all data)
        this.applyCVEFiltersAndSort();
    }
    
    updateCVESortIcons() {
        const cveTable = document.querySelector('#cve-table-body')?.closest('table');
        if (!cveTable) return;

        // Reset all headers: icons and ARIA
        cveTable.querySelectorAll('th.sortable').forEach(th => {
            th.setAttribute('aria-sort', 'none');
            const icon = th.querySelector('i');
            if (icon) icon.className = 'fas fa-sort text-muted';
        });

        // Set active header icon and ARIA
        const activeTh = cveTable.querySelector(`th.sortable[data-sort="${this.currentCVESort.field}"]`);
        if (activeTh) {
            activeTh.setAttribute('aria-sort', this.currentCVESort.direction === 'asc' ? 'ascending' : 'descending');
            const icon = activeTh.querySelector('i');
            if (icon) icon.className = `fas ${this.currentCVESort.direction === 'asc' ? 'fa-sort-up' : 'fa-sort-down'} text-primary`;
        }
    }
    
    // updateFilteredCVEPagination removed - now using server-side pagination

    // CWE filtering and sorting functions
    applyCWEFiltersAndSort() {
        // Since we're now using server-side pagination, we need to reload data with filters
        // For now, we'll reload the first page with current filters
        this.loadTopCWEs(1, this.currentCWEsPerPage);
    }

    clearAllCWEFilters() {
        this.currentCWEFilters = { severity: '', risk: '', search: '' };
        
        // Reset filter controls
        const severityFilter = document.getElementById('cwe-severity-filter');
        const riskFilter = document.getElementById('cwe-risk-filter');
        const searchInput = document.getElementById('cwe-search');
        
        if (severityFilter) severityFilter.value = '';
        if (riskFilter) riskFilter.value = '';
        if (searchInput) searchInput.value = '';
        
        this.applyCWEFiltersAndSort();
    }

    updateCWESortIcons() {
        const cweTable = document.querySelector('#cwe-table');
        if (!cweTable) return;

        // Reset all headers: icons and ARIA
        cweTable.querySelectorAll('th.sortable').forEach(th => {
            th.setAttribute('aria-sort', 'none');
            const icon = th.querySelector('i');
            if (icon) icon.className = 'fas fa-sort text-muted';
        });

        // Set active header icon and ARIA
        const activeTh = cweTable.querySelector(`th.sortable[data-sort="${this.currentCWESort.field}"]`);
        if (activeTh) {
            activeTh.setAttribute('aria-sort', this.currentCWESort.direction === 'asc' ? 'ascending' : 'descending');
            const icon = activeTh.querySelector('i');
            if (icon) icon.className = `fas ${this.currentCWESort.direction === 'asc' ? 'fa-sort-up' : 'fa-sort-down'} text-primary`;
        }
    }
    
    // Local pagination functions removed - now using server-side pagination
    
    exportCVEsData() {
        const dataToExport = this.filteredCVEsData.length > 0 ? this.filteredCVEsData : this.originalCVEsData;
        
        if (dataToExport.length === 0) {
            this.showError('No CVE data available to export');
            return;
        }
        
        const headers = ['CVE ID', 'Description', 'Published Date', 'Severity', 'CVSS Score', 'Patch Available', 'Reference URL'];
        const csvContent = [headers.join(',')];
        
        const formatPatch = (available) => {
            if (available === true) return 'Available';
            if (available === false) return 'Not Available';
            return 'Pending';
        };
        
        dataToExport.forEach(cve => {
            const published = cve.published_date ? (() => { try { return new Date(cve.published_date).toISOString().split('T')[0]; } catch { return String(cve.published_date); } })() : '';
            const cvss = typeof cve.cvss_score === 'number' ? cve.cvss_score.toFixed(1) : (cve.cvss_score || '');
            const row = [
                 `"${(cve.cve_id || '').replace(/"/g, '""')}"`,
                 `"${(cve.description || '').replace(/"/g, '""')}"`,
                 `"${published}"`,
                 `"${(cve.base_severity || '').replace(/"/g, '""')}"`,
                 `${cvss}`,
                 `"${formatPatch(cve.patch_available)}"`,
                 `"${(cve.reference_url || '').replace(/"/g, '""')}"`
             ];
            csvContent.push(row.join(','));
        });
        
        const blob = new Blob([csvContent.join('\n')], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `latest_cves_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }
    
    exportCWEsData() {
        const dataToExport = this.filteredCWEsData.length > 0 ? this.filteredCWEsData : this.originalCWEsData;
        
        if (dataToExport.length === 0) {
            this.showError('No CWE data available to export');
            return;
        }
        
        const headers = ['CWE', 'Count', 'Avg CVSS', 'Max CVSS', 'Critical', 'High', 'Medium', 'Low', 'Critical %', 'Recent CVEs', 'Active Years', 'Trend Status', 'Risk Score'];
        const csvContent = [headers.join(',')];
        
        dataToExport.forEach(cwe => {
            const severity = cwe.severity_distribution || {};
            const avgCvss = typeof cwe.avg_cvss === 'number' ? cwe.avg_cvss.toFixed(1) : (cwe.avg_cvss || '');
            const maxCvss = typeof cwe.max_cvss === 'number' ? cwe.max_cvss.toFixed(1) : (cwe.max_cvss || '');
            const riskScore = typeof cwe.risk_score === 'number' ? cwe.risk_score.toFixed(2) : (cwe.risk_score || '');
            const criticalPct = typeof cwe.critical_percentage === 'number' ? `${cwe.critical_percentage.toFixed(1)}%` : (cwe.critical_percentage || '0%');
            const row = [
                 `"${(cwe.cwe || '').replace(/"/g, '""')}"`,
                 `${cwe.count || 0}`,
                 `${avgCvss}`,
                 `${maxCvss}`,
                 `${severity.critical || 0}`,
                 `${severity.high || 0}`,
                 `${severity.medium || 0}`,
                 `${severity.low || 0}`,
                 `${criticalPct}`,
                 `${cwe.recent_cves || 0}`,
                 `${cwe.active_years || 0}`,
                 `"${(cwe.trend_status || '').replace(/"/g, '""')}"`,
                 `${riskScore}`
             ];
            csvContent.push(row.join(','));
        });
        
        const blob = new Blob([csvContent.join('\n')], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `top_cwes_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }
}

// Chart expansion modal functionality
class ChartExpansionModal {
    constructor() {
        this.modal = null;
        this.expandedChart = null;
        this.originalChart = null;
        this.init();
    }

    init() {
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Event listeners for expand buttons
        document.addEventListener('click', (e) => {
            if (e.target.closest('.expand-chart-btn')) {
                const button = e.target.closest('.expand-chart-btn');
                const chartId = button.getAttribute('data-chart');
                const chartTitle = button.getAttribute('data-title');
                this.expandChart(chartId, chartTitle);
            }
        });

        // Modal close events
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-bs-dismiss="modal"]') || e.target.closest('[data-bs-dismiss="modal"]')) {
                this.closeModal();
            }
        });

        // Download button
        document.addEventListener('click', (e) => {
            if (e.target.matches('#download-chart') || e.target.closest('#download-chart')) {
                this.downloadChart();
            }
        });

        // ESC key to close modal
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal && this.modal.style.display === 'block') {
                this.closeModal();
            }
        });
    }

    expandChart(chartId, chartTitle) {
        const originalCanvas = document.getElementById(chartId);
        if (!originalCanvas || !window.analytics) return;
        // Guard: Chart.js must be available
        if (typeof window.Chart === 'undefined') {
            console.warn('ChartExpansionModal: Chart.js não está disponível, abortando expansão.');
            return;
        }

        // Get the original chart instance
        this.originalChart = (window.analytics.charts && window.analytics.charts[chartId]) || null;
        if (!this.originalChart) return;

        // Get modal elements
        this.modal = document.getElementById('chartModal');
        const modalTitle = document.getElementById('chartModalTitle');
        const expandedCanvas = document.getElementById('expandedChart');

        if (!this.modal || !modalTitle || !expandedCanvas) return;

        // Set modal title
        modalTitle.textContent = chartTitle;

        // Show modal
        this.modal.style.display = 'block';
        this.modal.classList.add('show');
        document.body.classList.add('modal-open');

        // Create backdrop
        const backdrop = document.createElement('div');
        backdrop.className = 'modal-backdrop fade show';
        backdrop.id = 'chartModalBackdrop';
        document.body.appendChild(backdrop);

        // Clone chart configuration
        const config = JSON.parse(JSON.stringify(this.originalChart.config));
        
        // Adjust configuration for larger display
        if (config.options) {
            config.options.responsive = true;
            config.options.maintainAspectRatio = false;
            if (config.options.plugins && config.options.plugins.legend) {
                config.options.plugins.legend.position = 'bottom';
            }
        }

        // Create expanded chart
        setTimeout(() => {
            try {
                const ctx = expandedCanvas.getContext('2d');
                this.expandedChart = new Chart(ctx, config);
            } catch (e) {
                console.error('ChartExpansionModal: falha ao criar gráfico expandido:', e);
            }
        }, 100);
    }

    closeModal() {
        if (!this.modal) return;

        // Destroy expanded chart
        if (this.expandedChart) {
            this.expandedChart.destroy();
            this.expandedChart = null;
        }

        // Hide modal
        this.modal.style.display = 'none';
        this.modal.classList.remove('show');
        document.body.classList.remove('modal-open');

        // Remove backdrop
        const backdrop = document.getElementById('chartModalBackdrop');
        if (backdrop) {
            backdrop.remove();
        }

        this.originalChart = null;
    }

    downloadChart() {
        if (!this.expandedChart) return;

        const canvas = this.expandedChart.canvas;
        const url = canvas.toDataURL('image/png');
        const a = document.createElement('a');
        a.href = url;
        a.download = `chart-${Date.now()}.png`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }
}

// Initialize analytics dashboard when DOM is loaded
let analytics;
let chartModal;
document.addEventListener('DOMContentLoaded', () => {
    // Prevent multiple initializations
    if (window.analytics) {
        console.log('DEBUG: Analytics dashboard already initialized, skipping');
        return;
    }

    // Guard: only initialize on Analytics page
    const analyticsRoot = document.querySelector('.analytics-dashboard');
    if (!analyticsRoot) {
        console.log('DEBUG: Not on Analytics page, skipping analytics.js initialization');
        return;
    }

    try {
        console.log('DEBUG: Initializing analytics dashboard');
        analytics = new AnalyticsDashboard();
        chartModal = new ChartExpansionModal();
        // Export for global access after initialization
        window.analytics = analytics;
        window.chartModal = chartModal;
    } catch (err) {
        console.error('ERROR: Failed to initialize analytics dashboard:', err);
    }
});
// Helper: fetch with simple retry/backoff for transient network aborts
// Expose globally so AnalyticsDashboard can bind to it when available
if (typeof window.fetchWithRetry !== 'function') {
window.fetchWithRetry = async function fetchWithRetry(url, options = {}, retries = 2, backoffMs = 300) {
    for (let attempt = 0; attempt <= retries; attempt++) {
        try {
            // Permitir que requisições GET terminem durante transições/unload
            try {
                if (typeof options.keepalive === 'undefined') {
                    const method = options.method ? String(options.method).toUpperCase() : 'GET';
                    if (method === 'GET') options.keepalive = true;
                }
            } catch(_) {}
            const resp = await fetch(url, options);
            if (resp && resp.ok) return resp;
            // Do not retry for client errors (4xx)
            if (resp && resp.status >= 400 && resp.status < 500) {
                return resp;
            }
            // For server errors, try again
            const isLast = attempt === retries;
            if (isLast) return resp;
        } catch (err) {
            const msg = String(err && (err.message || err)).toLowerCase();
            const isAbort = (err && err.name === 'AbortError') || msg.includes('abort');
            // Não retry em AbortError; deixa o chamador ignorar silenciosamente
            if (isAbort) throw err;
            // Retry em erros de rede/transientes
            if (attempt === retries) throw err;
            // Small backoff before next attempt
        }
        await new Promise(r => setTimeout(r, backoffMs));
    }
    // Fallback: one last fetch to surface any error
    return fetch(url, options);
};
}
