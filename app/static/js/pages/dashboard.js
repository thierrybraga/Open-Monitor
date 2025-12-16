// dashboard.js - Dashboard principal com gráficos interativos
// Handles data loading and chart creation for the main dashboard

class DashboardCharts {
    constructor() {
        this.apiBase = '/api/v1';
        this.charts = {};
        // Estado de preferências de vendors
        this.selectedVendorIds = [];
        this.init();
    }

    async init() {
        try {
            // Load Chart.js if not already loaded
            await this.loadChartJS();
            
            // Wait for Chart.js to be available
            await new Promise(resolve => setTimeout(resolve, 100));
            
            if (typeof Chart !== 'undefined') {
                console.log('Chart.js loaded successfully for dashboard');
                
                // Load dashboard charts
                await this.loadSeverityDistributionChart();
                await this.loadWeeklyTrendChart();
                await this.loadVulnerabilityTimelineChart();
                await this.loadTopCVSSChart();
                
                // Setup event listeners
                this.setupEventListeners();
                
                console.log('Dashboard charts initialized successfully');
            } else {
                throw new Error('Chart.js failed to load');
            }
            
        } catch (error) {
            console.error('Failed to initialize dashboard charts:', error);
            this.showError('Failed to load dashboard charts');
        }
    }

    // --- Helpers de vendor_ids (URL tem prioridade; fallback localStorage) ---
    isGlobalScope() {
        try {
            const params = new URLSearchParams(window.location.search || '');
            return (String(params.get('vendor_scope') || '').trim().toLowerCase() === 'all');
        } catch (_) {
            return false;
        }
    }
    getVendorIdsFromUrl() {
        try {
            // Se escopo global estiver ativo, ignorar vendor_ids
            if (this.isGlobalScope()) return [];
            const params = new URLSearchParams(window.location.search || '');
            const multi = params.getAll('vendor_ids');
            let ids = [];
            if (multi && multi.length) {
                multi.forEach(v => {
                    const parts = String(v).split(',');
                    parts.forEach(p => {
                        const n = parseInt(p.trim(), 10);
                        if (!isNaN(n)) ids.push(n);
                    });
                });
            }
            const single = params.get('vendor');
            if (single) {
                const parts2 = String(single).split(',');
                parts2.forEach(p => {
                    const n = parseInt(p.trim(), 10);
                    if (!isNaN(n)) ids.push(n);
                });
            }
            ids = Array.from(new Set(ids)).sort((a, b) => a - b);
            return ids;
        } catch (_) {
            return [];
        }
    }

    getVendorIdsFromLocalStorage() {
        try {
            const raw = localStorage.getItem('vendorSelection.selectedVendorIds');
            if (!raw) return [];
            const arr = JSON.parse(raw);
            if (!Array.isArray(arr)) return [];
            const ids = [];
            arr.forEach(v => {
                const n = parseInt(String(v).trim(), 10);
                if (!isNaN(n)) ids.push(n);
            });
            return Array.from(new Set(ids)).sort((a, b) => a - b);
        } catch (_) {
            return [];
        }
    }

    buildVendorParam(prefix = '?') {
        try {
            // Em escopo global, padronizar query para vendor_scope=all
            if (this.isGlobalScope()) {
                return `${prefix}vendor_scope=all`;
            }
            const urlVendorIds = this.getVendorIdsFromUrl();
            const effectiveIds = (urlVendorIds && urlVendorIds.length)
                ? urlVendorIds
                : (this.selectedVendorIds && this.selectedVendorIds.length
                    ? this.selectedVendorIds
                    : this.getVendorIdsFromLocalStorage());
            return (effectiveIds && effectiveIds.length)
                ? `${prefix}vendor_ids=${effectiveIds.join(',')}`
                : '';
        } catch (_) {
            return '';
        }
    }

    loadChartJS() {
        return new Promise((resolve, reject) => {
            // Check if Chart.js is already available
            if (typeof Chart !== 'undefined') {
                console.log('Chart.js already available for dashboard');
                resolve();
                return;
            }

            // Check if script is already being loaded
            const existingScript = document.querySelector('script[src*="chart.js"]');
            if (existingScript) {
                console.log('Chart.js script already exists, waiting for load');
                existingScript.addEventListener('load', () => {
                    console.log('Existing Chart.js script loaded for dashboard');
                    resolve();
                });
                existingScript.addEventListener('error', () => {
                    console.error('Existing Chart.js script failed to load');
                    reject(new Error('Failed to load existing Chart.js'));
                });
                return;
            }

            // Load Chart.js script
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js';
            script.onload = () => {
                console.log('Chart.js script loaded for dashboard');
                resolve();
            };
            script.onerror = () => {
                console.error('Failed to load Chart.js script');
                reject(new Error('Failed to load Chart.js'));
            };
            document.head.appendChild(script);
        });
    }

    async loadSeverityDistributionChart() {
        try {
            // Get data from the page or API
            const data = await this.getSeverityData();
            this.createSeverityChart(data);
        } catch (error) {
            console.error('Error loading severity distribution chart:', error);
        }
    }

