/**
 * Performance Optimizer
 * Implementa lazy loading, code splitting e outras otimizações de performance
 */

class PerformanceOptimizer {
    constructor() {
        this.lazyLoadedModules = new Map();
        this.intersectionObserver = null;
        this.init();
    }

    init() {
        this.setupLazyLoading();
        this.setupImageLazyLoading();
        this.setupModuleLazyLoading();
        this.optimizeEventListeners();
        this.setupResourceHints();
    }

    /**
     * Configura lazy loading para elementos visuais
     */
    setupLazyLoading() {
        // Configurar Intersection Observer para lazy loading
        const observerOptions = {
            root: null,
            rootMargin: '50px',
            threshold: 0.1
        };

        this.intersectionObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    this.loadElement(entry.target);
                    this.intersectionObserver.unobserve(entry.target);
                }
            });
        }, observerOptions);

        // Observar elementos com atributo data-lazy
        document.querySelectorAll('[data-lazy]').forEach(el => {
            this.intersectionObserver.observe(el);
        });
    }

    /**
     * Lazy loading específico para imagens
     */
    setupImageLazyLoading() {
        const images = document.querySelectorAll('img[data-src]');
        
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src;
                        img.classList.remove('lazy');
                        img.classList.add('loaded');
                        imageObserver.unobserve(img);
                    }
                });
            });

            images.forEach(img => {
                img.classList.add('lazy');
                imageObserver.observe(img);
            });
        } else {
            // Fallback para navegadores sem suporte
            images.forEach(img => {
                img.src = img.dataset.src;
            });
        }
    }

    /**
     * Lazy loading para módulos JavaScript
     */
    setupModuleLazyLoading() {
        // Configurar lazy loading para diferentes seções
        // Temporariamente desabilitado devido a problemas de compatibilidade ES6
        const lazyModules = {
            // 'analytics': () => import('./views/analytics_view.js'),
            // 'reports': () => import('./views/reports_view.js'),
            // 'search': () => import('./views/search_view.js'),
            // 'vulnerabilities': () => import('./vulnerabilities.js'),
            // 'chatbot': () => import('./views/chatbot_view.js')
        };

        // Observar elementos que requerem módulos específicos
        Object.keys(lazyModules).forEach(moduleName => {
            const elements = document.querySelectorAll(`[data-module="${moduleName}"]`);
            elements.forEach(el => {
                this.intersectionObserver.observe(el);
                el.dataset.lazy = moduleName;
            });
        });

        // Função para carregar módulo sob demanda
        window.loadModule = async (moduleName) => {
            if (this.lazyLoadedModules.has(moduleName)) {
                return this.lazyLoadedModules.get(moduleName);
            }

            if (lazyModules[moduleName]) {
                try {
                    const module = await lazyModules[moduleName]();
                    this.lazyLoadedModules.set(moduleName, module);
                    return module;
                } catch (error) {
                    console.error(`Erro ao carregar módulo ${moduleName}:`, error);
                }
            }
        };
    }

    /**
     * Carrega elemento lazy
     */
    async loadElement(element) {
        const lazyType = element.dataset.lazy;
        
        if (lazyType) {
            // Carregar módulo correspondente
            await window.loadModule(lazyType);
        }

        // Carregar conteúdo lazy
        if (element.dataset.src) {
            element.src = element.dataset.src;
        }

        // Executar callback personalizado
        if (element.dataset.callback) {
            const callback = window[element.dataset.callback];
            if (typeof callback === 'function') {
                callback(element);
            }
        }

        element.classList.add('loaded');
    }

    /**
     * Otimiza event listeners usando delegação
     */
    optimizeEventListeners() {
        // Delegação de eventos para botões
        document.addEventListener('click', this.debounce((e) => {
            const button = e.target.closest('button');
            if (button) {
                this.handleButtonClick(button, e);
            }
        }, 100));

        // Delegação para formulários
        document.addEventListener('submit', this.debounce((e) => {
            this.handleFormSubmit(e.target, e);
        }, 200));

        // Otimizar scroll events
        let scrollTimeout;
        document.addEventListener('scroll', () => {
            if (scrollTimeout) {
                cancelAnimationFrame(scrollTimeout);
            }
            scrollTimeout = requestAnimationFrame(() => {
                this.handleScroll();
            });
        }, { passive: true });
    }

    /**
     * Configura resource hints para melhor performance
     */
    setupResourceHints() {
        // Preload recursos críticos
        const criticalResources = [
            { href: '/static/css/variables.css', as: 'style' },
            { href: '/static/css/base.css', as: 'style' },
            { href: '/static/js/base.js', as: 'script' }
        ];

        criticalResources.forEach(resource => {
            const link = document.createElement('link');
            link.rel = 'preload';
            link.href = resource.href;
            link.as = resource.as;
            document.head.appendChild(link);
        });

        // Prefetch recursos que podem ser necessários
        const prefetchResources = [
            '/static/js/views/analytics_view.js',
            '/static/js/views/reports_view.js',
            '/static/css/vulnerabilities.css'
        ];

        // Prefetch após carregamento inicial
        window.addEventListener('load', () => {
            setTimeout(() => {
                prefetchResources.forEach(href => {
                    const link = document.createElement('link');
                    link.rel = 'prefetch';
                    link.href = href;
                    document.head.appendChild(link);
                });
            }, 2000);
        });
    }

    /**
     * Manipula cliques em botões de forma otimizada
     */
    handleButtonClick(button, event) {
        // Prevenir múltiplos cliques
        if (button.disabled || button.classList.contains('loading')) {
            event.preventDefault();
            return;
        }

        // Carregar módulo se necessário
        const moduleName = button.dataset.module;
        if (moduleName) {
            window.loadModule(moduleName);
        }
    }

    /**
     * Manipula submissão de formulários
     */
    handleFormSubmit(form, event) {
        // Validação básica antes de enviar
        const requiredFields = form.querySelectorAll('[required]');
        let isValid = true;

        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                isValid = false;
                field.classList.add('is-invalid');
            } else {
                field.classList.remove('is-invalid');
            }
        });

        if (!isValid) {
            event.preventDefault();
        }
    }

    /**
     * Manipula eventos de scroll otimizados
     */
    handleScroll() {
        // Implementar lógica de scroll otimizada
        const scrollTop = window.pageYOffset;
        
        // Lazy load elementos que entraram na viewport
        document.querySelectorAll('[data-lazy]:not(.loaded)').forEach(el => {
            const rect = el.getBoundingClientRect();
            if (rect.top < window.innerHeight + 100) {
                this.loadElement(el);
            }
        });
    }

    /**
     * Debounce function para otimizar eventos
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * Throttle function para eventos de alta frequência
     */
    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    /**
     * Monitora performance e métricas
     */
    monitorPerformance() {
        if ('PerformanceObserver' in window) {
            // Monitorar Largest Contentful Paint
            const lcpObserver = new PerformanceObserver((list) => {
                const entries = list.getEntries();
                const lastEntry = entries[entries.length - 1];
                console.log('LCP:', lastEntry.startTime);
            });
            lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] });

            // Monitorar First Input Delay
            const fidObserver = new PerformanceObserver((list) => {
                const entries = list.getEntries();
                entries.forEach(entry => {
                    console.log('FID:', entry.processingStart - entry.startTime);
                });
            });
            fidObserver.observe({ entryTypes: ['first-input'] });
        }
    }

    /**
     * Cleanup resources
     */
    destroy() {
        if (this.intersectionObserver) {
            this.intersectionObserver.disconnect();
        }
        this.lazyLoadedModules.clear();
    }
}

// Inicializar otimizador de performance
let performanceOptimizer;
document.addEventListener('DOMContentLoaded', () => {
    performanceOptimizer = new PerformanceOptimizer();
    performanceOptimizer.monitorPerformance();
});

// Cleanup ao sair da página
window.addEventListener('beforeunload', () => {
    if (performanceOptimizer) {
        performanceOptimizer.destroy();
    }
});

// Exportar para uso em outros módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PerformanceOptimizer;
} else if (typeof window !== 'undefined') {
    window.PerformanceOptimizer = PerformanceOptimizer;
    window.performanceOptimizer = performanceOptimizer;
}