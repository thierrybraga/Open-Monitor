/**
 * Bundle Configuration
 * Configuração para bundling e minificação de JavaScript
 */

const BundleConfig = {
    // Configuração de módulos críticos que devem ser carregados imediatamente
    critical: [
        'base.js',
        'theme.js',
        'notifications.js'
    ],

    // Configuração de módulos que podem ser carregados sob demanda
    lazy: {
        'dashboard': {
            modules: ['controllers/index_controller.js'],
            trigger: '[data-page="dashboard"]'
        },
        'vulnerabilities': {
            modules: [
                'vulnerabilities.js',
                'views/vulnerability_view.js'
            ],
            trigger: '[data-page="vulnerabilities"]'
        },
        'analytics': {
            modules: [
                'analytics.js',
                'controllers/analytics_controller.js',
                'views/analytics_view.js',
                'models/analytics_model.js'
            ],
            trigger: '[data-page="analytics"]'
        },
        'reports': {
            modules: [
                'controllers/reports_controller.js',
                'views/reports_view.js',
                'models/reports_model.js'
            ],
            trigger: '[data-page="reports"]'
        },
        'search': {
            modules: [
                'controllers/search_controller.js',
                'views/search_view.js'
            ],
            trigger: '[data-page="search"]'
        },
        'chatbot': {
            modules: [
                'controllers/chatbot_controller.js',
                'views/chatbot_view.js',
                'models/chatbot_model.js'
            ],
            trigger: '[data-page="chatbot"]'
        },
        'assets': {
            modules: [
                'controllers/assets_controller.js',
                'views/assets_view.js'
            ],
            trigger: '[data-page="assets"]'
        },
        'account': {
            modules: [
                'account.js',
                'controllers/account_controller.js',
                'views/account_view.js',
                'models/account_model.js'
            ],
            trigger: '[data-page="account"]'
        }
    },

    // Configuração de dependências externas
    external: {
        'bootstrap': {
            url: 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js',
            fallback: '/static/js/vendor/bootstrap.bundle.min.js',
            integrity: 'sha384-C6RzsynM9kWDrMNeT87bh95OGNyZPhcTNXj1NW7RuBCsyN/o0jlpcV8Qyq46cDfL'
        }
    },

    // Configuração de otimização
    optimization: {
        minify: true,
        sourceMaps: window.location.hostname === 'localhost',
        treeshaking: true,
        codesplitting: true,
        compression: {
            gzip: true,
            brotli: true
        }
    },

    // Configuração de cache
    cache: {
        strategy: 'content-hash',
        maxAge: 31536000, // 1 ano
        immutable: true
    }
};

/**
 * Dynamic Module Loader
 * Carrega módulos dinamicamente baseado na configuração
 */
class DynamicModuleLoader {
    constructor(config) {
        this.config = config;
        this.loadedModules = new Set();
        this.loadingPromises = new Map();
        this.init();
    }

    init() {
        this.setupPageDetection();
        this.preloadCriticalModules();
        this.setupLazyLoading();
    }

    /**
     * Detecta a página atual e carrega módulos necessários
     */
    setupPageDetection() {
        const pageElement = document.querySelector('[data-page]');
        if (pageElement) {
            const pageName = pageElement.dataset.page;
            this.loadPageModules(pageName);
        }
    }

    /**
     * Pré-carrega módulos críticos
     */
    async preloadCriticalModules() {
        const promises = this.config.critical.map(module => 
            this.loadModule(module, true)
        );
        
        try {
            await Promise.all(promises);
            console.log('Módulos críticos carregados');
        } catch (error) {
            console.error('Erro ao carregar módulos críticos:', error);
        }
    }

