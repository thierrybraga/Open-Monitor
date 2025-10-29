/**
 * loading.js - Gerenciamento de Estados de Carregamento (ES5 Compat)
 * Versão: 1.0 - Atualizado para compatibilidade ES5
 * Sistema para gerenciar loading states, skeleton screens e feedback visual
 */

(function() {
    'use strict';

    // ==========================================================================
    // Configurações e Constantes
    // ==========================================================================

    var CONFIG = {
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
        durations: {
            fadeIn: 300,
            fadeOut: 300,
            skeleton: 1500,
            spinner: 1000
        },
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

    var loadingInstances = {}; // Substitui Map por objeto simples
    var loadingCounter = 0;

    // ==========================================================================
    // Utilitários
    // ==========================================================================

    function generateId() {
        loadingCounter += 1;
        return 'loading-' + loadingCounter + '-' + Date.now();
    }

    function createElement(tag, classes, attributes) {
        classes = classes || [];
        attributes = attributes || {};
        var element = document.createElement(tag);
        if (classes.length > 0) { element.className = classes.join(' '); }
        for (var key in attributes) {
            if (Object.prototype.hasOwnProperty.call(attributes, key)) {
                element.setAttribute(key, attributes[key]);
            }
        }
        return element;
    }

    // Thenable simples para evitar dependência de Promise
    function createThenable(executor) {
        var callbacks = [];
        var resolved = false;
        var value;
        function resolve(val) {
            resolved = true;
            value = val;
            for (var i = 0; i < callbacks.length; i++) {
                try { callbacks[i](val); } catch(_){}
            }
        }
        try { executor(resolve); } catch(_){}
        return {
            then: function(cb) {
                if (typeof cb === 'function') {
                    if (resolved) { try { cb(value); } catch(_){} }
                    else { callbacks.push(cb); }
                }
                return this;
            }
        };
    }

    function removeElementWithAnimation(element, duration) {
        duration = (typeof duration === 'undefined') ? CONFIG.durations.fadeOut : duration;
        if (!element || !element.parentNode) {
            return createThenable(function(resolve){ resolve(); });
        }
        return createThenable(function(resolve) {
            element.style.transition = 'opacity ' + duration + 'ms ease-out';
            element.style.opacity = '0';
            setTimeout(function() {
                if (element.parentNode) { element.parentNode.removeChild(element); }
                resolve();
            }, duration);
        });
    }

    function addElementWithAnimation(parent, element, duration) {
        duration = (typeof duration === 'undefined') ? CONFIG.durations.fadeIn : duration;
        element.style.opacity = '0';
        parent.appendChild(element);
        element.offsetHeight; // Forçar reflow
        element.style.transition = 'opacity ' + duration + 'ms ease-out';
        element.style.opacity = '1';
    }

    function mergeOptions(target, source) {
        target = target || {};
        source = source || {};
        for (var key in source) {
            if (Object.prototype.hasOwnProperty.call(source, key)) {
                target[key] = source[key];
            }
        }
        return target;
    }

    function createCustomEvent(name, detail) {
        try { return new CustomEvent(name, { detail: detail }); } catch(e) {
            var evt = document.createEvent('CustomEvent');
            if (evt.initCustomEvent) { evt.initCustomEvent(name, true, true, detail); }
            else { evt.initEvent(name, true, true); evt.detail = detail; }
            return evt;
        }
    }

    // ==========================================================================
    // Classe LoadingManager (ES5)
    // ==========================================================================

    function LoadingManager(element, options) {
        this.id = generateId();
        this.element = element;
        this.options = {
            type: 'overlay',
            text: CONFIG.texts.loading,
            spinner: 'default',
            position: 'center',
            backdrop: true
        };
        this.options = mergeOptions(this.options, options || {});
        this.loadingElement = null;
        this.originalContent = null;
        this.isActive = false;
        loadingInstances[this.id] = this;
    }

    LoadingManager.prototype.show = function() {
        if (this.isActive) return this;
        this.isActive = true;
        if (this.options.type === 'inline') { this.showInline(); }
        else if (this.options.type === 'skeleton') { this.showSkeleton(); }
        else { this.showOverlay(); }
        this.dispatchEvent('show');
        return this;
    };

    LoadingManager.prototype.hide = function() {
        if (!this.isActive) return this;
        this.isActive = false;
        var self = this;
        if (this.loadingElement) {
            removeElementWithAnimation(this.loadingElement).then(function() {
                self.loadingElement = null;
                self.restoreOriginalContent();
                self.dispatchEvent('hide');
            });
        }
        return this;
    };

    LoadingManager.prototype.showOverlay = function() {
        var overlay = createElement('div', [CONFIG.classes.loadingOverlay], { 'aria-label': this.options.text, 'role': 'status' });
        var content = createElement('div', [CONFIG.classes.loadingContent]);
        var spinner = this.createSpinner();
        content.appendChild(spinner);
        if (this.options.text) {
            var text = createElement('div', [CONFIG.classes.loadingText]);
            text.textContent = this.options.text;
            content.appendChild(text);
        }
        overlay.appendChild(content);
        if (this.element === document.body) { overlay.classList.add('loading-fullscreen'); }
        else { this.element.style.position = 'relative'; }
        this.loadingElement = overlay;
        addElementWithAnimation(this.element, overlay);
    };

    LoadingManager.prototype.showInline = function() {
        this.saveOriginalContent();
        var container = createElement('div', ['loading-inline']);
        var spinner = this.createSpinner();
        container.appendChild(spinner);
        if (this.options.text) {
            var text = createElement('span', [CONFIG.classes.loadingText]);
            text.textContent = this.options.text;
            container.appendChild(text);
        }
        this.element.innerHTML = '';
        this.element.appendChild(container);
        this.loadingElement = container;
    };

    LoadingManager.prototype.showSkeleton = function() {
        this.saveOriginalContent();
        var skeleton = this.createSkeletonContent();
        this.element.innerHTML = '';
        this.element.appendChild(skeleton);
        this.loadingElement = skeleton;
    };

    LoadingManager.prototype.createSpinner = function() {
        var spinner = createElement('div', [CONFIG.classes.spinner]);
        switch (this.options.spinner) {
            case 'dots':
                spinner.classList.add('spinner-dots');
                for (var i = 0; i < 8; i++) { spinner.appendChild(createElement('div')); }
                break;
            case 'pulse':
                spinner.classList.add('spinner-pulse');
                break;
            default:
                break;
        }
        return spinner;
    };

    LoadingManager.prototype.createSkeletonContent = function() {
        var container = createElement('div', ['skeleton-container']);
        if (this.element.classList && this.element.classList.contains('dashboard-card')) {
            return this.createDashboardSkeleton();
        } else if (this.element.tagName === 'TABLE') {
            return this.createTableSkeleton();
        } else if (this.element.classList && this.element.classList.contains('card')) {
            return this.createCardSkeleton();
        } else {
            return this.createGenericSkeleton();
        }
    };

    LoadingManager.prototype.createDashboardSkeleton = function() {
        var skeleton = createElement('div', ['skeleton-dashboard-card']);
        var heading = createElement('div', [CONFIG.classes.skeletonHeading, 'h3']);
        skeleton.appendChild(heading);
        var value = createElement('div', [CONFIG.classes.skeletonText]);
        value.style.height = '2em';
        value.style.width = '40%';
        skeleton.appendChild(value);
        var text = createElement('div', [CONFIG.classes.skeletonText, 'line-short']);
        skeleton.appendChild(text);
        return skeleton;
    };

    LoadingManager.prototype.createTableSkeleton = function() {
        var table = createElement('table', ['skeleton-table']);
        var tbody = createElement('tbody');
        for (var i = 0; i < 5; i++) {
            var row = createElement('tr');
            for (var j = 0; j < 4; j++) {
                var cell = createElement('td');
                var skeletonCell = createElement('div', ['skeleton-table-cell', CONFIG.classes.skeleton]);
                cell.appendChild(skeletonCell);
                row.appendChild(cell);
            }
            tbody.appendChild(row);
        }
        table.appendChild(tbody);
        return table;
    };

    LoadingManager.prototype.createCardSkeleton = function() {
        var skeleton = createElement('div', [CONFIG.classes.skeletonCard]);
        var header = createElement('div', ['skeleton-card-header']);
        var avatar = createElement('div', [CONFIG.classes.skeletonAvatar]);
        var headerText = createElement('div', [CONFIG.classes.skeletonHeading]);
        header.appendChild(avatar);
        header.appendChild(headerText);
        skeleton.appendChild(header);
        var body = createElement('div', ['skeleton-card-body']);
        for (var i = 0; i < 3; i++) {
            var line = createElement('div', [CONFIG.classes.skeletonText, 'line-' + (i + 1)]);
            body.appendChild(line);
        }
        skeleton.appendChild(body);
        return skeleton;
    };

    LoadingManager.prototype.createGenericSkeleton = function() {
        var skeleton = createElement('div', ['skeleton-generic']);
        var heading = createElement('div', [CONFIG.classes.skeletonHeading]);
        skeleton.appendChild(heading);
        for (var i = 0; i < 4; i++) {
            var line = createElement('div', [CONFIG.classes.skeletonText, 'line-' + (i + 1)]);
            skeleton.appendChild(line);
        }
        return skeleton;
    };

    LoadingManager.prototype.saveOriginalContent = function() {
        if (!this.originalContent) { this.originalContent = this.element.innerHTML; }
    };

    LoadingManager.prototype.restoreOriginalContent = function() {
        if (this.originalContent) {
            this.element.innerHTML = this.originalContent;
            if (this.element.classList) {
                this.element.classList.add(CONFIG.classes.loadingComplete);
                var self = this;
                setTimeout(function() { self.element.classList.remove(CONFIG.classes.loadingComplete); }, 500);
            }
        }
    };

    LoadingManager.prototype.dispatchEvent = function(eventName) {
        var event = createCustomEvent('loading:' + eventName, {
            id: this.id,
            element: this.element,
            manager: this
        });
        window.dispatchEvent(event);
    };

    LoadingManager.prototype.destroy = function() {
        this.hide();
        try { delete loadingInstances[this.id]; } catch(_){}
    };

    // ==========================================================================
    // API Pública
    // ==========================================================================

    var LoadingAPI = {
        create: function(element, options) {
            options = options || {};
            if (typeof element === 'string') { element = document.querySelector(element); }
            if (!element) { try { console.warn('Elemento não encontrado para loading'); } catch(_){} return null; }
            return new LoadingManager(element, options);
        },
        show: function(element, options) {
            options = options || {};
            var manager = this.create(element, options);
            return manager ? manager.show() : null;
        },
        hide: function(element) {
            if (typeof element === 'string') { element = document.querySelector(element); }
            for (var id in loadingInstances) {
                if (Object.prototype.hasOwnProperty.call(loadingInstances, id)) {
                    var manager = loadingInstances[id];
                    if (manager && manager.element === element && manager.isActive) { manager.hide(); return true; }
                }
            }
            return false;
        },
        showFullscreen: function(options) {
            options = options || {};
            var opts = {};
            opts = mergeOptions(opts, options);
            opts.type = 'overlay';
            return this.show(document.body, opts);
        },
        hideFullscreen: function() {
            return this.hide(document.body);
        },
        showSkeleton: function(element, options) {
            options = options || {};
            var opts = {};
            opts = mergeOptions(opts, options);
            opts.type = 'skeleton';
            return this.show(element, opts);
        },
        buttonLoading: function(button, enable) {
            if (typeof enable === 'undefined') enable = true;
            if (typeof button === 'string') { button = document.querySelector(button); }
            if (!button) return;
            if (enable) {
                if (button.classList) { button.classList.add(CONFIG.classes.loading); }
                button.disabled = true;
            } else {
                if (button.classList) { button.classList.remove(CONFIG.classes.loading); }
                button.disabled = false;
            }
        },
        formLoading: function(form, enable) {
            if (typeof enable === 'undefined') enable = true;
            if (typeof form === 'string') { form = document.querySelector(form); }
            if (!form) return;
            if (enable) {
                if (form.classList) { form.classList.add('form-loading'); }
                var inputs = form.querySelectorAll('input, select, textarea, button');
                Array.prototype.forEach.call(inputs, function(input) { input.disabled = true; });
            } else {
                if (form.classList) { form.classList.remove('form-loading'); }
                var inputs2 = form.querySelectorAll('input, select, textarea, button');
                Array.prototype.forEach.call(inputs2, function(input) { input.disabled = false; });
            }
        },
        getInstance: function(id) {
            return loadingInstances[id] || null;
        },
        getAllInstances: function() {
            var arr = [];
            for (var id in loadingInstances) {
                if (Object.prototype.hasOwnProperty.call(loadingInstances, id)) { arr.push(loadingInstances[id]); }
            }
            return arr;
        },
        hideAll: function() {
            for (var id in loadingInstances) {
                if (Object.prototype.hasOwnProperty.call(loadingInstances, id)) {
                    var manager = loadingInstances[id];
                    if (manager && manager.isActive) { manager.hide(); }
                }
            }
        },
        configure: function(options) {
            options = options || {};
            if (options.texts) { for (var k in options.texts) { if (Object.prototype.hasOwnProperty.call(options.texts, k)) { CONFIG.texts[k] = options.texts[k]; } } }
            if (options.durations) { for (var d in options.durations) { if (Object.prototype.hasOwnProperty.call(options.durations, d)) { CONFIG.durations[d] = options.durations[d]; } } }
        }
    };

    // ==========================================================================
    // Integração com AJAX (opcional)
    // ==========================================================================

    function setupFetchInterceptor() {
        var originalFetch = window.fetch;
        if (typeof originalFetch !== 'function') { return; }
        window.fetch = function() {
            var args = Array.prototype.slice.call(arguments);
            var url = args[0];
            var options = args[1] || {};
            if (options.showLoading !== false) {
                LoadingAPI.showFullscreen({ text: 'Carregando dados...' });
            }
            return originalFetch.apply(this, args)
                .then(function(response) {
                    if (options.showLoading !== false) { LoadingAPI.hideFullscreen(); }
                    return response;
                })
                .catch(function(error) {
                    if (options.showLoading !== false) { LoadingAPI.hideFullscreen(); }
                    throw error;
                });
        };
    }

    // ==========================================================================
    // Utilitários para Estados Vazios e Erro
    // ==========================================================================

    var StateManager = {
        showEmpty: function(element, options) {
            options = options || {};
            if (typeof element === 'string') { element = document.querySelector(element); }
            var config = {
                icon: 'bi-inbox',
                title: 'Nenhum dado encontrado',
                description: 'Não há informações para exibir no momento.',
                action: null
            };
            config = mergeOptions(config, options);
            var emptyState = createElement('div', ['empty-state']);
            var icon = createElement('div', ['empty-state-icon']);
            icon.innerHTML = '<i class="bi ' + config.icon + '"></i>';
            emptyState.appendChild(icon);
            var title = createElement('div', ['empty-state-title']);
            title.textContent = config.title;
            emptyState.appendChild(title);
            if (config.description) {
                var description = createElement('div', ['empty-state-description']);
                description.textContent = config.description;
                emptyState.appendChild(description);
            }
            if (config.action) {
                var action = createElement('button', ['btn', 'btn-primary']);
                action.textContent = config.action.text;
                action.addEventListener('click', config.action.handler);
                emptyState.appendChild(action);
            }
            element.innerHTML = '';
            element.appendChild(emptyState);
        },
        showError: function(element, options) {
            options = options || {};
            if (typeof element === 'string') { element = document.querySelector(element); }
            var config = {
                icon: 'bi-exclamation-triangle',
                title: 'Erro ao carregar dados',
                description: 'Ocorreu um erro inesperado. Tente novamente.',
                retry: null
            };
            config = mergeOptions(config, options);
            var errorState = createElement('div', ['error-state']);
            var icon = createElement('div', ['error-state-icon']);
            icon.innerHTML = '<i class="bi ' + config.icon + '"></i>';
            errorState.appendChild(icon);
            var title = createElement('div', ['error-state-title']);
            title.textContent = config.title;
            errorState.appendChild(title);
            if (config.description) {
                var description = createElement('div', ['error-state-description']);
                description.textContent = config.description;
                errorState.appendChild(description);
            }
            var actions = createElement('div', ['error-state-actions']);
            if (config.retry) {
                var retryBtn = createElement('button', ['btn', 'btn-primary']);
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
        // setupFetchInterceptor(); // opcional
        window.LoadingManager = LoadingAPI;
        window.StateManager = StateManager;
        window.loading = LoadingAPI;
        window.states = StateManager;
        try { console.log('Sistema de loading inicializado'); } catch(_){}
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();