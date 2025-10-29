/**
 * notifications.js - Sistema de Notificações e Feedback (ES5)
 * Versão: 1.0 - ES5 compatível
 */

(function() {
    'use strict';

    // Console fallbacks
    if (!window.console) {
        window.console = { log: function(){}, warn: function(){}, error: function(){} };
    } else {
        if (!window.console.log) window.console.log = function(){};
        if (!window.console.warn) window.console.warn = function(){};
        if (!window.console.error) window.console.error = function(){};
    }

    // CustomEvent polyfill
    (function() {
        if (typeof window.CustomEvent === 'function') return;
        function CustomEventPolyfill(event, params) {
            params = params || { bubbles: false, cancelable: false, detail: undefined };
            var evt = document.createEvent('CustomEvent');
            evt.initCustomEvent(event, params.bubbles, params.cancelable, params.detail);
            return evt;
        }
        CustomEventPolyfill.prototype = window.Event ? window.Event.prototype : {};
        window.CustomEvent = CustomEventPolyfill;
    })();

    // Simple Object.assign polyfill
    function extend(target) {
        target = target || {};
        for (var i = 1; i < arguments.length; i++) {
            var source = arguments[i] || {};
            for (var key in source) {
                if (Object.prototype.hasOwnProperty.call(source, key)) {
                    target[key] = source[key];
                }
            }
        }
        return target;
    }

    // Minimal Map replacement (values/forEach used)
    function SimpleMap() {
        this._store = {};
    }
    SimpleMap.prototype.set = function(key, value) {
        this._store[String(key)] = value;
    };
    SimpleMap.prototype.get = function(key) {
        return this._store[String(key)];
    };
    SimpleMap.prototype.has = function(key) {
        return Object.prototype.hasOwnProperty.call(this._store, String(key));
    };
    SimpleMap.prototype.delete = function(key) {
        if (this.has(key)) {
            delete this._store[String(key)];
            return true;
        }
        return false;
    };
    SimpleMap.prototype.values = function() {
        var arr = [];
        for (var k in this._store) {
            if (Object.prototype.hasOwnProperty.call(this._store, k)) {
                arr.push(this._store[k]);
            }
        }
        return arr;
    };
    SimpleMap.prototype.forEach = function(callback) {
        var vals = this.values();
        for (var i = 0; i < vals.length; i++) {
            callback(vals[i], i);
        }
    };

    // ======================================================================
    // Configurações e Constantes
    // ======================================================================

    var CONFIG = {
        durations: {
            success: 4000,
            error: 8000,
            warning: 6000,
            info: 5000,
            default: 5000
        },
        positions: {
            'top-right': 'top-right',
            'top-left': 'top-left',
            'top-center': 'top-center',
            'bottom-right': 'bottom-right',
            'bottom-left': 'bottom-left',
            'bottom-center': 'bottom-center'
        },
        defaults: {
            position: 'top-right',
            closable: true,
            progress: true,
            pauseOnHover: true,
            sound: false,
            type: 'default',
            duration: 5000
        },
        maxToasts: 5,
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

    // ======================================================================
    // Estado Global
    // ======================================================================

    var toastCounter = 0;
    var activeToasts = new SimpleMap();
    var containers = new SimpleMap();

    // ======================================================================
    // Utilitários
    // ======================================================================

    function generateId() {
        return 'toast-' + (++toastCounter) + '-' + Date.now();
    }

    function sanitizeText(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function createElement(tag, classes, attributes) {
        classes = classes || [];
        attributes = attributes || {};
        var element = document.createElement(tag);
        if (classes && classes.length > 0) {
            element.className = classes.join(' ');
        }
        for (var key in attributes) {
            if (Object.prototype.hasOwnProperty.call(attributes, key)) {
                element.setAttribute(key, attributes[key]);
            }
        }
        return element;
    }

    function getContainer(position) {
        position = position || CONFIG.defaults.position;
        if (containers.has(position)) {
            return containers.get(position);
        }
        var container = createElement('div', [
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

    function getIcon(type) {
        var icons = {
            success: 'bi-check-circle-fill',
            error: 'bi-x-circle-fill',
            warning: 'bi-exclamation-triangle-fill',
            info: 'bi-info-circle-fill',
            default: 'bi-bell-fill'
        };
        return icons[type] || icons.default;
    }

    // ======================================================================
    // Classe Toast (ES5)
    // ======================================================================

    function Toast(options) {
        this.id = generateId();
        this.options = extend({}, CONFIG.defaults, options || {});
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

    Toast.prototype.create = function() {
        var self = this;
        this.element = createElement('div', [
            CONFIG.classes.toast,
            'toast-' + (this.options.type || 'default')
        ], {
            'id': this.id,
            'role': 'alert',
            'aria-live': 'assertive',
            'aria-atomic': 'true'
        });

        // Ícone
        if (this.options.icon !== false) {
            var iconElement = createElement('div', [CONFIG.classes.icon]);
            iconElement.innerHTML = '<i class="bi ' + getIcon(this.options.type) + '" aria-hidden="true"></i>';
            this.element.appendChild(iconElement);
        }

        // Conteúdo
        var contentElement = createElement('div', [CONFIG.classes.content]);

        // Título
        if (this.options.title) {
            var titleElement = createElement('div', [CONFIG.classes.title]);
            titleElement.textContent = this.options.title;
            contentElement.appendChild(titleElement);
        }

        // Mensagem
        if (this.options.message) {
            var messageElement = createElement('div', [CONFIG.classes.message]);
            messageElement.textContent = this.options.message;
            contentElement.appendChild(messageElement);
        }

        // Ações
        if (this.options.actions && this.options.actions.length > 0) {
            var actionsElement = createElement('div', [CONFIG.classes.actions]);
            for (var i = 0; i < this.options.actions.length; i++) {
                var action = this.options.actions[i] || {};
                var actionButton = createElement('button', [
                    CONFIG.classes.action,
                    action.style || 'secondary'
                ]);
                actionButton.textContent = action.text || '';
                actionButton.addEventListener('click', (function(handler) {
                    return function() {
                        if (typeof handler === 'function') { handler(); }
                        self.close();
                    };
                })(action.handler));
                actionsElement.appendChild(actionButton);
            }
            contentElement.appendChild(actionsElement);
        }

        this.element.appendChild(contentElement);

        // Botão de fechar
        if (this.options.closable) {
            var closeButton = createElement('button', [CONFIG.classes.close], {
                'aria-label': 'Fechar notificação',
                'type': 'button'
            });
            closeButton.innerHTML = '<i class="bi bi-x" aria-hidden="true"></i>';
            closeButton.addEventListener('click', function() { self.close(); });
            this.element.appendChild(closeButton);
        }

        // Barra de progresso
        if (this.options.progress && this.options.duration > 0) {
            this.progressElement = createElement('div', [CONFIG.classes.progress]);
            this.element.appendChild(this.progressElement);
        }

        // Event listeners
        if (this.options.pauseOnHover) {
            this.element.addEventListener('mouseenter', function() { self.pause(); });
            this.element.addEventListener('mouseleave', function() { self.resume(); });
        }

        // Acessibilidade - foco
        this.element.addEventListener('focus', function() { self.pause(); });
        this.element.addEventListener('blur', function() { self.resume(); });
    };

    Toast.prototype.show = function() {
        var container = getContainer(this.options.position);
        this.limitToasts(container);
        container.appendChild(this.element);
        activeToasts.set(this.id, this);
        if (this.options.duration > 0) {
            this.startTimer();
        }
        this.dispatchEvent('show');
        if (this.options.sound) { this.playSound(); }
    };

    Toast.prototype.limitToasts = function(container) {
        var toasts = container.querySelectorAll('.' + CONFIG.classes.toast);
        if (toasts.length >= CONFIG.maxToasts) {
            var oldestToast = toasts[0];
            var toastId = oldestToast.id;
            if (activeToasts.has(toastId)) {
                var t = activeToasts.get(toastId);
                if (t && typeof t.close === 'function') { t.close(); }
            }
        }
    };

    Toast.prototype.startTimer = function() {
        var self = this;
        this.startTime = Date.now();
        this.remainingTime = this.options.duration;
        this.timer = setTimeout(function() { self.close(); }, this.options.duration);
        if (this.progressElement) { this.startProgress(); }
    };

    Toast.prototype.startProgress = function() {
        try {
            this.progressElement.style.width = '100%';
            this.progressElement.style.transitionDuration = String(this.options.duration) + 'ms';
            // Force reflow
            /* eslint-disable no-unused-expressions */
            this.progressElement.offsetWidth;
            /* eslint-enable no-unused-expressions */
            this.progressElement.style.width = '0%';
        } catch (e) {}
    };

    Toast.prototype.pause = function() {
        if (this.isPaused || !this.timer) return;
        this.isPaused = true;
        clearTimeout(this.timer);
        var elapsed = Date.now() - this.startTime;
        this.remainingTime = Math.max(0, this.options.duration - elapsed);
        if (this.progressElement) {
            try { this.progressElement.style.animationPlayState = 'paused'; } catch (e) {}
        }
        this.dispatchEvent('pause');
    };

    Toast.prototype.resume = function() {
        if (!this.isPaused || this.remainingTime <= 0) return;
        var self = this;
        this.isPaused = false;
        this.startTime = Date.now();
        this.timer = setTimeout(function() { self.close(); }, this.remainingTime);
        if (this.progressElement) {
            try {
                this.progressElement.style.transitionDuration = String(this.remainingTime) + 'ms';
                this.progressElement.style.animationPlayState = 'running';
            } catch (e) {}
        }
        this.dispatchEvent('resume');
    };

    Toast.prototype.close = function() {
        if (!this.element || !this.element.parentNode) return;
        if (this.timer) { clearTimeout(this.timer); this.timer = null; }
        if (this.element.classList) { this.element.classList.add('hiding'); }
        var self = this;
        setTimeout(function() {
            if (self.element && self.element.parentNode) {
                self.element.parentNode.removeChild(self.element);
            }
            activeToasts.delete(self.id);
            self.dispatchEvent('close');
        }, 300);
    };

    Toast.prototype.playSound = function() {
        // Placeholder para som (desativado por padrão)
        // var audio = new Audio('/static/sounds/notification.mp3');
        // audio.play();
    };

    Toast.prototype.dispatchEvent = function(eventName) {
        var event = new CustomEvent('toast:' + eventName, {
            detail: {
                id: this.id,
                type: this.options.type,
                toast: this
            }
        });
        window.dispatchEvent(event);
    };

    // ======================================================================
    // API Pública
    // ======================================================================

    var NotificationManager = {
        show: function(options) {
            if (typeof options === 'string') { options = { message: options }; }
            return new Toast(options);
        },
        success: function(message, options) {
            options = options || {};
            var opts = extend({}, { type: 'success', message: message, duration: CONFIG.durations.success }, options);
            return this.show(opts);
        },
        error: function(message, options) {
            options = options || {};
            var opts = extend({}, { type: 'error', message: message, duration: CONFIG.durations.error }, options);
            return this.show(opts);
        },
        warning: function(message, options) {
            options = options || {};
            var opts = extend({}, { type: 'warning', message: message, duration: CONFIG.durations.warning }, options);
            return this.show(opts);
        },
        info: function(message, options) {
            options = options || {};
            var opts = extend({}, { type: 'info', message: message, duration: CONFIG.durations.info }, options);
            return this.show(opts);
        },
        closeAll: function() {
            activeToasts.forEach(function(toast) { if (toast && toast.close) toast.close(); });
        },
        close: function(id) {
            if (activeToasts.has(id)) {
                var t = activeToasts.get(id);
                if (t && t.close) t.close();
            }
        },
        get: function(id) { return activeToasts.get(id); },
        getAll: function() { return activeToasts.values(); },
        configure: function(options) { extend(CONFIG.defaults, options || {}); }
    };

    // ======================================================================
    // Integração com Flask Flash Messages
    // ======================================================================

    function processFlashMessages() {
        var flashMessages = window.flashMessages || [];
        for (var i = 0; i < flashMessages.length; i++) {
            var flash = flashMessages[i] || {};
            var type = flash.category || 'info';
            var message = flash.message;
            NotificationManager.show({
                type: (type === 'message' ? 'info' : type),
                message: message,
                title: getFlashTitle(type)
            });
        }
        window.flashMessages = [];
    }

    function getFlashTitle(type) {
        var titles = {
            success: 'Sucesso',
            error: 'Erro',
            warning: 'Atenção',
            info: 'Informação',
            message: 'Informação'
        };
        return titles[type] || 'Notificação';
    }

    // ======================================================================
    // Inicialização
    // ======================================================================

    function init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', processFlashMessages);
        } else {
            processFlashMessages();
        }
        window.NotificationManager = NotificationManager;
        window.notify = NotificationManager;
        console.log('Sistema de notificações inicializado');
    }

    init();
})();