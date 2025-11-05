/**
 * Search Page Enhanced Functionality
 * Provides advanced search features, auto-complete, and improved UX
 */

class SearchManager {
    constructor() {
        this.searchForm = null;
        this.searchInput = null;
        this.resultsSection = null;
        this.statusRegion = null;
        this.loadingIndicator = null;
        this.searchHistory = [];
        this.searchSuggestions = [];
        this.debounceTimer = null;
        this.currentRequest = null;
        this.searchStats = null;
        
        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.initializeElements();
            this.setupEventListeners();
            this.loadSearchHistory();
            this.setupKeyboardShortcuts();
            this.initializeAutoComplete();
        });
    }

    initializeElements() {
        this.searchForm = document.getElementById('search-form');
        this.searchInput = document.getElementById('search-ip');
        this.resultsSection = document.getElementById('result-section');
        this.statusRegion = document.getElementById('results-status');
        this.loadingIndicator = this.createLoadingIndicator();
    }

    setupEventListeners() {
        // Enhanced search input with debouncing
        if (this.searchInput) {
            this.searchInput.addEventListener('input', (e) => {
                this.handleInputChange(e);
            });

            this.searchInput.addEventListener('keydown', (e) => {
                this.handleKeyDown(e);
            });

            this.searchInput.addEventListener('focus', () => {
                this.showSearchSuggestions();
                // Show recent searches if empty
                if (this.searchInput.value.trim() === '') {
                    this.renderRecentSearches();
                }
            });

            // Hide recent searches with slight delay on blur
            this.searchInput.addEventListener('blur', () => {
                setTimeout(() => {
                    const container = document.getElementById('recent-searches');
                    if (container) container.classList.add('d-none');
                }, 200);
            });
        }

        // Form submission with enhanced validation
        if (this.searchForm) {
            this.searchForm.addEventListener('submit', (e) => {
                this.handleFormSubmit(e);
            });
        }

        // Copy to clipboard functionality
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-copy]')) {
                this.copyToClipboard(e.target.dataset.copy);
            }
        });

        // Clear form button
        const clearBtn = document.getElementById('clear-form');
        if (clearBtn) {
            clearBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.clearForm();
            });
        }

        // Removido: handlers de exemplos rápidos (.example-btn)
    }

    handleInputChange(e) {
        const value = e.target.value.trim();
        
        // Clear previous debounce timer
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        // Debounce the input to avoid excessive API calls
        this.debounceTimer = setTimeout(() => {
            if (value.length >= 3) {
                this.fetchSuggestions(value);
            } else {
                this.hideSuggestions();
            }
        }, 300);

        // Real-time validation feedback
        this.validateInput(value);
    }

    handleKeyDown(e) {
        const suggestions = document.querySelectorAll('.suggestion-item');
        const activeSuggestion = document.querySelector('.suggestion-item.active');
        
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.navigateSuggestions('down', suggestions);
                break;
            case 'ArrowUp':
                e.preventDefault();
                this.navigateSuggestions('up', suggestions);
                break;
            case 'Enter':
                if (activeSuggestion) {
                    e.preventDefault();
                    this.selectSuggestion(activeSuggestion.textContent);
                }
                break;
            case 'Escape':
                this.hideSuggestions();
                break;
        }
    }

    validateInput(value) {
        const ipRegex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
        const domainRegex = /^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*)?$/;
        const urlRegex = /^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$/;
        
        const isValid = ipRegex.test(value) || domainRegex.test(value) || urlRegex.test(value);
        
        if (value === '') {
            this.searchInput.classList.remove('is-valid', 'is-invalid');
        } else if (isValid) {
            this.searchInput.classList.remove('is-invalid');
            this.searchInput.classList.add('is-valid');
        } else {
            this.searchInput.classList.remove('is-valid');
            this.searchInput.classList.add('is-invalid');
        }
        
        return isValid;
    }

    async fetchSuggestions(query) {
        // Cancel previous request
        if (this.currentRequest) {
            this.currentRequest.abort();
        }

        try {
            this.currentRequest = new AbortController();
            
            // Simulate API call for suggestions (replace with actual endpoint)
            const suggestions = this.generateSuggestions(query);
            this.displaySuggestions(suggestions);
            
        } catch (error) {
            if (error.name !== 'AbortError') {
                console.error('Error fetching suggestions:', error);
            }
        }
    }

    generateSuggestions(query) {
        // Common domains and IPs for suggestions
        const commonDomains = [
            'google.com', 'facebook.com', 'amazon.com', 'microsoft.com',
            'apple.com', 'netflix.com', 'github.com', 'stackoverflow.com'
        ];
        
        const commonIPs = [
            '8.8.8.8', '8.8.4.4', '1.1.1.1', '1.0.0.1',
            '208.67.222.222', '208.67.220.220'
        ];

        const suggestions = [];
        
        // Filter domains
        commonDomains.forEach(domain => {
            if (domain.toLowerCase().includes(query.toLowerCase())) {
                suggestions.push(domain);
            }
        });
        
        // Filter IPs
        commonIPs.forEach(ip => {
            if (ip.includes(query)) {
                suggestions.push(ip);
            }
        });

        return suggestions.slice(0, 5);
    }

    displaySuggestions(suggestions) {
        let suggestionsContainer = document.getElementById('search-suggestions');
        
        if (!suggestionsContainer) {
            suggestionsContainer = this.createSuggestionsContainer();
        }

        if (suggestions.length === 0) {
            this.hideSuggestions();
            return;
        }

        const suggestionsHTML = suggestions.map(suggestion => 
            `<div class="suggestion-item" role="option" aria-selected="false" data-suggestion="${suggestion}">
                <i class="bi bi-search me-2"></i>
                <span>${suggestion}</span>
                <small class="text-muted ms-auto">Sugestão</small>
            </div>`
        ).join('');

        suggestionsContainer.innerHTML = suggestionsHTML;
        suggestionsContainer.classList.remove('d-none');
        suggestionsContainer.setAttribute('aria-hidden', 'false');
        this.searchInput?.setAttribute('aria-expanded', 'true');

        // Add click handlers
        suggestionsContainer.querySelectorAll('.suggestion-item').forEach(item => {
            item.addEventListener('click', () => {
                this.selectSuggestion(item.dataset.suggestion);
            });
        });
    }

    createSuggestionsContainer() {
        const container = document.createElement('div');
        container.id = 'search-suggestions';
        container.className = 'search-suggestions position-absolute w-100 bg-white border rounded-bottom shadow-sm d-none';
        container.setAttribute('role', 'listbox');
        container.setAttribute('aria-label', 'Sugestões de busca');
        container.setAttribute('aria-hidden', 'true');
        container.style.cssText = 'top: 100%; left: 0; z-index: 1000; max-height: 200px; overflow-y: auto;';
        
        const inputGroup = this.searchInput.closest('.input-group');
        inputGroup.style.position = 'relative';
        inputGroup.appendChild(container);
        
        return container;
    }

    selectSuggestion(suggestion) {
        this.searchInput.value = suggestion;
        this.searchInput.dispatchEvent(new Event('input'));
        this.hideSuggestions();
        this.searchInput.focus();
    }

    hideSuggestions() {
        const suggestionsContainer = document.getElementById('search-suggestions');
        if (suggestionsContainer) {
            suggestionsContainer.classList.add('d-none');
            suggestionsContainer.setAttribute('aria-hidden', 'true');
        }
        this.searchInput?.setAttribute('aria-expanded', 'false');
    }

    showSearchSuggestions() {
        const value = this.searchInput.value.trim();
        if (value.length >= 3) {
            this.fetchSuggestions(value);
        }
    }

    navigateSuggestions(direction, suggestions) {
        const current = document.querySelector('.suggestion-item.active');
        let next;

        if (!current) {
            next = direction === 'down' ? suggestions[0] : suggestions[suggestions.length - 1];
        } else {
            current.classList.remove('active');
            current.setAttribute('aria-selected', 'false');
            const currentIndex = Array.from(suggestions).indexOf(current);
            
            if (direction === 'down') {
                next = suggestions[currentIndex + 1] || suggestions[0];
            } else {
                next = suggestions[currentIndex - 1] || suggestions[suggestions.length - 1];
            }
        }

        if (next) {
            next.classList.add('active');
            next.setAttribute('aria-selected', 'true');
            next.scrollIntoView({ block: 'nearest' });
        }
    }

    handleFormSubmit(e) {
        const value = this.searchInput.value.trim();
        
        if (!this.validateInput(value)) {
            e.preventDefault();
            this.showNotification('Por favor, digite um endereço IP, domínio ou URL válido.', 'error');
            return;
        }

        this.addToSearchHistory(value);
        this.showLoadingState();
        this.hideSuggestions();

        // Announce status and mark busy
        this.announce(`Buscando informações para: ${value}`);
        this.resultsSection?.setAttribute('aria-busy', 'true');

        // Measure perceived response time across reload
        try {
            localStorage.setItem('searchStart', String(Date.now()));
        } catch (_) { /* ignore quota errors */ }
    }

    showLoadingState() {
        const submitBtn = document.querySelector('#search-btn');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = `
                <span class="spinner-border spinner-border-sm me-2" role="status"></span>
                Buscando...
            `;
        }
        this.resultsSection?.setAttribute('aria-busy', 'true');
        this.showGlobalLoading();
    }

    hideLoadingState() {
        const submitBtn = document.querySelector('#search-btn');
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = `
                <i class="bi bi-search me-1"></i>
                Buscar
            `;
        }
        this.resultsSection?.setAttribute('aria-busy', 'false');
        this.hideGlobalLoading();
    }

    addToSearchHistory(query) {
        this.searchHistory = this.searchHistory.filter(item => item !== query);
        this.searchHistory.unshift(query);
        this.searchHistory = this.searchHistory.slice(0, 10);
        
        localStorage.setItem('searchHistory', JSON.stringify(this.searchHistory));

        // Update recent searches UI
        this.renderRecentSearches();
    }

    loadSearchHistory() {
        const stored = localStorage.getItem('searchHistory');
        if (stored) {
            this.searchHistory = JSON.parse(stored);
        }
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + K to focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                this.searchInput?.focus();
            }
            
            // Escape to clear search
            if (e.key === 'Escape' && document.activeElement === this.searchInput) {
                this.searchInput.value = '';
                this.searchInput.blur();
                this.hideSuggestions();
            }
        });
    }

    renderRecentSearches() {
        const container = document.getElementById('recent-searches');
        const list = document.getElementById('recent-searches-list');
        if (!container || !list) return;

        const recent = Array.isArray(this.searchHistory) ? this.searchHistory.slice(0, 5) : [];
        if (recent.length === 0) {
            container.classList.add('d-none');
            return;
        }

        list.innerHTML = recent.map(query => `
            <div class="recent-search-item" data-query="${query}">
               <i class="bi bi-clock-history me-2"></i>
               <span>${query}</span>
               <button type="button" class="btn btn-sm btn-outline-danger remove-recent" data-query="${query}" title="Remover">
                 <i class="bi bi-x"></i>
               </button>
             </div>
        `).join('');

        container.classList.remove('d-none');

        // Item click (fill input)
        list.querySelectorAll('.recent-search-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (!e.target.closest('.remove-recent')) {
                    this.searchInput.value = item.dataset.query;
                    this.searchInput.dispatchEvent(new Event('input'));
                    container.classList.add('d-none');
                }
            });
        });

        // Remove buttons
        list.querySelectorAll('.remove-recent').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.removeRecentSearch(btn.dataset.query);
                this.renderRecentSearches();
            });
        });
    }

    removeRecentSearch(query) {
        this.searchHistory = this.searchHistory.filter(item => item !== query);
        localStorage.setItem('searchHistory', JSON.stringify(this.searchHistory));
    }

    initializeAutoComplete() {
        // Add search shortcut hint
        if (this.searchInput) {
            this.searchInput.setAttribute('placeholder', 
                this.searchInput.getAttribute('placeholder') + ' (Ctrl+K)'
            );
        }

        // Initialize stats and announce if results already visible
        this.initializeStats();
        this.initializeTableEnhancements();
    }

    copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            this.showNotification('Copiado para a área de transferência!', 'success');
        }).catch(() => {
            this.showNotification('Erro ao copiar para a área de transferência.', 'error');
        });
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 1060; min-width: 300px;';
        
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }

    // ===== Accessibility & Announcements =====
    announce(message) {
        if (this.statusRegion) {
            this.statusRegion.textContent = message;
        }
    }

    // ===== Form helpers =====
    clearForm() {
        if (!this.searchInput) return;
        this.searchInput.value = '';
        this.searchInput.classList.remove('is-invalid', 'is-valid');
        const errorDiv = document.getElementById('ip-error');
        if (errorDiv) errorDiv.textContent = '';
        const clearInputBtn = document.getElementById('clear-input');
        if (clearInputBtn) clearInputBtn.style.display = 'none';
        this.searchInput.setAttribute('aria-invalid', 'false');
        this.searchInput.setAttribute('aria-describedby', 'search-help');
        const recent = document.getElementById('recent-searches');
        if (recent) recent.classList.add('d-none');
        this.searchInput.focus();
        this.showNotification('Formulário limpo com sucesso!', 'success');
    }

    // ===== Stats management =====
    initializeStats() {
        // Load stats
        const stored = localStorage.getItem('searchStats');
        const stats = stored ? JSON.parse(stored) : {
            totalSearches: 0,
            responseTimes: [],
            securityScore: 100
        };

        // If last search time is stored, compute response time
        const start = Number(localStorage.getItem('searchStart') || 0);
        if (start) {
            const duration = Math.max(0, Date.now() - start);
            stats.totalSearches += 1;
            stats.responseTimes.push(duration);
            if (stats.responseTimes.length > 100) {
                stats.responseTimes = stats.responseTimes.slice(-100);
            }
            try { localStorage.removeItem('searchStart'); } catch (_) {}
            this.showNotification(`Página carregada em ${duration}ms`, 'info');
        }

        // Persist and update UI
        try { localStorage.setItem('searchStats', JSON.stringify(stats)); } catch (_) {}
        this.updateStatsDisplay(stats);
    }

    updateStatsDisplay(stats) {
        const avg = stats.responseTimes.length
            ? Math.round(stats.responseTimes.reduce((a, b) => a + b, 0) / stats.responseTimes.length)
            : 0;
        const totalEl = document.getElementById('total-searches');
        const avgEl = document.getElementById('avg-response-time');
        const secEl = document.getElementById('security-score');
        if (totalEl) totalEl.textContent = stats.totalSearches.toLocaleString();
        if (avgEl) avgEl.textContent = `${avg}ms`;
        if (secEl) secEl.textContent = `${stats.securityScore}%`;
    }

    // ===== Table sorting & announcements =====
    initializeTableEnhancements() {
        // Announce existing results
        const tbody = document.getElementById('result-table-body');
        if (tbody) {
            const count = tbody.querySelectorAll('tr').length;
            if (count > 0) {
                this.announce(`${count} resultados carregados.`);
            }
        }
        this.setupTableSorting();
    }

    setupTableSorting() {
        const headers = document.querySelectorAll('thead .sortable');
        const tbody = document.getElementById('result-table-body');
        if (!headers.length || !tbody) return;

        headers.forEach(th => {
            th.tabIndex = 0;
            th.addEventListener('click', () => this.onSortClick(th, tbody));
            th.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.onSortClick(th, tbody);
                }
            });
        });
    }

    onSortClick(th, tbody) {
        const current = th.getAttribute('aria-sort') || 'none';
        const next = current === 'ascending' ? 'descending' : 'ascending';
        // Reset other headers
        document.querySelectorAll('thead .sortable').forEach(h => h.setAttribute('aria-sort', h === th ? next : 'none'));

        const key = th.dataset.sort;
        const idx = key === 'property' ? 0 : 1; // action column ignored

        const rows = Array.from(tbody.querySelectorAll('tr'));
        rows.sort((a, b) => {
            const av = (a.children[idx]?.textContent || '').trim().toLowerCase();
            const bv = (b.children[idx]?.textContent || '').trim().toLowerCase();
            const cmp = av.localeCompare(bv, undefined, { numeric: true, sensitivity: 'base' });
            return next === 'ascending' ? cmp : -cmp;
        });

        // Re-append in sorted order
        rows.forEach(r => tbody.appendChild(r));
        const count = rows.length;
        this.announce(`Tabela ordenada por ${key}, ${next === 'ascending' ? 'crescente' : 'decrescente'}. ${count} linhas.`);
    }

    createLoadingIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'loading-indicator position-fixed top-50 start-50 translate-middle d-none';
        indicator.setAttribute('aria-hidden', 'true');
        indicator.style.zIndex = '1070';
        
        indicator.innerHTML = `
            <div class="card shadow-lg">
                <div class="card-body text-center p-4">
                    <div class="spinner-border text-primary mb-3" role="status">
                        <span class="visually-hidden">Carregando...</span>
                    </div>
                    <h5 class="card-title">Processando consulta...</h5>
                    <p class="card-text text-muted">Aguarde enquanto buscamos as informações.</p>
                </div>
            </div>
        `;
        
        document.body.appendChild(indicator);
        return indicator;
    }

    showGlobalLoading() {
        if (this.loadingIndicator) {
            this.loadingIndicator.classList.remove('d-none');
            this.loadingIndicator.setAttribute('aria-hidden', 'false');
        }
    }

    hideGlobalLoading() {
        if (this.loadingIndicator) {
            this.loadingIndicator.classList.add('d-none');
            this.loadingIndicator.setAttribute('aria-hidden', 'true');
        }
    }
}

