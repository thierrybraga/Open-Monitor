// account_view.js
// Responsável por renderizar os dados da página de conta de usuário e manipular eventos de view

import AccountModel from "../models/account_model.js";

const AccountView = (() => {
    let container;

    function init() {
        container = document.getElementById("account-container");
    }

    /**
     * Renderiza as informações do usuário dentro do container.
     * @param {Object} user - Objeto com dados do usuário.
     *        {string} user.username
     *        {string} user.email
     *        {string} user.registered_at (ISO date string)
     */
    function render(user) {
        if (!container) init();

        container.innerHTML = `
            <div class="account-details">
                <h2>Bem-vindo, ${user.username}</h2>
                <p><strong>E‑mail:</strong> ${user.email}</p>
                <p><strong>Registrado em:</strong> ${new Date(user.registered_at).toLocaleDateString()}</p>
                <button id="edit-account-btn" class="btn btn-primary">Editar Conta</button>
            </div>
        `;

        bindEvents();
    }

    /**
     * Limpa o conteúdo da view.
     */
    function clear() {
        if (!container) init();
        container.innerHTML = "";
    }

    /**
     * Associa eventos de UI a ações customizadas.
     */
    function bindEvents() {
        const btn = document.getElementById("edit-account-btn");
        if (btn) {
            btn.addEventListener("click", () => {
                // Dispara evento para o controller tratar edição de conta
                document.dispatchEvent(new CustomEvent("account:edit", { detail: null }));
            });
        }
    }

    return {
        render,
        clear
    };
})();

export default AccountView;
