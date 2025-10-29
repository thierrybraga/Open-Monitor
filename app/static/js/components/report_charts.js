/**
 * Sistema de Gráficos Interativos para Relatórios de Cybersegurança
 * Utiliza Chart.js para criar visualizações dinâmicas e interativas
 */

class ReportCharts {
    constructor() {
        this.charts = {};
        this.chartAvailable = (typeof window !== 'undefined' && typeof window.Chart !== 'undefined');
        this.defaultColors = {
            primary: '#007bff',
            secondary: '#6c757d',
            success: '#28a745',
            danger: '#dc3545',
            warning: '#ffc107',
            info: '#17a2b8',
            light: '#f8f9fa'
        };
        
        this.severityColors = {
            critical: '#dc3545',
            high: '#fd7e14',
            medium: '#ffc107',
            low: '#28a745',
            info: '#17a2b8'
        };
        
        this.init();
    }
    
    init() {
        // Configurações globais do Chart.js
        if (!this.chartAvailable) {
            console.warn('Chart.js não está disponível. Os gráficos do relatório serão desativados.');
            return;
        }
        Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
        Chart.defaults.font.size = 12;
        Chart.defaults.color = '#6c757d';
        Chart.defaults.plugins.legend.labels.usePointStyle = true;
        Chart.defaults.plugins.legend.labels.padding = 20;
        Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(0, 0, 0, 0.8)';
        Chart.defaults.plugins.tooltip.titleColor = '#ffffff';
        Chart.defaults.plugins.tooltip.bodyColor = '#ffffff';
        Chart.defaults.plugins.tooltip.cornerRadius = 8;
        Chart.defaults.plugins.tooltip.padding = 12;
    }
    
