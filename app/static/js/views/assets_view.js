// assets_view.js
// Responsável por renderizar a lista de ativos e manipular eventos de interação do usuário

import AssetsModel from "../models/assets_model.js";

const AssetsView = (() => {
    let container;
    let filterForm;

    function init() {
        container = document.getElementById("assets-container");
        filterForm = document.getElementById("assets-filter-form");
        bindEvents();
    }

    /**
     * Renderiza a lista de ativos.
     * @param {Array<Object>} assets - Lista de ativos com campos:
     *   {number} id
     *   {string} name
     *   {string} ip
     *   {string} status
     */
    function render(assets) {
        if (!container) init();

        if (assets.length === 0) {
            container.innerHTML = `<p>Nenhum ativo encontrado.</p>`;
            return;
        }

        const rows = assets.map(asset => `
            <tr data-id="${asset.id}">
                <td>${asset.name}</td>
                <td>${asset.ip}</td>
                <td>${asset.status}</td>
                <td>
                    <button class="btn btn-sm btn-info view-details-btn">Detalhes</button>
                </td>
            </tr>
        `).join('');

        container.innerHTML = `
            <table class="table table-striped">
                <thead>
                    <tr>
                        <th>Nome</th>
                        <th>IP</th>
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
     * Associa evento de filtragem ao formulário.
     */
    function bindEvents() {
        if (!filterForm) return;
        filterForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const formData = new FormData(filterForm);
            const filters = Object.fromEntries(formData.entries());
            document.dispatchEvent(
                new CustomEvent("assets:filter:apply", { detail: filters })
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
                    new CustomEvent("assets:view:details", { detail: { id } })
                );
            });
        });
    }

    return {
        render,
        clear
    };
})();

export default AssetsView;