    async loadWeeklyTrendChart() {
        try {
            const data = await this.getWeeklyTrendData();
            this.createWeeklyTrendChart(data);
        } catch (error) {
            console.error('Error loading weekly trend chart:', error);
        }
    }

    async loadVulnerabilityTimelineChart() {
        try {
            const data = await this.getTimelineData();
            this.createTimelineChart(data);
        } catch (error) {
            console.error('Error loading vulnerability timeline chart:', error);
        }
    }

    async loadTopCVSSChart() {
        try {
            const data = await this.getTopCVSSData();
            this.createTopCVSSChart(data);
        } catch (error) {
            console.error('Error loading top CVSS chart:', error);
        }
    }

    async getSeverityData() {
        try {
            console.log('🔍 Buscando dados de severidade da API...');
            const vendorParam = this.buildVendorParam('?');
            const response = await fetch(`/api/v1/dashboard/charts${vendorParam}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log('Dados recebidos da API:', data);
            console.log('Dados de severidade brutos:', data.severity_distribution);
            
            // Mapear labels da API para portugues
            const severityMap = {
                'CRITICAL': 'Criticas',
                'HIGH': 'Altas', 
                'MEDIUM': 'Medias',
                'LOW': 'Baixas',
                'N/A': 'N/A',
                'NONE': 'Nenhuma'
            };
            
            const mappedLabels = data.severity_distribution.labels.map(label => 
                severityMap[label] || label
            );
            
            // Filtrar apenas dados com valores maiores que zero
            const filteredData = [];
            const filteredLabels = [];
            
            for (let i = 0; i < mappedLabels.length; i++) {
                if (data.severity_distribution.data[i] > 0) {
                    filteredLabels.push(mappedLabels[i]);
                    filteredData.push(data.severity_distribution.data[i]);
                }
            }
            
            const result = {
                labels: filteredLabels,
                data: filteredData
            };
            
            console.log('Dados processados para o grafico:', result);
            console.log('Total de categorias com dados:', filteredLabels.length);
            return result;
        } catch (error) {
            console.error('Erro ao buscar dados de severidade:', error);
            // Fallback para dados da página
            const criticalElement = document.querySelector('.metric-card.critical .metric-card-value');
            const highElement = document.querySelector('.metric-card.high .metric-card-value');
            const mediumElement = document.querySelector('.metric-card.medium .metric-card-value');
            
            const critical = criticalElement ? parseInt(criticalElement.textContent) || 0 : 0;
            const high = highElement ? parseInt(highElement.textContent) || 0 : 0;
            const medium = mediumElement ? parseInt(mediumElement.textContent) || 0 : 0;
            
            return {
                labels: ['Criticas', 'Altas', 'Medias'],
                data: [critical, high, medium]
            };
        }
    }

    async getWeeklyTrendData() {
        try {
            const vendorParam = this.buildVendorParam('?');
            const response = await fetch(`/api/v1/dashboard/charts${vendorParam}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            return data.weekly_trend;
        } catch (error) {
            console.error('Erro ao buscar dados de tendência semanal:', error);
            // Fallback para dados da página
            const weeklyElements = document.querySelectorAll('.weekly-badge');
            const weeklyData = [];
            const labels = [];
            
            weeklyElements.forEach(element => {
                const text = element.textContent;
                const match = text.match(/\+(\d+)/);
                if (match) {
                    weeklyData.push(parseInt(match[1]));
                    if (element.classList.contains('critical')) labels.push('Criticas');
                    else if (element.classList.contains('high')) labels.push('Altas');
                    else if (element.classList.contains('medium')) labels.push('Medias');
                    else if (element.classList.contains('total')) labels.push('Total');
                }
            });
            
            return {
                labels: labels,
                data: weeklyData
            };
        }
    }

    async getTimelineData() {
        try {
            const vendorParam = this.buildVendorParam('?');
            const response = await fetch(`/api/v1/dashboard/charts${vendorParam}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            return data.vulnerability_timeline;
        } catch (error) {
            console.error('Erro ao buscar dados de timeline:', error);
            // Fallback para dados simulados
            return {
                labels: Array.from({length: 7}, (_, i) => {
                    const date = new Date();
                    date.setDate(date.getDate() - (6 - i));
                    return date.toLocaleDateString('pt-BR');
                }),
                data: Array.from({length: 7}, () => Math.floor(Math.random() * 10))
            };
        }
    }

    async getTopCVSSData() {
        try {
            const vendorParam = this.buildVendorParam('?');
            const response = await fetch(`/api/v1/dashboard/charts${vendorParam}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            return data.top_cvss;
        } catch (error) {
            console.error('Erro ao buscar dados de CVSS:', error);
            // Fallback para dados simulados
            return {
                labels: ['CVE-2024-0001', 'CVE-2024-0002', 'CVE-2024-0003', 'CVE-2024-0004', 'CVE-2024-0005'],
                data: [9.8, 9.5, 9.2, 8.9, 8.7]
            };
        }
    }

    createSeverityChart(data) {
        console.log('Iniciando criacao do grafico de severidade...');
        console.log('Dados recebidos para criacao:', data);
        
        const ctx = document.getElementById('severityDistributionChart');
        if (!ctx) {
            console.error('Canvas severityDistributionChart nao encontrado!');
            return;
        }
        console.log('Canvas encontrado:', ctx);

        // Destroy existing chart if it exists
        if (this.charts.severityChart) {
            console.log('Destruindo grafico existente...');
            this.charts.severityChart.destroy();
        }

        const colors = {
            'CRITICAL': '#dc3545',
            'HIGH': '#fd7e14', 
            'MEDIUM': '#ffc107',
            'LOW': '#198754',
            'N/A': '#6c757d',
            'NONE': '#6c757d',
            // Fallback para labels em portugues
            'Criticas': '#dc3545',
            'Altas': '#fd7e14',
            'Medias': '#ffc107',
            'Baixas': '#198754'
        };
        
        console.log('Mapeamento de cores:', colors);
        const backgroundColors = data.labels.map(label => colors[label] || '#6c757d');
        console.log('Cores aplicadas:', backgroundColors);

        try {
            console.log('Criando instancia do Chart.js...');
            this.charts.severityChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: data.labels,
                    datasets: [{
                        data: data.data,
                        backgroundColor: backgroundColors,
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            usePointStyle: true,
                            font: {
                                size: 12
                            }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed || 0;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : '0.0';
                                return `${label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
        console.log('Grafico de severidade criado com sucesso!');
        } catch (error) {
            console.error('Erro ao criar grafico de severidade:', error);
        }
    }

    createWeeklyTrendChart(data) {
        const ctx = document.getElementById('weeklyTrendChart');
        if (!ctx) {
            console.warn('Weekly trend chart canvas not found');
            return;
        }

        // Destroy existing chart if it exists
        if (this.charts.weeklyChart) {
            this.charts.weeklyChart.destroy();
        }

        this.charts.weeklyChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Novas Vulnerabilidades',
                    data: data.data,
                    backgroundColor: [
                        '#dc3545', // Critical
                        '#fd7e14', // High
                        '#ffc107', // Medium
                        '#0d6efd'  // Total
                    ],
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.label}: ${context.parsed.y} novas`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                }
            }
        });
    }

    createTimelineChart(data) {
        const ctx = document.getElementById('vulnerabilityTimelineChart');
        if (!ctx) {
            console.warn('Vulnerability timeline chart canvas not found');
            return;
        }

        // Destroy existing chart if it exists
        if (this.charts.timelineChart) {
            this.charts.timelineChart.destroy();
        }

        this.charts.timelineChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Vulnerabilidades Publicadas',
                    data: data.data,
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                }
            }
        });
    }

    createTopCVSSChart(data) {
        const ctx = document.getElementById('topCVSSChart');
        if (!ctx) {
            console.warn('Top CVSS chart canvas not found');
            return;
        }

        // Destroy existing chart if it exists
        if (this.charts.cvssChart) {
            this.charts.cvssChart.destroy();
        }

        this.charts.cvssChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'CVSS Score',
                    data: data.data,
                    backgroundColor: data.data.map(score => {
                        if (score >= 9.0) return '#dc3545'; // Critical
                        if (score >= 7.0) return '#fd7e14'; // High
                        if (score >= 4.0) return '#ffc107'; // Medium
                        return '#198754'; // Low
                    }),
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        max: 10
                    }
                }
            }
        });
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = document.getElementById('refresh-dashboard-charts');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.refreshAllCharts();
            });
        }

        // Auto-refresh every 5 minutes
        setInterval(() => {
            this.refreshAllCharts();
        }, 300000); // 5 minutes
    }

    async refreshAllCharts() {
        try {
            console.log('Refreshing dashboard charts...');
            await this.loadSeverityDistributionChart();
            await this.loadWeeklyTrendChart();
            await this.loadVulnerabilityTimelineChart();
            await this.loadTopCVSSChart();
            console.log('Dashboard charts refreshed successfully');
        } catch (error) {
            console.error('Error refreshing charts:', error);
        }
    }

    showError(message) {
        console.error(message);
        // You can implement a toast notification here
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger';
        errorDiv.textContent = message;
        document.body.appendChild(errorDiv);
        
        setTimeout(() => {
            errorDiv.remove();
        }, 5000);
    }

    // Cleanup method
    destroy() {
        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
        this.charts = {};
    }
}

// Export class for global access
window.DashboardCharts = DashboardCharts;

// Initialize dashboard charts when DOM is loaded
let dashboardCharts;
document.addEventListener('DOMContentLoaded', () => {
    dashboardCharts = new DashboardCharts();
});

// Export instance for global access
window.dashboardCharts = dashboardCharts;

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (dashboardCharts) {
        dashboardCharts.destroy();
    }
});