    /**
     * Cria gráfico de distribuição CVSS (histograma/pie)
     */
    createCVSSDistribution(canvasId, data, type = 'doughnut') {
        if (!this.chartAvailable) return null;
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;
        
        const chartData = {
            labels: ['Crítico (9.0-10.0)', 'Alto (7.0-8.9)', 'Médio (4.0-6.9)', 'Baixo (0.1-3.9)', 'Informativo (0.0)'],
            datasets: [{
                label: 'Vulnerabilidades por CVSS',
                data: [
                    data.critical || 0,
                    data.high || 0,
                    data.medium || 0,
                    data.low || 0,
                    data.info || 0
                ],
                backgroundColor: [
                    this.severityColors.critical,
                    this.severityColors.high,
                    this.severityColors.medium,
                    this.severityColors.low,
                    this.severityColors.info
                ],
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        };
        
        const config = {
            type: type,
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            generateLabels: function(chart) {
                                const data = chart.data;
                                if (data.labels.length && data.datasets.length) {
                                    return data.labels.map((label, i) => {
                                        const value = data.datasets[0].data[i];
                                        return {
                                            text: `${label}: ${value}`,
                                            fillStyle: data.datasets[0].backgroundColor[i],
                                            strokeStyle: data.datasets[0].borderColor,
                                            lineWidth: data.datasets[0].borderWidth,
                                            hidden: false,
                                            index: i
                                        };
                                    });
                                }
                                return [];
                            }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.parsed * 100) / total).toFixed(1);
                                return `${context.label}: ${context.parsed} (${percentage}%)`;
                            }
                        }
                    }
                },
                animation: {
                    animateRotate: true,
                    animateScale: true
                }
            }
        };
        
        this.charts[canvasId] = new Chart(ctx, config);
        return this.charts[canvasId];
    }
    
    /**
     * Cria gráfico de top N ativos por risco (bar chart)
     */
    createTopAssetsByRisk(canvasId, data, topN = 10) {
        if (!this.chartAvailable) return null;
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;
        
        // Ordenar e pegar apenas os top N
        const sortedAssets = data.sort((a, b) => b.risk_score - a.risk_score).slice(0, topN);
        
        const chartData = {
            labels: sortedAssets.map(asset => asset.name),
            datasets: [{
                label: 'Score de Risco',
                data: sortedAssets.map(asset => asset.risk_score),
                backgroundColor: sortedAssets.map(asset => {
                    if (asset.risk_score >= 9) return this.severityColors.critical;
                    if (asset.risk_score >= 7) return this.severityColors.high;
                    if (asset.risk_score >= 4) return this.severityColors.medium;
                    return this.severityColors.low;
                }),
                borderColor: sortedAssets.map(asset => {
                    if (asset.risk_score >= 9) return this.severityColors.critical;
                    if (asset.risk_score >= 7) return this.severityColors.high;
                    if (asset.risk_score >= 4) return this.severityColors.medium;
                    return this.severityColors.low;
                }),
                borderWidth: 1,
                borderRadius: 4,
                borderSkipped: false
            }]
        };
        
        const config = {
            type: 'bar',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y', // Barras horizontais
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            title: function(context) {
                                return `Ativo: ${context[0].label}`;
                            },
                            label: function(context) {
                                const asset = sortedAssets[context.dataIndex];
                                return [
                                    `Score de Risco: ${context.parsed.x}`,
                                    `Vulnerabilidades: ${asset.vulnerabilities_count || 0}`,
                                    `IP: ${asset.ip_address || 'N/A'}`
                                ];
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        max: 10,
                        title: {
                            display: true,
                            text: 'Score de Risco'
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Ativos'
                        },
                        grid: {
                            display: false
                        }
                    }
                },
                animation: {
                    duration: 1500,
                    easing: 'easeOutQuart'
                }
            }
        };
        
        this.charts[canvasId] = new Chart(ctx, config);
        return this.charts[canvasId];
    }
    
    /**
     * Cria gráfico de tendência de vulnerabilidades por data (line)
     */
    createVulnerabilityTrend(canvasId, data, days = 30) {
        if (!this.chartAvailable) return null;
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;
        
        const chartData = {
            labels: data.labels || this.generateDateLabels(days),
            datasets: [
                {
                    label: 'Novas Vulnerabilidades',
                    data: data.new_vulnerabilities || [],
                    borderColor: this.severityColors.danger,
                    backgroundColor: this.hexToRgba(this.severityColors.danger, 0.1),
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointHoverRadius: 6
                },
                {
                    label: 'Vulnerabilidades Corrigidas',
                    data: data.fixed_vulnerabilities || [],
                    borderColor: this.severityColors.success,
                    backgroundColor: this.hexToRgba(this.severityColors.success, 0.1),
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointHoverRadius: 6
                },
                {
                    label: 'Total Ativo',
                    data: data.total_active || [],
                    borderColor: this.defaultColors.primary,
                    backgroundColor: this.hexToRgba(this.defaultColors.primary, 0.1),
                    fill: false,
                    tension: 0.4,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    borderDash: [5, 5]
                }
            ]
        };
        
        const config = {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: {
                        position: 'top'
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            title: function(context) {
                                return `Data: ${context[0].label}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Período'
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Quantidade'
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        }
                    }
                },
                animation: {
                    duration: 2000,
                    easing: 'easeOutQuart'
                }
            }
        };
        
        this.charts[canvasId] = new Chart(ctx, config);
        return this.charts[canvasId];
    }
    
    /**
     * Cria matriz de risco (scatter plot)
     */
    createRiskMatrix(canvasId, data) {
        if (!this.chartAvailable) return null;
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;
        
        const scatterData = data.map(item => ({
            x: item.probability,
            y: item.impact,
            label: item.name,
            risk_level: item.risk_level
        }));
        
        const chartData = {
            datasets: [{
                label: 'Ativos',
                data: scatterData,
                backgroundColor: scatterData.map(item => {
                    switch(item.risk_level) {
                        case 'critical': return this.severityColors.critical;
                        case 'high': return this.severityColors.high;
                        case 'medium': return this.severityColors.medium;
                        default: return this.severityColors.low;
                    }
                }),
                borderColor: '#ffffff',
                borderWidth: 2,
                pointRadius: 8,
                pointHoverRadius: 12
            }]
        };
        
        const config = {
            type: 'scatter',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            title: function(context) {
                                const point = context[0].raw;
                                return point.label;
                            },
                            label: function(context) {
                                const point = context.raw;
                                return [
                                    `Probabilidade: ${point.x}`,
                                    `Impacto: ${point.y}`,
                                    `Nível de Risco: ${point.risk_level}`
                                ];
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        position: 'bottom',
                        min: 0,
                        max: 5,
                        title: {
                            display: true,
                            text: 'Probabilidade'
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        }
                    },
                    y: {
                        min: 0,
                        max: 5,
                        title: {
                            display: true,
                            text: 'Impacto'
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        }
                    }
                },
                animation: {
                    duration: 1500,
                    easing: 'easeOutBounce'
                }
            }
        };
        
        this.charts[canvasId] = new Chart(ctx, config);
        return this.charts[canvasId];
    }
    
    /**
     * Cria heatmap de ativos × tipos de vulnerabilidades
     */
    createAssetVulnerabilityHeatmap(canvasId, data) {
        if (!this.chartAvailable) return null;
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;
        
        // Transformar dados em formato de heatmap
        const heatmapData = [];
        data.assets.forEach((asset, assetIndex) => {
            data.vulnerability_types.forEach((vulnType, vulnIndex) => {
                const count = data.matrix[assetIndex][vulnIndex] || 0;
                heatmapData.push({
                    x: vulnIndex,
                    y: assetIndex,
                    v: count
                });
            });
        });
        
        const maxValue = Math.max(...heatmapData.map(d => d.v));
        
        const chartData = {
            datasets: [{
                label: 'Vulnerabilidades',
                data: heatmapData,
                backgroundColor: function(context) {
                    const value = context.parsed.v;
                    const alpha = value / maxValue;
                    return `rgba(220, 53, 69, ${alpha})`;
                },
                borderColor: '#ffffff',
                borderWidth: 1,
                width: ({chart}) => (chart.chartArea || {}).width / data.vulnerability_types.length,
                height: ({chart}) => (chart.chartArea || {}).height / data.assets.length
            }]
        };
        
        const config = {
            type: 'scatter',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            title: function(context) {
                                const point = context[0].parsed;
                                return `${data.assets[point.y]} × ${data.vulnerability_types[point.x]}`;
                            },
                            label: function(context) {
                                return `Vulnerabilidades: ${context.parsed.v}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        position: 'bottom',
                        min: -0.5,
                        max: data.vulnerability_types.length - 0.5,
                        ticks: {
                            stepSize: 1,
                            callback: function(value) {
                                return data.vulnerability_types[value] || '';
                            }
                        },
                        title: {
                            display: true,
                            text: 'Tipos de Vulnerabilidade'
                        }
                    },
                    y: {
                        min: -0.5,
                        max: data.assets.length - 0.5,
                        ticks: {
                            stepSize: 1,
                            callback: function(value) {
                                return data.assets[value] || '';
                            }
                        },
                        title: {
                            display: true,
                            text: 'Ativos'
                        }
                    }
                }
            }
        };
        
        this.charts[canvasId] = new Chart(ctx, config);
        return this.charts[canvasId];
    }
    
    /**
     * Cria timeline de KPI/KRI (area/line)
     */
    createKPITimeline(canvasId, data) {
        if (!this.chartAvailable) return null;
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;
        
        const datasets = data.kpis.map((kpi, index) => ({
            label: kpi.name,
            data: kpi.values,
            borderColor: this.getColorByIndex(index),
            backgroundColor: this.hexToRgba(this.getColorByIndex(index), 0.1),
            fill: kpi.fill || false,
            tension: 0.4,
            pointRadius: 3,
            pointHoverRadius: 6
        }));
        
        const chartData = {
            labels: data.labels,
            datasets: datasets
        };
        
        const config = {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: {
                        position: 'top'
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Período'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Valor'
                        }
                    }
                }
            }
        };
        
        this.charts[canvasId] = new Chart(ctx, config);
        return this.charts[canvasId];
    }
    
    /**
     * Cria gráfico radar de maturidade de segurança
     */
    createSecurityMaturityRadar(canvasId, data) {
        if (!this.chartAvailable) return null;
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;
        
        const chartData = {
            labels: data.domains,
            datasets: [
                {
                    label: 'Nível Atual',
                    data: data.current_levels,
                    borderColor: this.defaultColors.primary,
                    backgroundColor: this.hexToRgba(this.defaultColors.primary, 0.2),
                    pointBackgroundColor: this.defaultColors.primary,
                    pointBorderColor: '#ffffff',
                    pointHoverBackgroundColor: '#ffffff',
                    pointHoverBorderColor: this.defaultColors.primary
                },
                {
                    label: 'Meta',
                    data: data.target_levels,
                    borderColor: this.defaultColors.success,
                    backgroundColor: this.hexToRgba(this.defaultColors.success, 0.1),
                    pointBackgroundColor: this.defaultColors.success,
                    pointBorderColor: '#ffffff',
                    pointHoverBackgroundColor: '#ffffff',
                    pointHoverBorderColor: this.defaultColors.success,
                    borderDash: [5, 5]
                }
            ]
        };
        
        const config = {
            type: 'radar',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    r: {
                        beginAtZero: true,
                        min: 0,
                        max: 5,
                        ticks: {
                            stepSize: 1,
                            callback: function(value) {
                                const levels = ['', 'Inicial', 'Básico', 'Intermediário', 'Avançado', 'Otimizado'];
                                return levels[value] || value;
                            }
                        },
                        pointLabels: {
                            font: {
                                size: 11
                            }
                        }
                    }
                },
                animation: {
                    duration: 2000,
                    easing: 'easeOutQuart'
                }
            }
        };
        
        this.charts[canvasId] = new Chart(ctx, config);
        return this.charts[canvasId];
    }
    
    /**
     * Utilitários
     */
    generateDateLabels(days) {
        const labels = [];
        const today = new Date();
        for (let i = days - 1; i >= 0; i--) {
            const date = new Date(today);
            date.setDate(date.getDate() - i);
            labels.push(date.toLocaleDateString('pt-BR', { month: 'short', day: 'numeric' }));
        }
        return labels;
    }
    
    hexToRgba(hex, alpha) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }
    
    getColorByIndex(index) {
        const colors = [
            this.defaultColors.primary,
            this.defaultColors.success,
            this.defaultColors.warning,
            this.defaultColors.danger,
            this.defaultColors.info,
            this.defaultColors.secondary
        ];
        return colors[index % colors.length];
    }
    
    /**
     * Destrói um gráfico específico
     */
    destroyChart(canvasId) {
        if (this.charts[canvasId]) {
            this.charts[canvasId].destroy();
            delete this.charts[canvasId];
        }
    }
    
    /**
     * Destrói todos os gráficos
     */
    destroyAllCharts() {
        Object.keys(this.charts).forEach(canvasId => {
            this.destroyChart(canvasId);
        });
    }
    
    /**
     * Redimensiona todos os gráficos
     */
    resizeAllCharts() {
        Object.values(this.charts).forEach(chart => {
            chart.resize();
        });
    }
    
    /**
     * Exporta gráfico como imagem
     */
    exportChart(canvasId, filename = 'chart.png') {
        if (this.charts[canvasId]) {
            const url = this.charts[canvasId].toBase64Image();
            const link = document.createElement('a');
            link.download = filename;
            link.href = url;
            link.click();
        }
    }
}

// Instância global
window.ReportCharts = new ReportCharts();

// Event listeners
window.addEventListener('resize', () => {
    window.ReportCharts.resizeAllCharts();
});

window.addEventListener('beforeprint', () => {
    // Ajustar gráficos para impressão
    Object.values(window.ReportCharts.charts).forEach(chart => {
        chart.resize();
    });
});

// Exportar para uso em módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ReportCharts;
}