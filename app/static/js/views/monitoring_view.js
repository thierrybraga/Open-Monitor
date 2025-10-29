// monitoring_view.js
// Responsável por renderizar regras e resultados de monitoramento e manipular eventos de filtro e detalhes

import MonitoringModel from "../models/monitoring_model.js";

const MonitoringView = (() => {
    let container;
    let filterForm;

    function init() {
        container = document.getElementById("monitoring-container");
        filterForm = document.getElementById("monitoring-filter-form");
        bindEvents();
    }

    /**
     * Renderiza a lista de regras de monitoramento.
     * @param {Array<Object>} items - Lista de regras/execuções de monitoramento com campos:
     *   {number} id
     *   {string} name
     *   {string} lastRun (ISO date string)
     *   {string} status
     */
    function render(items) {
        if (!container) init();

        if (items.length === 0) {
            container.innerHTML = `<p>Nenhuma regra de monitoramento encontrada.</p>`;
            return;
        }

        const rows = items.map(item => `
            <tr data-id="${item.id}">
                <td>${item.name}</td>
                <td>${new Date(item.lastRun).toLocaleString()}</td>
                <td>${item.status}</td>
                <td>
                    <button class="btn btn-sm btn-info view-details-btn">Detalhes</button>
                </td>
            </tr>
        `).join('');

        container.innerHTML = `
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Regra</th>
                        <th>Última Execução</th>
                        <th>Status</th>
                        <th>Ações</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows}
                </tbody>
            </table>
        `;

        bindDetailButtons();
    }

    /**
     * Limpa a view.
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
                new CustomEvent("monitoring:filter:apply", { detail: filters })
            );
        });
    }

    /**
     * Adiciona listener aos botões de detalhes.
     */
    function bindDetailButtons() {
        const buttons = document.querySelectorAll(".view-details-btn");
        buttons.forEach(btn => {
            btn.addEventListener("click", (e) => {
                const id = e.target.closest('tr').dataset.id;
                document.dispatchEvent(
                    new CustomEvent("monitoring:view:details", { detail: { id } })
                );
            });
        });
    }

    return {
        render,
        clear
    };
})();

export default MonitoringView;
