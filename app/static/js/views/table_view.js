// table_view.js
// Componente reutilizável para renderizar tabelas com filtros e ações
// Consolidação de newsletter_view.js seguindo princípios SOLID

class TableView {
    constructor(containerId, filterFormId, config = {}) {
        this.container = document.getElementById(containerId);
        this.filterForm = document.getElementById(filterFormId);
        this.config = {
            emptyMessage: 'Nenhum item disponível.',
            tableClass: 'table table-responsive',
            eventPrefix: 'table',
            ...config
        };
        this.init();
    }

    init() {
        this.bindEvents();
    }

    /**
     * Renderiza a tabela com os dados fornecidos
     * @param {Array<Object>} items - Lista de itens para renderizar
     * @param {Array<Object>} columns - Configuração das colunas
     * @param {Array<Object>} actions - Configuração das ações
     */
    render(items, columns, actions = []) {
        if (!this.container) {
            console.error('Container não encontrado');
            return;
        }

        if (!items || items.length === 0) {
            this.container.innerHTML = `<p class="text-muted">${this.config.emptyMessage}</p>`;
            return;
        }

        const headerRow = columns.map(col => `<th>${col.label}</th>`).join('');
        const actionsHeader = actions.length > 0 ? '<th>Ações</th>' : '';

        const rows = items.map(item => {
            const cells = columns.map(col => {
                let value = this.getNestedValue(item, col.field);
                if (col.formatter) {
                    value = col.formatter(value, item);
                }
                return `<td>${value}</td>`;
            }).join('');

            const actionButtons = actions.map(action => 
                `<button class="btn btn-sm btn-${action.variant || 'primary'} ${action.class}" 
                         data-action="${action.name}" 
                         data-id="${item.id}">
                    ${action.icon ? `<i class="${action.icon}"></i> ` : ''}${action.label}
                </button>`
            ).join(' ');

            const actionsCell = actions.length > 0 ? `<td>${actionButtons}</td>` : '';

            return `<tr data-id="${item.id}">${cells}${actionsCell}</tr>`;
        }).join('');

        this.container.innerHTML = `
            <table class="${this.config.tableClass}">
                <thead>
                    <tr>${headerRow}${actionsHeader}</tr>
                </thead>
                <tbody>
                    ${rows}
                </tbody>
            </table>
        `;

        this.bindActionButtons();
    }

    /**
     * Limpa o conteúdo da tabela
     */
    clear() {
        if (this.container) {
            this.container.innerHTML = '';
        }
    }

    /**
     * Associa eventos de filtro ao formulário
     */
    bindEvents() {
        if (!this.filterForm) return;
        
        this.filterForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const formData = new FormData(this.filterForm);
            const filters = Object.fromEntries(formData.entries());
            this.dispatchEvent('filter:apply', { filters });
        });
    }

    /**
     * Associa eventos aos botões de ação
     */
    bindActionButtons() {
        const actionButtons = this.container.querySelectorAll('[data-action]');
        
        actionButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const action = e.target.dataset.action;
                const id = e.target.dataset.id;
                const row = e.target.closest('tr');
                
                this.dispatchEvent(action, { id, element: e.target, row });
            });
        });
    }

    /**
     * Dispara eventos customizados
     */
    dispatchEvent(eventName, detail) {
        const fullEventName = `${this.config.eventPrefix}:${eventName}`;
        document.dispatchEvent(new CustomEvent(fullEventName, { detail }));
    }

    /**
     * Obtém valor aninhado de um objeto usando notação de ponto
     */
    getNestedValue(obj, path) {
        return path.split('.').reduce((current, key) => current?.[key], obj) || '';
    }
}



// Configurações específicas para newsletter
export class NewsletterView extends TableView {
    constructor() {
        super('newsletter-container', 'newsletter-filter-form', {
            emptyMessage: 'Nenhuma newsletter disponível.',
            eventPrefix: 'newsletter'
        });
    }

    renderNewsletters(newsletters) {
        const columns = [
            { field: 'subject', label: 'Assunto' },
            { 
                field: 'sent_at', 
                label: 'Enviado em',
                formatter: (value) => value ? new Date(value).toLocaleString() : 'Não enviado'
            },
            { field: 'status', label: 'Status' }
        ];

        const actions = [
            { name: 'view', label: 'Visualizar', variant: 'primary', icon: 'bi bi-eye' },
            { name: 'edit', label: 'Editar', variant: 'warning', icon: 'bi bi-pencil' },
            { name: 'send', label: 'Enviar', variant: 'success', icon: 'bi bi-send' }
        ];

        this.render(newsletters, columns, actions);
    }
}

export default TableView;