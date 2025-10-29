/**
 * bundle-config.js - Configuração de Bundle JavaScript
 * Versão: 1.0 - Criado em Janeiro 2025
 * Configurações para carregamento e inicialização de módulos
 */

(function() {
    'use strict';
    
    console.log('🔥 === BUNDLE CONFIG EXECUTANDO ===');
    console.log('Bundle Config carregado');
    window.BUNDLE_CONFIG_LOADED = true;
    console.log('🔥 BUNDLE_CONFIG_LOADED definido como:', window.BUNDLE_CONFIG_LOADED);

    // ==========================================================================
    // Configurações do Bundle
    // ==========================================================================

    const BUNDLE_CONFIG = {
        // Configurações de carregamento
        loading: {
            timeout: 10000, // 10 segundos
            retries: 3,
            showProgress: true
        },
        
        // Módulos a serem carregados
        modules: {
            core: {
                files: ['lazy.min.js'],
                priority: 1,
                required: true
            }
        },
        
        // Configurações de performance
        performance: {
            preload: true,
            defer: true,
            async: true
        }
    };

    // ==========================================================================
    // Gerenciador de Bundle
    // ==========================================================================

    class BundleManager {
        constructor() {
            this.loadedModules = new Set();
            this.loadingModules = new Map();
            this.failedModules = new Set();
            this.initialized = false;
        }

        /**
         * Inicializa o gerenciador de bundle
         */
        init() {
            if (this.initialized) return;
            
            console.log('Inicializando Bundle Manager...');
            
            // Carregar módulos por prioridade
            this.loadModulesByPriority();
            
            this.initialized = true;
        }

        /**
         * Carrega módulos baseado na prioridade
         */
        async loadModulesByPriority() {
            const modules = Object.entries(BUNDLE_CONFIG.modules)
                .sort(([,a], [,b]) => a.priority - b.priority);

            for (const [name, config] of modules) {
                try {
                    await this.loadModule(name, config);
                } catch (error) {
                    console.error(`Erro ao carregar módulo ${name}:`, error);
                    this.failedModules.add(name);
                }
            }
        }

        /**
         * Carrega um módulo específico
         */
        async loadModule(name, config) {
            // Verificar se já foi carregado
            if (this.loadedModules.has(name)) {
                return Promise.resolve();
            }

            // Verificar se já está carregando
            if (this.loadingModules.has(name)) {
                return this.loadingModules.get(name);
            }

            // Verificar condição (se especificada)
            if (config.condition && !config.condition()) {
                console.log(`Módulo ${name} não carregado - condição não atendida`);
                return Promise.resolve();
            }

            // Criar promise de carregamento
            const loadPromise = this.loadModuleFiles(name, config);
            this.loadingModules.set(name, loadPromise);

            try {
                await loadPromise;
                this.loadedModules.add(name);
                this.loadingModules.delete(name);
                console.log(`Módulo ${name} carregado com sucesso`);
            } catch (error) {
                this.loadingModules.delete(name);
                throw error;
            }
        }

        /**
         * Carrega os arquivos de um módulo
         */
        async loadModuleFiles(name, config) {
            const promises = config.files.map(file => this.loadScript(file));
            return Promise.all(promises);
        }

        /**
         * Carrega um script individual
         */
        loadScript(src) {
            return new Promise((resolve, reject) => {
                // Verificar se o script já existe
                const existingScript = document.querySelector(`script[src*="${src}"]`);
                if (existingScript) {
                    resolve();
                    return;
                }

                const script = document.createElement('script');
                script.src = `/static/js/${src}`;
                script.async = BUNDLE_CONFIG.performance.async;
                script.defer = BUNDLE_CONFIG.performance.defer;

                script.onload = () => resolve();
                script.onerror = () => reject(new Error(`Falha ao carregar ${src}`));

                // Timeout
                const timeout = setTimeout(() => {
                    reject(new Error(`Timeout ao carregar ${src}`));
                }, BUNDLE_CONFIG.loading.timeout);

                script.onload = () => {
                    clearTimeout(timeout);
                    resolve();
                };

                document.head.appendChild(script);
            });
        }

        /**
         * Verifica se um módulo está carregado
         */
        isModuleLoaded(name) {
            return this.loadedModules.has(name);
        }

        /**
         * Obtém estatísticas de carregamento
         */
        getStats() {
            return {
                loaded: Array.from(this.loadedModules),
                loading: Array.from(this.loadingModules.keys()),
                failed: Array.from(this.failedModules),
                total: Object.keys(BUNDLE_CONFIG.modules).length
            };
        }
    }

    // ==========================================================================
    // Utilitários
    // ==========================================================================

    /**
     * Detecta recursos necessários na página
     */
    function detectPageResources() {
        console.log('🔍 === INICIANDO DETECÇÃO DE RECURSOS ===');
        
        const canvasElements = document.querySelectorAll('canvas[id*="Chart"]');
        const chartContainers = document.querySelectorAll('.chart-container');
        const dashboardSection = document.querySelector('.dashboard-charts-section');
        const allCanvas = document.querySelectorAll('canvas');
        
        console.log('📊 Canvas elements found:', canvasElements.length);
        console.log('📊 Canvas IDs:', Array.from(canvasElements).map(c => c.id));
        console.log('📊 Chart containers found:', chartContainers.length);
        console.log('📊 Dashboard section found:', !!dashboardSection);
        console.log('📊 DOM ready state:', document.readyState);
        console.log('📊 All canvas elements:', allCanvas.length);
        console.log('📊 All canvas IDs:', Array.from(allCanvas).map(c => c.id));
        
        const resources = {
            maps: document.querySelectorAll('.map-container, [data-map]').length > 0,
            calendar: document.querySelectorAll('.calendar, [data-calendar]').length > 0,
            charts: canvasElements.length > 0 || chartContainers.length > 0
        };

        console.log('📊 Recursos detectados na página:', resources);
        
        // Se há gráficos na página, carregar dashboard.js
        if (resources.charts) {
            console.log('📊 Gráficos detectados! Carregando dashboard.js...');
            loadDashboardScript();
        } else {
            console.log('📊 Nenhum gráfico detectado na página');
            console.log('📊 Tentando novamente em 1 segundo...');
            setTimeout(() => {
                detectPageResources();
            }, 1000);
        }
        
        return resources;
    }
    
    /**
     * Carrega o script do dashboard
     */
    function loadDashboardScript() {
        // Verificar se o script já foi carregado
        if (document.querySelector('script[src*="dashboard.js"]')) {
            console.log('Dashboard.js já está carregado');
            return;
        }
        
        const script = document.createElement('script');
        script.src = '/static/js/pages/dashboard.js';
        script.defer = true;
        script.onload = () => {
            console.log('Dashboard.js carregado com sucesso');
            // Aguardar um pouco para garantir que o script seja executado
            setTimeout(() => {
                if (window.DashboardCharts) {
                    console.log('Classe DashboardCharts disponível');
                } else {
                    console.error('Classe DashboardCharts não encontrada após carregamento');
                }
            }, 50);
        };
        script.onerror = () => {
            console.error('Erro ao carregar dashboard.js');
        };
        document.head.appendChild(script);
    }

    /**
     * Otimiza carregamento baseado na conexão
     */
    function optimizeForConnection() {
        if ('connection' in navigator) {
            const connection = navigator.connection;
            
            // Ajustar configurações baseado na velocidade da conexão
            if (connection.effectiveType === 'slow-2g' || connection.effectiveType === '2g') {
                BUNDLE_CONFIG.loading.timeout = 20000; // Aumentar timeout
                BUNDLE_CONFIG.performance.preload = false; // Desabilitar preload
            }
            
            console.log('Conexão detectada:', connection.effectiveType);
        }
    }

    // ==========================================================================
    // Inicialização
    // ==========================================================================

    // Criar instância global do gerenciador
    const bundleManager = new BundleManager();

    /**
     * Inicialização principal
     */
    function initBundleConfig() {
        console.log('🚀 === INICIALIZANDO BUNDLE CONFIG ===');
        console.log('🚀 Document ready state:', document.readyState);
        
        // Otimizar para conexão
        optimizeForConnection();
        
        // Aguardar o DOM estar completamente carregado
        if (document.readyState === 'loading') {
            console.log('🚀 DOM ainda carregando, aguardando DOMContentLoaded...');
            document.addEventListener('DOMContentLoaded', () => {
                console.log('📊 DOM carregado, iniciando detecção...');
                setTimeout(() => {
                    detectPageResources();
                }, 100);
            });
        } else {
            console.log('📊 DOM já carregado, iniciando detecção imediata...');
            setTimeout(() => {
                detectPageResources();
            }, 100);
        }
        
        // Inicializar gerenciador
        bundleManager.init();
        
        // Marcar como inicializado
        document.documentElement.setAttribute('data-bundle-initialized', 'true');
    }

    // ==========================================================================
    // API Pública
    // ==========================================================================

    // Expor API pública
    window.BundleConfig = {
        manager: bundleManager,
        config: BUNDLE_CONFIG,
        detectPageResources,
        optimizeForConnection
    };

    // Inicializar
    initBundleConfig();

})();