// analytics_view.js
// Responsável por renderizar as métricas de vulnerabilidades e disparar eventos para filtros e gráficos

const AnalyticsView = (() => {
    let container;
    let filterForm;
    let analyticsModel;
    let debounceTimer;
    let isInitialized = false;

    // Lazy loading do modelo
    async function loadModel() {
        if (!analyticsModel) {
            // Aguarda o modelo estar disponível globalmente
            if (typeof window.AnalyticsModel !== 'undefined') {
                analyticsModel = window.AnalyticsModel;
            } else {
                throw new Error('AnalyticsModel not loaded');
            }
        }
        return analyticsModel;
    }

    function init() {
        if (isInitialized) return;
        
        container = document.getElementById("analytics-container");
        filterForm = document.getElementById("analytics-filter-form");
        bindEvents();
        isInitialized = true;
    }

    // Debounce para eventos de filtro
    function debounce(func, wait) {
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(debounceTimer);
                func(...args);
            };
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(later, wait);
        };
    }

    /**
     * Renderiza o resumo de métricas e dispara evento para construir gráfico.
     * @param {Object} metrics
     *        {number} metrics.totalVulnerabilities
     *        {number} metrics.highSeverity
     *        {number} metrics.mediumSeverity
     *        {number} metrics.lowSeverity
     *        {Array}  metrics.chartData
     */
    function render(metrics) {
        if (!container) init();

        container.innerHTML = `
            <div class="analytics-summary row">
                <div class="col">
                    <div class="card mb-3">
                        <div class="card-body text-center">
                            <h5>Total de Vulnerabilidades</h5>
                            <p class="display-4">${metrics.totalVulnerabilities}</p>
                        </div>
                    </div>
                </div>
                <div class="col">
                    <div class="card mb-3">
                        <div class="card-body text-center">
                            <h5>Alta Severidade</h5>
                            <p class="display-4 text-danger">${metrics.highSeverity}</p>
                        </div>
                    </div>
                </div>
                <div class="col">
                    <div class="card mb-3">
                        <div class="card-body text-center">
                            <h5>Média Severidade</h5>
                            <p class="display-4 text-warning">${metrics.mediumSeverity}</p>
                        </div>
                    </div>
                </div>
                <div class="col">
                    <div class="card mb-3">
                        <div class="card-body text-center">
                            <h5>Baixa Severidade</h5>
                            <p class="display-4 text-success">${metrics.lowSeverity}</p>
                        </div>
                    </div>
                </div>
            </div>
            <div id="analytics-chart" class="mt-4"></div>
        `;

        // Dispara evento para o controller montar o gráfico no elemento #analytics-chart
        document.dispatchEvent(
            new CustomEvent("analytics:chart:render", { detail: metrics.chartData })
        );
    }

    /**
     * Limpa a view antes de renderizar novos dados.
     */
    function clear() {
        if (!container) init();
        container.innerHTML = "";
    }

    /**
     * Associa evento de filtro ao formulário com debounce.
     */
    function bindEvents() {
        if (!filterForm) return;
        
        const debouncedFilter = debounce((filters) => {
            document.dispatchEvent(
                new CustomEvent("analytics:filter:apply", { detail: filters })
            );
        }, 300);
        
        filterForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const formData = new FormData(filterForm);
            const filters = Object.fromEntries(formData.entries());
            debouncedFilter(filters);
        });
        
        // Adiciona listener para mudanças em tempo real nos inputs
        const inputs = filterForm.querySelectorAll('input, select');
        inputs.forEach(input => {
            input.addEventListener('input', debounce(() => {
                const formData = new FormData(filterForm);
                const filters = Object.fromEntries(formData.entries());
                debouncedFilter(filters);
            }, 500));
        });
    }

    /**
     * Limpa recursos e event listeners para evitar memory leaks.
     */
    function cleanup() {
        if (debounceTimer) {
            clearTimeout(debounceTimer);
        }
        
        if (filterForm) {
            const inputs = filterForm.querySelectorAll('input, select');
            inputs.forEach(input => {
                input.removeEventListener('input', () => {});
            });
        }
        
        container = null;
        filterForm = null;
        analyticsModel = null;
        isInitialized = false;
    }

    return {
        render,
        clear,
        cleanup,
        init
    };
})();

// Export for global access
if (typeof window !== 'undefined') {
    window.AnalyticsView = AnalyticsView;
}