// Initialize the search manager
const searchManager = new SearchManager();

// Export for potential use in other scripts
window.SearchManager = SearchManager;

// Mapbox initialization for Search page
function initMap() {
    try {
        if (typeof mapboxgl === 'undefined' || !window.MAPBOX_ACCESS_TOKEN) {
            console.warn('Mapbox GL not available or access token missing.');
            return;
        }
        mapboxgl.accessToken = window.MAPBOX_ACCESS_TOKEN;

        var mapEl = document.getElementById('map');
        if (!mapEl) {
            console.warn('Map container #map not found.');
            return;
        }

        var lat = parseFloat(mapEl.getAttribute('data-lat'));
        var lng = parseFloat(mapEl.getAttribute('data-lng'));
        var label = mapEl.getAttribute('data-label') || '';

        if (isNaN(lat) || isNaN(lng)) {
            // Fallback coordinates (Belo Horizonte)
            lat = -19.9245;
            lng = -43.9352;
            label = label || 'Belo Horizonte, MG';
        }

        var loadingEl = document.getElementById('map-loading');
        if (loadingEl) {
            loadingEl.classList.remove('d-none');
        }

        var map = new mapboxgl.Map({
            container: 'map',
            style: 'mapbox://styles/mapbox/streets-v11',
            center: [lng, lat],
            zoom: 11,
        });

        map.on('load', function() {
            if (loadingEl) { loadingEl.classList.add('d-none'); }
        });

        var marker = new mapboxgl.Marker({ color: '#3b82f6' })
            .setLngLat([lng, lat])
            .addTo(map);

        if (label) {
            var popup = new mapboxgl.Popup({ offset: 25 })
                .setText(label);
            marker.setPopup(popup);
        }
    } catch (e) {
        console.error('Error initializing Mapbox map:', e);
    }
}

// Inicializa o mapa quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', initMap);