/**
 * Performance Metrics and Monitoring
 * Monitora métricas de performance e carregamento de JavaScript
 */

class PerformanceMetrics {
    constructor() {
        this.metrics = {
            loadTimes: {},
            bundleSizes: {},
            cacheHits: {},
            errors: [],
            userTiming: {},
            webVitals: {}
        };
        
        this.observers = [];
        this.init();
    }
    
    init() {
        this.setupPerformanceObserver();
        this.setupWebVitalsMonitoring();
        this.setupErrorTracking();
        this.setupResourceTiming();
    }
    
    // Configura observador de performance
    setupPerformanceObserver() {
        if ('PerformanceObserver' in window) {
            // Observa navegação
            const navObserver = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    this.recordNavigationTiming(entry);
                }
            });
            navObserver.observe({ entryTypes: ['navigation'] });
            this.observers.push(navObserver);
            
            // Observa recursos
            const resourceObserver = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (entry.name.includes('.js')) {
                        this.recordResourceTiming(entry);
                    }
                }
            });
            resourceObserver.observe({ entryTypes: ['resource'] });
            this.observers.push(resourceObserver);
            
            // Observa medidas customizadas
            const measureObserver = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    this.recordUserTiming(entry);
                }
            });
            measureObserver.observe({ entryTypes: ['measure'] });
            this.observers.push(measureObserver);
        }
    }
    
    // Monitora Web Vitals
    setupWebVitalsMonitoring() {
        // Largest Contentful Paint (LCP)
        if ('PerformanceObserver' in window) {
            const lcpObserver = new PerformanceObserver((list) => {
                const entries = list.getEntries();
                const lastEntry = entries[entries.length - 1];
                this.metrics.webVitals.lcp = lastEntry.startTime;
                this.reportWebVital('LCP', lastEntry.startTime);
            });
            lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] });
            this.observers.push(lcpObserver);
        }
        
        // First Input Delay (FID)
        if ('PerformanceObserver' in window) {
            const fidObserver = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    this.metrics.webVitals.fid = entry.processingStart - entry.startTime;
                    this.reportWebVital('FID', this.metrics.webVitals.fid);
                }
            });
            fidObserver.observe({ entryTypes: ['first-input'] });
            this.observers.push(fidObserver);
        }
        
        // Cumulative Layout Shift (CLS)
        if ('PerformanceObserver' in window) {
            let clsValue = 0;
            const clsObserver = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (!entry.hadRecentInput) {
                        clsValue += entry.value;
                    }
                }
                this.metrics.webVitals.cls = clsValue;
                this.reportWebVital('CLS', clsValue);
            });
            clsObserver.observe({ entryTypes: ['layout-shift'] });
            this.observers.push(clsObserver);
        }
    }
    
    // Configura rastreamento de erros
    setupErrorTracking() {
        window.addEventListener('error', (event) => {
            this.recordError({
                type: 'javascript',
                message: event.message,
                filename: event.filename,
                lineno: event.lineno,
                colno: event.colno,
                stack: event.error ? event.error.stack : null,
                timestamp: Date.now()
            });
        });
        
        window.addEventListener('unhandledrejection', (event) => {
            this.recordError({
                type: 'promise',
                message: event.reason.message || 'Unhandled Promise Rejection',
                stack: event.reason.stack,
                timestamp: Date.now()
            });
        });
    }
    
    // Configura timing de recursos
    setupResourceTiming() {
        // Monitora carregamento de scripts
        const scripts = document.querySelectorAll('script[src]');
        scripts.forEach(script => {
            script.addEventListener('load', () => {
                this.recordScriptLoad(script.src, 'success');
            });
            
            script.addEventListener('error', () => {
                this.recordScriptLoad(script.src, 'error');
            });
        });
    }
    
    // Registra timing de navegação
    recordNavigationTiming(entry) {
        this.metrics.loadTimes.navigation = {
            domContentLoaded: entry.domContentLoadedEventEnd - entry.domContentLoadedEventStart,
            loadComplete: entry.loadEventEnd - entry.loadEventStart,
            domInteractive: entry.domInteractive - entry.fetchStart,
            firstPaint: this.getFirstPaint(),
            firstContentfulPaint: this.getFirstContentfulPaint()
        };
    }
    
    // Registra timing de recursos
    recordResourceTiming(entry) {
        const resourceName = this.getResourceName(entry.name);
        this.metrics.loadTimes[resourceName] = {
            duration: entry.duration,
            transferSize: entry.transferSize,
            encodedBodySize: entry.encodedBodySize,
            decodedBodySize: entry.decodedBodySize,
            cached: entry.transferSize === 0 && entry.decodedBodySize > 0
        };
        
        // Registra hit de cache
        if (entry.transferSize === 0 && entry.decodedBodySize > 0) {
            this.recordCacheHit(resourceName);
        }
    }
    
    // Registra timing customizado
    recordUserTiming(entry) {
        this.metrics.userTiming[entry.name] = {
            duration: entry.duration,
            startTime: entry.startTime,
            timestamp: Date.now()
        };
    }
    
    // Registra erro
    recordError(error) {
        this.metrics.errors.push(error);
        
        // Limita o número de erros armazenados
        if (this.metrics.errors.length > 100) {
            this.metrics.errors = this.metrics.errors.slice(-50);
        }
    }
    
    // Registra carregamento de script
    recordScriptLoad(src, status) {
        const scriptName = this.getResourceName(src);
        this.metrics.loadTimes[scriptName] = {
            ...this.metrics.loadTimes[scriptName],
            status,
            timestamp: Date.now()
        };
    }
    
    // Registra hit de cache
    recordCacheHit(resourceName) {
        if (!this.metrics.cacheHits[resourceName]) {
            this.metrics.cacheHits[resourceName] = 0;
        }
        this.metrics.cacheHits[resourceName]++;
    }
    
    // Obtém First Paint
    getFirstPaint() {
        const paintEntries = performance.getEntriesByType('paint');
        const firstPaint = paintEntries.find(entry => entry.name === 'first-paint');
        return firstPaint ? firstPaint.startTime : null;
    }
    
    // Obtém First Contentful Paint
    getFirstContentfulPaint() {
        const paintEntries = performance.getEntriesByType('paint');
        const fcp = paintEntries.find(entry => entry.name === 'first-contentful-paint');
        return fcp ? fcp.startTime : null;
    }
    
    // Extrai nome do recurso
    getResourceName(url) {
        try {
            const urlObj = new URL(url);
            return urlObj.pathname.split('/').pop() || 'unknown';
        } catch {
            return url.split('/').pop() || 'unknown';
        }
    }
    
    // Reporta Web Vital
    reportWebVital(name, value) {
        // Determina se o valor está dentro dos limites recomendados
        const thresholds = {
            LCP: { good: 2500, poor: 4000 },
            FID: { good: 100, poor: 300 },
            CLS: { good: 0.1, poor: 0.25 }
        };
        
        const threshold = thresholds[name];
        let rating = 'good';
        
        if (threshold) {
            if (value > threshold.poor) {
                rating = 'poor';
            } else if (value > threshold.good) {
                rating = 'needs-improvement';
            }
        }
        
        console.log(`${name}: ${value}ms (${rating})`);
        
        // Dispara evento customizado
        document.dispatchEvent(new CustomEvent('webvital', {
            detail: { name, value, rating }
        }));
    }
    
    // Marca início de operação
    markStart(name) {
        performance.mark(`${name}-start`);
    }
    
    // Marca fim de operação e calcula duração
    markEnd(name) {
        performance.mark(`${name}-end`);
        performance.measure(name, `${name}-start`, `${name}-end`);
    }
    
    // Obtém métricas atuais
    getMetrics() {
        return {
            ...this.metrics,
            timestamp: Date.now(),
            userAgent: navigator.userAgent,
            connection: this.getConnectionInfo()
        };
    }
    
    // Obtém informações de conexão
    getConnectionInfo() {
        if ('connection' in navigator) {
            const conn = navigator.connection;
            return {
                effectiveType: conn.effectiveType,
                downlink: conn.downlink,
                rtt: conn.rtt,
                saveData: conn.saveData
            };
        }
        return null;
    }
    
    // Gera relatório de performance
    generateReport() {
        const metrics = this.getMetrics();
        const report = {
            summary: {
                totalErrors: metrics.errors.length,
                averageLoadTime: this.calculateAverageLoadTime(),
                cacheHitRate: this.calculateCacheHitRate(),
                webVitalsScore: this.calculateWebVitalsScore()
            },
            details: metrics,
            recommendations: this.generateRecommendations()
        };
        
        return report;
    }
    
    // Calcula tempo médio de carregamento
    calculateAverageLoadTime() {
        const loadTimes = Object.values(this.metrics.loadTimes)
            .filter(timing => typeof timing.duration === 'number')
            .map(timing => timing.duration);
        
        if (loadTimes.length === 0) return 0;
        
        return loadTimes.reduce((sum, time) => sum + time, 0) / loadTimes.length;
    }
    
    // Calcula taxa de hit de cache
    calculateCacheHitRate() {
        const totalRequests = Object.keys(this.metrics.loadTimes).length;
        const cacheHits = Object.values(this.metrics.cacheHits)
            .reduce((sum, hits) => sum + hits, 0);
        
        return totalRequests > 0 ? (cacheHits / totalRequests) * 100 : 0;
    }
    
    // Calcula pontuação dos Web Vitals
    calculateWebVitalsScore() {
        const vitals = this.metrics.webVitals;
        let score = 0;
        let count = 0;
        
        // LCP Score
        if (vitals.lcp !== undefined) {
            score += vitals.lcp <= 2500 ? 100 : vitals.lcp <= 4000 ? 50 : 0;
            count++;
        }
        
        // FID Score
        if (vitals.fid !== undefined) {
            score += vitals.fid <= 100 ? 100 : vitals.fid <= 300 ? 50 : 0;
            count++;
        }
        
        // CLS Score
        if (vitals.cls !== undefined) {
            score += vitals.cls <= 0.1 ? 100 : vitals.cls <= 0.25 ? 50 : 0;
            count++;
        }
        
        return count > 0 ? score / count : 0;
    }
    
    // Gera recomendações
    generateRecommendations() {
        const recommendations = [];
        const metrics = this.metrics;
        
        // Verifica Web Vitals
        if (metrics.webVitals.lcp > 4000) {
            recommendations.push('Otimizar Largest Contentful Paint (LCP) - considere lazy loading de imagens e otimização de recursos críticos');
        }
        
        if (metrics.webVitals.fid > 300) {
            recommendations.push('Reduzir First Input Delay (FID) - considere code splitting e otimização de JavaScript');
        }
        
        if (metrics.webVitals.cls > 0.25) {
            recommendations.push('Melhorar Cumulative Layout Shift (CLS) - defina dimensões para imagens e evite inserção dinâmica de conteúdo');
        }
        
        // Verifica erros
        if (metrics.errors.length > 10) {
            recommendations.push('Alto número de erros JavaScript detectados - revisar e corrigir erros');
        }
        
        // Verifica cache
        const cacheHitRate = this.calculateCacheHitRate();
        if (cacheHitRate < 50) {
            recommendations.push('Taxa de cache baixa - implementar estratégias de cache mais eficientes');
        }
        
        return recommendations;
    }
    
    // Limpa observadores
    cleanup() {
        this.observers.forEach(observer => {
            observer.disconnect();
        });
        this.observers = [];
    }
}

// Inicializa métricas de performance
const performanceMetrics = new PerformanceMetrics();

// Exporta para uso global
window.PerformanceMetrics = performanceMetrics;

// Cleanup ao descarregar página
window.addEventListener('beforeunload', () => {
    performanceMetrics.cleanup();
});

// Export for global access
if (typeof window !== 'undefined') {
    window.performanceMetrics = performanceMetrics;
}