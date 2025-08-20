/**
 * loading.js - Gerenciamento de Estados de Carregamento
 * Versão: 1.0 - Criado em Janeiro 2025
 * Sistema para gerenciar loading states, skeleton screens e feedback visual
 */

(function() {
    'use strict';

    // ==========================================================================
    // Configurações e Constantes
    // ==========================================================================

    const CONFIG = {
        // Classes CSS
        classes: {
            loading: 'loading',
            loadingOverlay: 'loading-overlay',
            loadingContent: 'loading-content',
            loadingText: 'loading-text',
            skeleton: 'skeleton',
            skeletonText: 'skeleton-text',
            skeletonHeading: 'skeleton-heading',
            skeletonAvatar: 'skeleton-avatar',
            skeletonButton: 'skeleton-button',
            skeletonCard: 'skeleton-card',
            spinner: 'spinner',
            loadingHidden: 'loading-hidden',
            loadingComplete: 'loading-complete',
            loadingDisabled: 'loading-disabled'
        },
        
        // Durações padrão
        durations: {
            fadeIn: 300,
            fadeOut: 300,
            skeleton: 1500,
            spinner: 1000
        },
        
        // Textos padrão
        texts: {
            loading: 'Carregando...',
            error: 'Erro ao carregar',
            retry: 'Tentar novamente',
            noData: 'Nenhum dado encontrado'
        }
    };

    // ==========================================================================
    // Estado Global
    // ==========================================================================

    let loadingInstances = new Map();
    let loadingCounter = 0;

    // ==========================================================================
    // Utilitários
    // ==========================================================================

    /**
     * Gera um ID único para instância de loading
     */
    function generateId() {
        return `loading-${++loadingCounter}-${Date.now()}`;
    }

    /**
     * Cria um elemento DOM
     */
    function createElement(tag, classes = [], attributes = {}) {
        const element = document.createElement(tag);
        
        if (classes.length > 0) {
            element.className = classes.join(' ');
        }
        
        Object.entries(attributes).forEach(([key, value]) => {
            element.setAttribute(key, value);
        });
        
        return element;
    }

    /**
     * Remove elemento com animação
     */
    function removeElementWithAnimation(element, duration = CONFIG.durations.fadeOut) {
        if (!element || !element.parentNode) return Promise.resolve();
        
        return new Promise(resolve => {
            element.style.transition = `opacity ${duration}ms ease-out`;
            element.style.opacity = '0';
            
            setTimeout(() => {
                if (element.parentNode) {
                    element.parentNode.removeChild(element);
                }
                resolve();
            }, duration);
        });
    }

    /**
     * Adiciona elemento com animação
     */
    function addElementWithAnimation(parent, element, duration = CONFIG.durations.fadeIn) {
        element.style.opacity = '0';
        parent.appendChild(element);
        
        // Forçar reflow
        element.offsetHeight;
        
        element.style.transition = `opacity ${duration}ms ease-out`;
        element.style.opacity = '1';
    }

    // ==========================================================================
    // Classe LoadingManager
    // ==========================================================================

    class LoadingManager {
        constructor(element, options = {}) {
            this.id = generateId();
            this.element = element;
            this.options = {
                type: 'overlay', // overlay, inline, skeleton
                text: CONFIG.texts.loading,
                spinner: 'default', // default, dots, pulse
                position: 'center', // center, top, bottom
                backdrop: true,
                ...options
            };
            
            this.loadingElement = null;
            this.originalContent = null;
            this.isActive = false;
            
            loadingInstances.set(this.id, this);
        }

        /**
         * Inicia o estado de loading
         */
        show() {
            if (this.isActive) return this;
            
            this.isActive = true;
            
            switch (this.options.type) {
                case 'overlay':
                    this.showOverlay();
                    break;
                case 'inline':
                    this.showInline();
                    break;
                case 'skeleton':
                    this.showSkeleton();
                    break;
                default:
                    this.showOverlay();
            }
            
            this.dispatchEvent('show');
            return this;
        }

        /**
         * Para o estado de loading
         */
        hide() {
            if (!this.isActive) return this;
            
            this.isActive = false;
            
            if (this.loadingElement) {
                removeElementWithAnimation(this.loadingElement).then(() => {
                    this.loadingElement = null;
                    this.restoreOriginalContent();
                    this.dispatchEvent('hide');
                });
            }
            
            return this;
        }

        /**
         * Mostra overlay de loading
         */
        showOverlay() {
            const overlay = createElement('div', [
                CONFIG.classes.loadingOverlay
            ], {
                'aria-label': this.options.text,
                'role': 'status'
            });
            
            const content = createElement('div', [CONFIG.classes.loadingContent]);
            
            // Spinner
            const spinner = this.createSpinner();
            content.appendChild(spinner);
            
            // Texto
            if (this.options.text) {
                const text = createElement('div', [CONFIG.classes.loadingText]);
                text.textContent = this.options.text;
                content.appendChild(text);
            }
            
            overlay.appendChild(content);
            
            // Posicionamento
            if (this.element === document.body) {
                overlay.classList.add('loading-fullscreen');
            } else {
                this.element.style.position = 'relative';
            }
            
            this.loadingElement = overlay;
            addElementWithAnimation(this.element, overlay);
        }

        /**
         * Mostra loading inline
         */
        showInline() {
            this.saveOriginalContent();
            
            const container = createElement('div', ['loading-inline']);
            const spinner = this.createSpinner();
            container.appendChild(spinner);
            
            if (this.options.text) {
                const text = createElement('span', [CONFIG.classes.loadingText]);
                text.textContent = this.options.text;
                container.appendChild(text);
            }
            
            this.element.innerHTML = '';
            this.element.appendChild(container);
            this.loadingElement = container;
        }

        /**
         * Mostra skeleton screen
         */
        showSkeleton() {
            this.saveOriginalContent();
            
            const skeleton = this.createSkeletonContent();
            this.element.innerHTML = '';
            this.element.appendChild(skeleton);
            this.loadingElement = skeleton;
        }

        /**
         * Cria spinner baseado no tipo
         */
        createSpinner() {
            const spinner = createElement('div', [CONFIG.classes.spinner]);
            
            switch (this.options.spinner) {
                case 'dots':
                    spinner.classList.add('spinner-dots');
                    for (let i = 0; i < 8; i++) {
                        spinner.appendChild(createElement('div'));
                    }
                    break;
                case 'pulse':
                    spinner.classList.add('spinner-pulse');
                    break;
                default:
                    // Spinner padrão já está configurado
                    break;
            }
            
            return spinner;
        }

        /**
         * Cria conteúdo skeleton baseado no elemento
         */
        createSkeletonContent() {
            const container = createElement('div', ['skeleton-container']);
            
            // Detectar tipo de conteúdo e criar skeleton apropriado
            if (this.element.classList.contains('dashboard-card')) {
                return this.createDashboardSkeleton();
            } else if (this.element.tagName === 'TABLE') {
                return this.createTableSkeleton();
            } else if (this.element.classList.contains('card')) {
                return this.createCardSkeleton();
            } else {
                return this.createGenericSkeleton();
            }
        }

        /**
         * Cria skeleton para dashboard card
         */
        createDashboardSkeleton() {
            const skeleton = createElement('div', ['skeleton-dashboard-card']);
            
            // Título
            const heading = createElement('div', [CONFIG.classes.skeletonHeading, 'h3']);
            skeleton.appendChild(heading);
            
            // Valor principal
            const value = createElement('div', [CONFIG.classes.skeletonText]);
            value.style.height = '2em';
            value.style.width = '40%';
            skeleton.appendChild(value);
            
            // Texto adicional
            const text = createElement('div', [CONFIG.classes.skeletonText, 'line-short']);
            skeleton.appendChild(text);
            
            return skeleton;
        }

        /**
         * Cria skeleton para tabela
         */
        createTableSkeleton() {
            const table = createElement('table', ['skeleton-table']);
            const tbody = createElement('tbody');
            
            // Criar 5 linhas de skeleton
            for (let i = 0; i < 5; i++) {
                const row = createElement('tr');
                
                // Criar 4 colunas por linha
                for (let j = 0; j < 4; j++) {
                    const cell = createElement('td');
                    const skeletonCell = createElement('div', ['skeleton-table-cell', CONFIG.classes.skeleton]);
                    cell.appendChild(skeletonCell);
                    row.appendChild(cell);
                }
                
                tbody.appendChild(row);
            }
            
            table.appendChild(tbody);
            return table;
        }

        /**
         * Cria skeleton para card
         */
        createCardSkeleton() {
            const skeleton = createElement('div', [CONFIG.classes.skeletonCard]);
            
            // Header
            const header = createElement('div', ['skeleton-card-header']);
            const avatar = createElement('div', [CONFIG.classes.skeletonAvatar]);
            const headerText = createElement('div', [CONFIG.classes.skeletonHeading]);
            header.appendChild(avatar);
            header.appendChild(headerText);
            skeleton.appendChild(header);
            
            // Body
            const body = createElement('div', ['skeleton-card-body']);
            for (let i = 0; i < 3; i++) {
                const line = createElement('div', [CONFIG.classes.skeletonText, `line-${i + 1}`]);
                body.appendChild(line);
            }
            skeleton.appendChild(body);
            
            return skeleton;
        }

        /**
         * Cria skeleton genérico
         */
        createGenericSkeleton() {
            const skeleton = createElement('div', ['skeleton-generic']);
            
            // Título
            const heading = createElement('div', [CONFIG.classes.skeletonHeading]);
            skeleton.appendChild(heading);
            
            // Linhas de texto
            for (let i = 0; i < 4; i++) {
                const line = createElement('div', [CONFIG.classes.skeletonText, `line-${i + 1}`]);
                skeleton.appendChild(line);
            }
            
            return skeleton;
        }

        /**
         * Salva conteúdo original
         */
        saveOriginalContent() {
            if (!this.originalContent) {
                this.originalContent = this.element.innerHTML;
            }
        }

        /**
         * Restaura conteúdo original
         */
        restoreOriginalContent() {
            if (this.originalContent) {
                this.element.innerHTML = this.originalContent;
                this.element.classList.add(CONFIG.classes.loadingComplete);
                
                // Remover classe após animação
                setTimeout(() => {
                    this.element.classList.remove(CONFIG.classes.loadingComplete);
                }, 500);
            }
        }

        /**
         * Dispatch evento customizado
         */
        dispatchEvent(eventName) {
            const event = new CustomEvent(`loading:${eventName}`, {
                detail: {
                    id: this.id,
                    element: this.element,
                    manager: this
                }
            });
            window.dispatchEvent(event);
        }

        /**
         * Destrói a instância
         */
        destroy() {
            this.hide();
            loadingInstances.delete(this.id);
        }
    }

    // ==========================================================================
    // API Pública
    // ==========================================================================

    const LoadingAPI = {
        /**
         * Cria uma nova instância de loading
         */
        create(element, options = {}) {
            if (typeof element === 'string') {
                element = document.querySelector(element);
            }
            
            if (!element) {
                console.warn('Elemento não encontrado para loading');
                return null;
            }
            
            return new LoadingManager(element, options);
        },

        /**
         * Mostra loading em um elemento
         */
        show(element, options = {}) {
            const manager = this.create(element, options);
            return manager ? manager.show() : null;
        },

        /**
         * Esconde loading de um elemento
         */
        hide(element) {
            if (typeof element === 'string') {
                element = document.querySelector(element);
            }
            
            // Encontrar instância ativa para este elemento
            for (const [id, manager] of loadingInstances) {
                if (manager.element === element && manager.isActive) {
                    manager.hide();
                    return true;
                }
            }
            
            return false;
        },

        /**
         * Mostra loading fullscreen
         */
        showFullscreen(options = {}) {
            return this.show(document.body, {
                type: 'overlay',
                ...options
            });
        },

        /**
         * Esconde loading fullscreen
         */
        hideFullscreen() {
            return this.hide(document.body);
        },

        /**
         * Mostra skeleton em um elemento
         */
        showSkeleton(element, options = {}) {
            return this.show(element, {
                type: 'skeleton',
                ...options
            });
        },

        /**
         * Adiciona loading a um botão
         */
        buttonLoading(button, enable = true) {
            if (typeof button === 'string') {
                button = document.querySelector(button);
            }
            
            if (!button) return;
            
            if (enable) {
                button.classList.add(CONFIG.classes.loading);
                button.disabled = true;
            } else {
                button.classList.remove(CONFIG.classes.loading);
                button.disabled = false;
            }
        },

        /**
         * Adiciona loading a um formulário
         */
        formLoading(form, enable = true) {
            if (typeof form === 'string') {
                form = document.querySelector(form);
            }
            
            if (!form) return;
            
            if (enable) {
                form.classList.add('form-loading');
                const inputs = form.querySelectorAll('input, select, textarea, button');
                inputs.forEach(input => input.disabled = true);
            } else {
                form.classList.remove('form-loading');
                const inputs = form.querySelectorAll('input, select, textarea, button');
                inputs.forEach(input => input.disabled = false);
            }
        },

        /**
         * Obtém instância por ID
         */
        getInstance(id) {
            return loadingInstances.get(id);
        },

        /**
         * Obtém todas as instâncias ativas
         */
        getAllInstances() {
            return Array.from(loadingInstances.values());
        },

        /**
         * Esconde todos os loadings ativos
         */
        hideAll() {
            loadingInstances.forEach(manager => {
                if (manager.isActive) {
                    manager.hide();
                }
            });
        },

        /**
         * Configura textos padrão
         */
        configure(options) {
            Object.assign(CONFIG.texts, options.texts || {});
            Object.assign(CONFIG.durations, options.durations || {});
        }
    };

    // ==========================================================================
    // Integração com AJAX
    // ==========================================================================

    /**
     * Intercepta requisições fetch para mostrar loading automaticamente
     */
    function setupFetchInterceptor() {
        const originalFetch = window.fetch;
        
        window.fetch = function(...args) {
            const url = args[0];
            const options = args[1] || {};
            
            // Verificar se deve mostrar loading
            if (options.showLoading !== false) {
                LoadingAPI.showFullscreen({
                    text: 'Carregando dados...'
                });
            }
            
            return originalFetch.apply(this, args)
                .then(response => {
                    if (options.showLoading !== false) {
                        LoadingAPI.hideFullscreen();
                    }
                    return response;
                })
                .catch(error => {
                    if (options.showLoading !== false) {
                        LoadingAPI.hideFullscreen();
                    }
                    throw error;
                });
        };
    }

    // ==========================================================================
    // Utilitários para Estados Vazios e Erro
    // ==========================================================================

    const StateManager = {
        /**
         * Mostra estado vazio
         */
        showEmpty(element, options = {}) {
            if (typeof element === 'string') {
                element = document.querySelector(element);
            }
            
            const config = {
                icon: 'bi-inbox',
                title: 'Nenhum dado encontrado',
                description: 'Não há informações para exibir no momento.',
                action: null,
                ...options
            };
            
            const emptyState = createElement('div', ['empty-state']);
            
            // Ícone
            const icon = createElement('div', ['empty-state-icon']);
            icon.innerHTML = `<i class="bi ${config.icon}"></i>`;
            emptyState.appendChild(icon);
            
            // Título
            const title = createElement('div', ['empty-state-title']);
            title.textContent = config.title;
            emptyState.appendChild(title);
            
            // Descrição
            if (config.description) {
                const description = createElement('div', ['empty-state-description']);
                description.textContent = config.description;
                emptyState.appendChild(description);
            }
            
            // Ação
            if (config.action) {
                const action = createElement('button', ['btn', 'btn-primary']);
                action.textContent = config.action.text;
                action.addEventListener('click', config.action.handler);
                emptyState.appendChild(action);
            }
            
            element.innerHTML = '';
            element.appendChild(emptyState);
        },

        /**
         * Mostra estado de erro
         */
        showError(element, options = {}) {
            if (typeof element === 'string') {
                element = document.querySelector(element);
            }
            
            const config = {
                icon: 'bi-exclamation-triangle',
                title: 'Erro ao carregar dados',
                description: 'Ocorreu um erro inesperado. Tente novamente.',
                retry: null,
                ...options
            };
            
            const errorState = createElement('div', ['error-state']);
            
            // Ícone
            const icon = createElement('div', ['error-state-icon']);
            icon.innerHTML = `<i class="bi ${config.icon}"></i>`;
            errorState.appendChild(icon);
            
            // Título
            const title = createElement('div', ['error-state-title']);
            title.textContent = config.title;
            errorState.appendChild(title);
            
            // Descrição
            if (config.description) {
                const description = createElement('div', ['error-state-description']);
                description.textContent = config.description;
                errorState.appendChild(description);
            }
            
            // Ações
            const actions = createElement('div', ['error-state-actions']);
            
            if (config.retry) {
                const retryBtn = createElement('button', ['btn', 'btn-primary']);
                retryBtn.textContent = 'Tentar novamente';
                retryBtn.addEventListener('click', config.retry);
                actions.appendChild(retryBtn);
            }
            
            errorState.appendChild(actions);
            
            element.innerHTML = '';
            element.appendChild(errorState);
        }
    };

    // ==========================================================================
    // Inicialização
    // ==========================================================================

    function init() {
        // Configurar interceptor de fetch (opcional)
        // setupFetchInterceptor();
        
        // Expor APIs globais
        window.LoadingManager = LoadingAPI;
        window.StateManager = StateManager;
        
        // Aliases mais curtos
        window.loading = LoadingAPI;
        window.states = StateManager;
        
        console.log('Sistema de loading inicializado');
    }

    // Inicializar quando DOM estiver pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();