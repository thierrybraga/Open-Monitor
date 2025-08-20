/**
 * notifications.js - Sistema de Notificações e Feedback
 * Versão: 1.0 - Criado em Janeiro 2025
 * Sistema completo de toasts, alertas e feedback visual
 */

(function() {
    'use strict';

    // ==========================================================================
    // Configurações e Constantes
    // ==========================================================================

    const CONFIG = {
        // Durações padrão (em ms)
        durations: {
            success: 4000,
            error: 8000,
            warning: 6000,
            info: 5000,
            default: 5000
        },
        
        // Posições disponíveis
        positions: {
            'top-right': 'top-right',
            'top-left': 'top-left',
            'top-center': 'top-center',
            'bottom-right': 'bottom-right',
            'bottom-left': 'bottom-left',
            'bottom-center': 'bottom-center'
        },
        
        // Configurações padrão
        defaults: {
            position: 'top-right',
            closable: true,
            progress: true,
            pauseOnHover: true,
            sound: false
        },
        
        // Máximo de toasts simultâneos
        maxToasts: 5,
        
        // Classes CSS
        classes: {
            container: 'toast-container',
            toast: 'toast',
            icon: 'toast-icon',
            content: 'toast-content',
            title: 'toast-title',
            message: 'toast-message',
            close: 'toast-close',
            progress: 'toast-progress',
            actions: 'toast-actions',
            action: 'toast-action'
        }
    };

    // ==========================================================================
    // Estado Global
    // ==========================================================================

    let toastCounter = 0;
    let activeToasts = new Map();
    let containers = new Map();

    // ==========================================================================
    // Utilitários
    // ==========================================================================

    /**
     * Gera um ID único para o toast
     */
    function generateId() {
        return `toast-${++toastCounter}-${Date.now()}`;
    }

    /**
     * Sanitiza texto para prevenir XSS
     */
    function sanitizeText(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Cria um elemento DOM com classes e atributos
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
     * Obtém ou cria um container para a posição especificada
     */
    function getContainer(position) {
        if (containers.has(position)) {
            return containers.get(position);
        }
        
        const container = createElement('div', [
            CONFIG.classes.container,
            position
        ], {
            'aria-live': 'polite',
            'aria-label': 'Notificações'
        });
        
        document.body.appendChild(container);
        containers.set(position, container);
        
        return container;
    }

    /**
     * Obtém o ícone apropriado para o tipo de toast
     */
    function getIcon(type) {
        const icons = {
            success: 'bi-check-circle-fill',
            error: 'bi-x-circle-fill',
            warning: 'bi-exclamation-triangle-fill',
            info: 'bi-info-circle-fill',
            default: 'bi-bell-fill'
        };
        
        return icons[type] || icons.default;
    }

    // ==========================================================================
    // Classe Toast
    // ==========================================================================

    class Toast {
        constructor(options) {
            this.id = generateId();
            this.options = { ...CONFIG.defaults, ...options };
            this.element = null;
            this.progressElement = null;
            this.timer = null;
            this.progressTimer = null;
            this.isPaused = false;
            this.startTime = null;
            this.remainingTime = null;
            
            this.create();
            this.show();
        }

        /**
         * Cria o elemento DOM do toast
         */
        create() {
            // Container principal do toast
            this.element = createElement('div', [
                CONFIG.classes.toast,
                `toast-${this.options.type || 'default'}`
            ], {
                'id': this.id,
                'role': 'alert',
                'aria-live': 'assertive',
                'aria-atomic': 'true'
            });

            // Ícone
            if (this.options.icon !== false) {
                const iconElement = createElement('div', [CONFIG.classes.icon]);
                iconElement.innerHTML = `<i class="bi ${getIcon(this.options.type)}" aria-hidden="true"></i>`;
                this.element.appendChild(iconElement);
            }

            // Conteúdo
            const contentElement = createElement('div', [CONFIG.classes.content]);
            
            // Título
            if (this.options.title) {
                const titleElement = createElement('div', [CONFIG.classes.title]);
                titleElement.textContent = this.options.title;
                contentElement.appendChild(titleElement);
            }
            
            // Mensagem
            if (this.options.message) {
                const messageElement = createElement('div', [CONFIG.classes.message]);
                messageElement.textContent = this.options.message;
                contentElement.appendChild(messageElement);
            }
            
            // Ações
            if (this.options.actions && this.options.actions.length > 0) {
                const actionsElement = createElement('div', [CONFIG.classes.actions]);
                
                this.options.actions.forEach(action => {
                    const actionButton = createElement('button', [
                        CONFIG.classes.action,
                        action.style || 'secondary'
                    ]);
                    actionButton.textContent = action.text;
                    actionButton.addEventListener('click', () => {
                        if (action.handler) action.handler();
                        this.close();
                    });
                    actionsElement.appendChild(actionButton);
                });
                
                contentElement.appendChild(actionsElement);
            }
            
            this.element.appendChild(contentElement);

            // Botão de fechar
            if (this.options.closable) {
                const closeButton = createElement('button', [CONFIG.classes.close], {
                    'aria-label': 'Fechar notificação',
                    'type': 'button'
                });
                closeButton.innerHTML = '<i class="bi bi-x" aria-hidden="true"></i>';
                closeButton.addEventListener('click', () => this.close());
                this.element.appendChild(closeButton);
            }

            // Barra de progresso
            if (this.options.progress && this.options.duration > 0) {
                this.progressElement = createElement('div', [CONFIG.classes.progress]);
                this.element.appendChild(this.progressElement);
            }

            // Event listeners
            if (this.options.pauseOnHover) {
                this.element.addEventListener('mouseenter', () => this.pause());
                this.element.addEventListener('mouseleave', () => this.resume());
            }

            // Acessibilidade - foco
            this.element.addEventListener('focus', () => this.pause());
            this.element.addEventListener('blur', () => this.resume());
        }

        /**
         * Exibe o toast
         */
        show() {
            const container = getContainer(this.options.position);
            
            // Limitar número de toasts
            this.limitToasts(container);
            
            container.appendChild(this.element);
            activeToasts.set(this.id, this);
            
            // Iniciar timer se tiver duração
            if (this.options.duration > 0) {
                this.startTimer();
            }
            
            // Dispatch evento
            this.dispatchEvent('show');
            
            // Som (se habilitado)
            if (this.options.sound) {
                this.playSound();
            }
        }

        /**
         * Limita o número de toasts visíveis
         */
        limitToasts(container) {
            const toasts = container.querySelectorAll(`.${CONFIG.classes.toast}`);
            if (toasts.length >= CONFIG.maxToasts) {
                const oldestToast = toasts[0];
                const toastId = oldestToast.id;
                if (activeToasts.has(toastId)) {
                    activeToasts.get(toastId).close();
                }
            }
        }

        /**
         * Inicia o timer de auto-close
         */
        startTimer() {
            this.startTime = Date.now();
            this.remainingTime = this.options.duration;
            
            this.timer = setTimeout(() => {
                this.close();
            }, this.options.duration);
            
            // Iniciar progresso
            if (this.progressElement) {
                this.startProgress();
            }
        }

        /**
         * Inicia a animação da barra de progresso
         */
        startProgress() {
            this.progressElement.style.width = '100%';
            this.progressElement.style.transitionDuration = `${this.options.duration}ms`;
            
            // Forçar reflow
            this.progressElement.offsetWidth;
            
            this.progressElement.style.width = '0%';
        }

        /**
         * Pausa o timer
         */
        pause() {
            if (this.isPaused || !this.timer) return;
            
            this.isPaused = true;
            clearTimeout(this.timer);
            
            // Calcular tempo restante
            const elapsed = Date.now() - this.startTime;
            this.remainingTime = Math.max(0, this.options.duration - elapsed);
            
            // Pausar progresso
            if (this.progressElement) {
                this.progressElement.style.animationPlayState = 'paused';
            }
            
            this.dispatchEvent('pause');
        }

        /**
         * Resume o timer
         */
        resume() {
            if (!this.isPaused || this.remainingTime <= 0) return;
            
            this.isPaused = false;
            this.startTime = Date.now();
            
            this.timer = setTimeout(() => {
                this.close();
            }, this.remainingTime);
            
            // Resumir progresso
            if (this.progressElement) {
                this.progressElement.style.transitionDuration = `${this.remainingTime}ms`;
                this.progressElement.style.animationPlayState = 'running';
            }
            
            this.dispatchEvent('resume');
        }

        /**
         * Fecha o toast
         */
        close() {
            if (!this.element || !this.element.parentNode) return;
            
            // Limpar timers
            if (this.timer) {
                clearTimeout(this.timer);
                this.timer = null;
            }
            
            // Adicionar classe de saída
            this.element.classList.add('hiding');
            
            // Aguardar animação e remover
            setTimeout(() => {
                if (this.element && this.element.parentNode) {
                    this.element.parentNode.removeChild(this.element);
                }
                activeToasts.delete(this.id);
                this.dispatchEvent('close');
            }, 300);
        }

        /**
         * Toca som de notificação
         */
        playSound() {
            // Implementar som se necessário
            // const audio = new Audio('/static/sounds/notification.mp3');
            // audio.play().catch(() => {});
        }

        /**
         * Dispatch evento customizado
         */
        dispatchEvent(eventName) {
            const event = new CustomEvent(`toast:${eventName}`, {
                detail: {
                    id: this.id,
                    type: this.options.type,
                    toast: this
                }
            });
            window.dispatchEvent(event);
        }
    }

    // ==========================================================================
    // API Pública
    // ==========================================================================

    const NotificationManager = {
        /**
         * Exibe um toast
         */
        show(options) {
            if (typeof options === 'string') {
                options = { message: options };
            }
            
            return new Toast(options);
        },

        /**
         * Exibe toast de sucesso
         */
        success(message, options = {}) {
            return this.show({
                type: 'success',
                message,
                duration: CONFIG.durations.success,
                ...options
            });
        },

        /**
         * Exibe toast de erro
         */
        error(message, options = {}) {
            return this.show({
                type: 'error',
                message,
                duration: CONFIG.durations.error,
                ...options
            });
        },

        /**
         * Exibe toast de aviso
         */
        warning(message, options = {}) {
            return this.show({
                type: 'warning',
                message,
                duration: CONFIG.durations.warning,
                ...options
            });
        },

        /**
         * Exibe toast de informação
         */
        info(message, options = {}) {
            return this.show({
                type: 'info',
                message,
                duration: CONFIG.durations.info,
                ...options
            });
        },

        /**
         * Fecha todos os toasts
         */
        closeAll() {
            activeToasts.forEach(toast => toast.close());
        },

        /**
         * Fecha toast por ID
         */
        close(id) {
            if (activeToasts.has(id)) {
                activeToasts.get(id).close();
            }
        },

        /**
         * Obtém toast por ID
         */
        get(id) {
            return activeToasts.get(id);
        },

        /**
         * Obtém todos os toasts ativos
         */
        getAll() {
            return Array.from(activeToasts.values());
        },

        /**
         * Configura opções padrão
         */
        configure(options) {
            Object.assign(CONFIG.defaults, options);
        }
    };

    // ==========================================================================
    // Integração com Flask Flash Messages
    // ==========================================================================

    /**
     * Converte mensagens flash do Flask em toasts
     */
    function processFlashMessages() {
        const flashMessages = window.flashMessages || [];
        
        flashMessages.forEach(flash => {
            const type = flash.category || 'info';
            const message = flash.message;
            
            NotificationManager.show({
                type: type === 'message' ? 'info' : type,
                message: message,
                title: getFlashTitle(type)
            });
        });
        
        // Limpar mensagens processadas
        window.flashMessages = [];
    }

    /**
     * Obtém título baseado no tipo de flash
     */
    function getFlashTitle(type) {
        const titles = {
            success: 'Sucesso',
            error: 'Erro',
            warning: 'Atenção',
            info: 'Informação',
            message: 'Informação'
        };
        
        return titles[type] || 'Notificação';
    }

    // ==========================================================================
    // Inicialização
    // ==========================================================================

    function init() {
        // Processar mensagens flash existentes
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', processFlashMessages);
        } else {
            processFlashMessages();
        }
        
        // Expor API global
        window.NotificationManager = NotificationManager;
        window.notify = NotificationManager; // Alias mais curto
        
        console.log('Sistema de notificações inicializado');
    }

    // Inicializar
    init();

})();