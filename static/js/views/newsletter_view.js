// reports_view.js
// Responsável por renderizar a lista de relatórios gerados e manipular eventos de visualização e download

import ReportsModel from "../models/reports_model.js";

const ReportsView = (() => {
    let container;
    let filterForm;

    function init() {
        container = document.getElementById("reports-container");
        filterForm = document.getElementById("reports-filter-form");
        bindEvents();
    }

    /**
     * Renderiza a lista de relatórios.
     * @param {Array<Object>} reports - Lista de relatórios com campos:
     *   {number} id
     *   {string} title
     *   {string} generated_at (ISO date string)
     *   {string} format (e.g. 'PDF', 'HTML')
     */
    function render(reports) {
        if (!container) init();

        if (!reports || reports.length === 0) {
            container.innerHTML = `<p>Nenhum relatório disponível.</p>`;
            return;
        }

        const rows = reports.map(rep => `
            <tr data-id="${rep.id}">
                <td>${rep.title}</td>
                <td>${new Date(rep.generated_at).toLocaleString()}</td>
                <td>${rep.format}</td>
                <td>
                    <button class="btn btn-sm btn-primary view-report-btn">Visualizar</button>
                    <button class="btn btn-sm btn-secondary download-report-btn">Baixar</button>
                </td>
            </tr>
        `).join('');

        container.innerHTML = `
            <table class="table table-responsive">
                <thead>
                    <tr>
                        <th>Título</th>
                        <th>Gerado em</th>
                        <th>Formato</th>
                        <th>Ações</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows}
                </tbody>
            </table>
        `;

        bindActionButtons();
    }

    /**
     * Limpa a view de relatórios.
     */
    function clear() {
        if (!container) init();
        container.innerHTML = "";
    }

    /**
     * Associa eventos de filtro ao formulário.
     */
    function bindEvents() {
        if (!filterForm) return;
        filterForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const formData = new FormData(filterForm);
            const filters = Object.fromEntries(formData.entries());
            document.dispatchEvent(
                new CustomEvent("reports:filter:apply", { detail: filters })
            );
        });
    }

    /**
     * Associa eventos de visualização e download aos botões.
     */
    function bindActionButtons() {
        const viewBtns = document.querySelectorAll(".view-report-btn");
        const downloadBtns = document.querySelectorAll(".download-report-btn");

        viewBtns.forEach(btn => {
            btn.addEventListener("click", (e) => {
                const id = e.target.closest('tr').dataset.id;
                document.dispatchEvent(
                    new CustomEvent("reports:view", { detail: { id } })
                );
            });
        });

        downloadBtns.forEach(btn => {
            btn.addEventListener("click", (e) => {
                const id = e.target.closest('tr').dataset.id;
                document.dispatchEvent(
                    new CustomEvent("reports:download", { detail: { id } })
                );
            });
        });
    }

    return {
        render,
        clear
    };
})();

export default ReportsView;
