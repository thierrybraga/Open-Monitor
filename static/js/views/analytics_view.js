// analytics_view.js
// Responsável por renderizar as métricas de vulnerabilidades e disparar eventos para filtros e gráficos

import AnalyticsModel from "../models/analytics_model.js";

const AnalyticsView = (() => {
    let container;
    let filterForm;

    function init() {
        container = document.getElementById("analytics-container");
        filterForm = document.getElementById("analytics-filter-form");
        bindEvents();
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
     * Associa evento de filtro ao formulário.
     */
    function bindEvents() {
        if (!filterForm) return;
        filterForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const formData = new FormData(filterForm);
            const filters = Object.fromEntries(formData.entries());
            document.dispatchEvent(
                new CustomEvent("analytics:filter:apply", { detail: filters })
            );
        });
    }

    return {
        render,
        clear
    };
})();

export default AnalyticsView;