    /**
     * Configura lazy loading baseado em triggers
     */
    setupLazyLoading() {
        Object.entries(this.config.lazy).forEach(([name, config]) => {
            const triggers = document.querySelectorAll(config.trigger);
            
            if (triggers.length > 0) {
                // Se o trigger já está presente, carregar imediatamente
                this.loadPageModules(name);
            } else {
                // Configurar observer para carregar quando o trigger aparecer
                this.observeTrigger(config.trigger, () => {
                    this.loadPageModules(name);
                });
            }
        });
    }

    /**
     * Observa triggers para lazy loading
     */
    observeTrigger(selector, callback) {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === 1) { // Element node
                        if (node.matches && node.matches(selector)) {
                            callback();
                            observer.disconnect();
                        } else if (node.querySelector) {
                            const found = node.querySelector(selector);
                            if (found) {
                                callback();
                                observer.disconnect();
                            }
                        }
                    }
                });
            });
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    /**
     * Carrega módulos de uma página específica
     */
    async loadPageModules(pageName) {
        const pageConfig = this.config.lazy[pageName];
        if (!pageConfig) return;

        const promises = pageConfig.modules.map(module => 
            this.loadModule(module)
        );

        try {
            await Promise.all(promises);
            console.log(`Módulos da página ${pageName} carregados`);
        } catch (error) {
            console.error(`Erro ao carregar módulos da página ${pageName}:`, error);
        }
    }

    /**
     * Carrega um módulo individual
     */
    async loadModule(modulePath, isCritical = false) {
        if (this.loadedModules.has(modulePath)) {
            return;
        }

        if (this.loadingPromises.has(modulePath)) {
            return this.loadingPromises.get(modulePath);
        }

        const loadPromise = this.doLoadModule(modulePath, isCritical);
        this.loadingPromises.set(modulePath, loadPromise);

        try {
            await loadPromise;
            this.loadedModules.add(modulePath);
            this.loadingPromises.delete(modulePath);
        } catch (error) {
            this.loadingPromises.delete(modulePath);
            throw error;
        }
    }

    /**
     * Executa o carregamento do módulo
     */
    async doLoadModule(modulePath, isCritical) {
        const fullPath = `/static/js/${modulePath}`;
        
        try {
            // Tentar carregar como ES module primeiro
            if (this.supportsESModules()) {
                await import(fullPath);
            } else {
                // Fallback para script tag
                await this.loadScript(fullPath);
            }
        } catch (error) {
            if (isCritical) {
                throw new Error(`Falha ao carregar módulo crítico: ${modulePath}`);
            } else {
                console.warn(`Falha ao carregar módulo: ${modulePath}`, error);
            }
        }
    }

    /**
     * Verifica suporte a ES modules
     */
    supportsESModules() {
        const script = document.createElement('script');
        return 'noModule' in script;
    }

    /**
     * Carrega script usando script tag
     */
    loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    /**
     * Pré-carrega módulo sem executar
     */
    preloadModule(modulePath) {
        const link = document.createElement('link');
        link.rel = 'modulepreload';
        link.href = `/static/js/${modulePath}`;
        document.head.appendChild(link);
    }

    /**
     * Remove módulo do cache
     */
    unloadModule(modulePath) {
        this.loadedModules.delete(modulePath);
        this.loadingPromises.delete(modulePath);
    }

    /**
     * Obtém estatísticas de carregamento
     */
    getStats() {
        return {
            loaded: Array.from(this.loadedModules),
            loading: Array.from(this.loadingPromises.keys()),
            total: this.config.critical.length + 
                   Object.values(this.config.lazy).reduce((acc, config) => 
                       acc + config.modules.length, 0
                   )
        };
    }
}

// Inicializar carregador de módulos
let moduleLoader;
document.addEventListener('DOMContentLoaded', () => {
    moduleLoader = new DynamicModuleLoader(BundleConfig);
});

// Exportar configuração e carregador
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { BundleConfig, DynamicModuleLoader };
} else if (typeof window !== 'undefined') {
    window.BundleConfig = BundleConfig;
    window.DynamicModuleLoader = DynamicModuleLoader;
    window.moduleLoader = moduleLoader;
}