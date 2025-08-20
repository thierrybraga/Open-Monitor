// analytics.js - Analytics page functionality
// Handles data loading and table population for the analytics dashboard

class AnalyticsDashboard {
    constructor() {
        this.apiBase = '/api/analytics';
        this.charts = {};
        this.currentPage = 1;
        this.perPage = 10;
        this.init();
    }

    async init() {
        try {
            // Load overview data first
            await this.loadOverviewData();
            
            // Load table data
            await this.loadTopProducts();
            await this.loadTopCWEs();
            await this.loadLatestCVEs();
            
            // Load and create charts
            await this.loadCharts();
            
            // Setup event listeners
            this.setupEventListeners();
            
            console.log('Analytics dashboard initialized successfully');
        } catch (error) {
            console.error('Failed to initialize analytics dashboard:', error);
            this.showError('Failed to load analytics data');
        }
    }

    async loadOverviewData() {
        try {
            const response = await fetch(`${this.apiBase}/overview`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            this.updateOverviewMetrics(data);
        } catch (error) {
            console.error('Error loading overview data:', error);
            throw error;
        }
    }

    updateOverviewMetrics(data) {
        // Update metric cards with real data
        const metrics = {
            'total-cves': data.total_cves,
            'critical-severity-cves': data.critical_cves,
            'high-severity-cves': data.high_cves,
            'medium-severity-cves': data.medium_cves,
            'patched-cves': data.patched_cves,
            'unpatched-cves': data.unpatched_cves,
            'active-threats': data.active_threats || 0,
            'avg-cvss-score': data.avg_cvss_score || 0.0,
            'avg-exploit-score': data.avg_exploit_score || 0.0,
            'patch-coverage': `${data.patch_coverage}%`,
            'vendor-count': data.vendor_count,
            'product-count': data.product_count,
            'cwe-count': data.cwe_count
        };

        Object.entries(metrics).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
                console.log(`Updated ${id}: ${value}`);
            } else {
                console.warn(`Element with id '${id}' not found`);
            }
        });
    }

    async loadTopProducts() {
        try {
            const response = await fetch(`${this.apiBase}/details/top_products?per_page=10`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            this.populateProductTable(result.data);
        } catch (error) {
            console.error('Error loading top products:', error);
            this.showTableError('product-table-body', 'Failed to load products data');
        }
    }

    populateProductTable(products) {
        const tbody = document.getElementById('product-table-body');
        if (!tbody) return;

        if (!products || products.length === 0) {
            tbody.innerHTML = '<tr><td colspan="2" class="text-center text-muted">No products data available</td></tr>';
            return;
        }

        tbody.innerHTML = products.map(product => `
            <tr>
                <td>${this.escapeHtml(product.product || 'Unknown')}</td>
                <td><span class="badge bg-primary">${product.count}</span></td>
            </tr>
        `).join('');
    }

    async loadTopCWEs() {
        try {
            const response = await fetch(`${this.apiBase}/details/top_cwes?per_page=10`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            this.populateCWETable(result.data);
        } catch (error) {
            console.error('Error loading top CWEs:', error);
            this.showTableError('cwe-table-body', 'Failed to load CWEs data');
        }
    }

    populateCWETable(cwes) {
        const tbody = document.getElementById('cwe-table-body');
        if (!tbody) return;

        if (!cwes || cwes.length === 0) {
            tbody.innerHTML = '<tr><td colspan="2" class="text-center text-muted">No CWEs data available</td></tr>';
            return;
        }

        tbody.innerHTML = cwes.map(cwe => `
            <tr>
                <td><code>${this.escapeHtml(cwe.cwe || 'Unknown')}</code></td>
                <td><span class="badge bg-warning">${cwe.count}</span></td>
            </tr>
        `).join('');
    }

    async loadLatestCVEs(page = 1) {
        try {
            const response = await fetch(`${this.apiBase}/details/latest_cves?page=${page}&per_page=${this.perPage}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            this.populateCVETable(result.data);
            this.updatePagination(result.pagination);
        } catch (error) {
            console.error('Error loading latest CVEs:', error);
            this.showTableError('cve-table-body', 'Failed to load CVEs data');
        }
    }

    populateCVETable(cves) {
        const tbody = document.getElementById('cve-table-body');
        if (!tbody) return;

        if (!cves || cves.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No CVEs data available</td></tr>';
            return;
        }

        tbody.innerHTML = cves.map(cve => {
            const severityClass = this.getSeverityClass(cve.severity);
            const patchClass = cve.patch_status === 'Patched' ? 'success' : 'danger';
            const publishedDate = cve.published_date ? new Date(cve.published_date).toLocaleDateString() : 'N/A';
            
            return `
                <tr>
                    <td><code>${this.escapeHtml(cve.cve_id || 'N/A')}</code></td>
                    <td class="text-truncate" style="max-width: 250px;" title="${this.escapeHtml(cve.description || '')}">
                        ${this.escapeHtml(cve.description || 'No description available')}
                    </td>
                    <td>${publishedDate}</td>
                    <td><span class="badge bg-${severityClass}">${this.escapeHtml(cve.severity || 'Unknown')}</span></td>
                    <td>${cve.cvss_score || 'N/A'}</td>
                    <td><span class="badge bg-${patchClass}">${cve.patch_status}</span></td>
                </tr>
            `;
        }).join('');
    }

    updatePagination(pagination) {
        const paginationContainer = document.getElementById('pagination');
        if (!paginationContainer || !pagination) return;

        const { page, pages, total } = pagination;
        
        if (pages <= 1) {
            paginationContainer.innerHTML = '';
            return;
        }

        let paginationHTML = '';
        
        // Previous button
        if (page > 1) {
            paginationHTML += `<button class="btn btn-sm btn-outline-primary" onclick="analytics.loadLatestCVEs(${page - 1})">&laquo; Previous</button>`;
        }
        
        // Page numbers
        const startPage = Math.max(1, page - 2);
        const endPage = Math.min(pages, page + 2);
        
        for (let i = startPage; i <= endPage; i++) {
            const activeClass = i === page ? 'btn-primary' : 'btn-outline-primary';
            paginationHTML += `<button class="btn btn-sm ${activeClass}" onclick="analytics.loadLatestCVEs(${i})">${i}</button>`;
        }
        
        // Next button
        if (page < pages) {
            paginationHTML += `<button class="btn btn-sm btn-outline-primary" onclick="analytics.loadLatestCVEs(${page + 1})">Next &raquo;</button>`;
        }
        
        paginationContainer.innerHTML = paginationHTML;
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = document.getElementById('refresh-data');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.refreshAllData();
            });
        }
    }

    async refreshAllData() {
        try {
            this.showLoading(true);
            await this.loadOverviewData();
            await this.loadTopProducts();
            await this.loadTopCWEs();
            await this.loadLatestCVEs(this.currentPage);
            await this.loadCharts();
            this.showLoading(false);
        } catch (error) {
            console.error('Error refreshing data:', error);
            this.showError('Failed to refresh data');
            this.showLoading(false);
        }
    }

    showLoading(show) {
        const spinner = document.getElementById('loading-spinner');
        if (spinner) {
            spinner.classList.toggle('d-none', !show);
            spinner.classList.toggle('d-flex', show);
        }
    }

    showError(message) {
        const errorElement = document.getElementById('error-message');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.classList.remove('d-none');
            setTimeout(() => {
                errorElement.classList.add('d-none');
            }, 5000);
        }
    }

    showTableError(tableBodyId, message) {
        const tbody = document.getElementById(tableBodyId);
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="100%" class="text-center text-danger">${message}</td></tr>`;
        }
    }

    getSeverityClass(severity) {
        const severityMap = {
            'CRITICAL': 'danger',
            'HIGH': 'warning',
            'MEDIUM': 'info',
            'LOW': 'secondary'
        };
        return severityMap[severity?.toUpperCase()] || 'secondary';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }



    async loadCharts() {
        try {
            // Check if Chart.js is already loaded
            if (typeof Chart !== 'undefined') {
                console.log('Chart.js already loaded');
                await this.loadSeverityChart(Chart);
                await this.loadPatchStatusChart(Chart);
                await this.loadProductChart(Chart);
                await this.loadCWEChart(Chart);
                return;
            }

            // Load Chart.js dynamically via CDN
            await this.loadChartJS();
            
            // Wait a bit for Chart.js to be available
            await new Promise(resolve => setTimeout(resolve, 100));
            
            if (typeof Chart !== 'undefined') {
                console.log('Chart.js loaded successfully');
                // Load severity distribution chart
                await this.loadSeverityChart(Chart);
                
                // Load patch status chart
                await this.loadPatchStatusChart(Chart);
                
                // Load product pie chart
                await this.loadProductChart(Chart);
                
                // Load CWE pie chart
                await this.loadCWEChart(Chart);
            } else {
                throw new Error('Chart.js failed to load');
            }
            
        } catch (error) {
            console.error('Error loading charts:', error);
        }
    }

    loadChartJS() {
        return new Promise((resolve, reject) => {
            // Check if Chart.js script is already loaded
            if (document.querySelector('script[src*="chart.js"]')) {
                resolve();
                return;
            }

            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js';
            script.onload = () => {
                console.log('Chart.js script loaded');
                resolve();
            };
            script.onerror = () => {
                console.error('Failed to load Chart.js script');
                reject(new Error('Failed to load Chart.js'));
            };
            document.head.appendChild(script);
        });
    }

    async loadSeverityChart(Chart) {
        try {
            const response = await fetch(`${this.apiBase}/severity-distribution`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            this.createSeverityChart(Chart, result.data);
        } catch (error) {
            console.error('Error loading severity chart:', error);
        }
    }

    async loadPatchStatusChart(Chart) {
        try {
            const response = await fetch(`${this.apiBase}/patch-status`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            this.createPatchStatusChart(Chart, result.data);
        } catch (error) {
            console.error('Error loading patch status chart:', error);
        }
    }

    createSeverityChart(Chart, data) {
        const ctx = document.getElementById('severityChart');
        if (!ctx) {
            console.warn('Severity chart canvas not found');
            return;
        }

        // Destroy existing chart if it exists
        if (this.charts.severityChart) {
            this.charts.severityChart.destroy();
        }

        const colors = {
            'Critical': '#dc3545',
            'High': '#fd7e14', 
            'Medium': '#ffc107',
            'Low': '#198754',
            'N/A': '#6c757d',
            'None': '#e9ecef'
        };

        // Process API data format: {data: [values], labels: [labels]}
        const chartLabels = data.labels || [];
        const chartData = data.data || [];

        this.charts.severityChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: chartLabels,
                datasets: [{
                    data: chartData,
                    backgroundColor: chartLabels.map(label => colors[label] || '#6c757d'),
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                aspectRatio: 1,
                devicePixelRatio: window.devicePixelRatio || 1,
                animation: {
                    animateRotate: true,
                    animateScale: true,
                    duration: 800,
                    easing: 'easeOutQuart'
                },
                layout: {
                    padding: {
                        top: 10,
                        bottom: 10,
                        left: 10,
                        right: 10
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true,
                            font: {
                                size: 12,
                                family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                            },
                            generateLabels: function(chart) {
                                const data = chart.data;
                                if (data.labels.length && data.datasets.length) {
                                    return data.labels.map((label, i) => {
                                        const dataset = data.datasets[0];
                                        const value = dataset.data[i];
                                        const total = dataset.data.reduce((a, b) => a + b, 0);
                                        const percentage = ((value / total) * 100).toFixed(1);
                                        return {
                                            text: `${label}: ${value} (${percentage}%)`,
                                            fillStyle: dataset.backgroundColor[i],
                                            strokeStyle: dataset.backgroundColor[i],
                                            lineWidth: 0,
                                            pointStyle: 'circle',
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
                        backgroundColor: 'rgba(0, 0, 0, 0.9)',
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff',
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 1,
                        cornerRadius: 8,
                        displayColors: true,
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((value / total) * 100).toFixed(1);
                                return `${label}: ${value} vulnerabilidades (${percentage}%)`;
                            }
                        }
                    }
                },
                cutout: '65%'
            }
        });
    }

    createPatchStatusChart(Chart, data) {
        const ctx = document.getElementById('patchStatusChart');
        if (!ctx) {
            console.warn('Patch status chart canvas not found');
            return;
        }

        // Destroy existing chart if it exists
        if (this.charts.patchStatusChart) {
            this.charts.patchStatusChart.destroy();
        }

        const colors = {
            'Patched': '#198754',
            'Unpatched': '#dc3545'
        };

        // Process API data format: {data: [values], labels: [labels]}
        const chartLabels = data.labels || [];
        const chartData = data.data || [];

        this.charts.patchStatusChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: chartLabels,
                datasets: [{
                    data: chartData,
                    backgroundColor: chartLabels.map(label => colors[label] || '#6c757d'),
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                aspectRatio: 1,
                devicePixelRatio: window.devicePixelRatio || 1,
                animation: {
                    animateRotate: true,
                    animateScale: true,
                    duration: 800,
                    easing: 'easeOutQuart'
                },
                layout: {
                    padding: {
                        top: 10,
                        bottom: 10,
                        left: 10,
                        right: 10
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true,
                            font: {
                                size: 12,
                                family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                            },
                            generateLabels: function(chart) {
                                const data = chart.data;
                                if (data.labels.length && data.datasets.length) {
                                    return data.labels.map((label, i) => {
                                        const dataset = data.datasets[0];
                                        const value = dataset.data[i];
                                        const total = dataset.data.reduce((a, b) => a + b, 0);
                                        const percentage = ((value / total) * 100).toFixed(1);
                                        return {
                                            text: `${label}: ${value} (${percentage}%)`,
                                            fillStyle: dataset.backgroundColor[i],
                                            strokeStyle: dataset.backgroundColor[i],
                                            lineWidth: 0,
                                            pointStyle: 'circle',
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
                        backgroundColor: 'rgba(0, 0, 0, 0.9)',
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff',
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 1,
                        cornerRadius: 8,
                        displayColors: true,
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((value / total) * 100).toFixed(1);
                                return `${label}: ${value} vulnerabilidades (${percentage}%)`;
                            }
                        }
                    }
                },
                cutout: '65%'
            }
        });
    }

    async loadProductChart(Chart) {
        try {
            const response = await fetch('/api/analytics/details/top_products');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('Product chart data:', data);
            
            if (!data.data || !Array.isArray(data.data)) {
                console.warn('Invalid product data format');
                return;
            }
            
            // Take only top 5 products
            const top5Products = data.data.slice(0, 5);
            
            const labels = top5Products.map(item => item.product || 'Unknown');
            const values = top5Products.map(item => item.count || 0);
            
            const colors = [
                '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'
            ];
            
            const ctx = document.getElementById('productChart');
            if (!ctx) {
                console.warn('Product chart canvas not found');
                return;
            }
            
            new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: colors,
                        borderColor: colors.map(color => color + '80'),
                        borderWidth: 2
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
                                    size: 11
                                }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.parsed || 0;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = ((value / total) * 100).toFixed(1);
                                    return `${label}: ${value} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
            
        } catch (error) {
            console.error('Error loading product chart:', error);
        }
    }

    async loadCWEChart(Chart) {
        try {
            const response = await fetch('/api/analytics/details/top_cwes');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('CWE chart data:', data);
            
            if (!data.data || !Array.isArray(data.data)) {
                console.warn('Invalid CWE data format');
                return;
            }
            
            // Take only top 5 CWEs
            const top5CWEs = data.data.slice(0, 5);
            
            const labels = top5CWEs.map(item => `CWE-${item.cwe_id}` || 'Unknown');
            const values = top5CWEs.map(item => item.count || 0);
            
            const colors = [
                '#FF9F40', '#FF6384', '#4BC0C0', '#36A2EB', '#9966FF'
            ];
            
            const ctx = document.getElementById('cweChart');
            if (!ctx) {
                console.warn('CWE chart canvas not found');
                return;
            }
            
            new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: colors,
                        borderColor: colors.map(color => color + '80'),
                        borderWidth: 2
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
                                    size: 11
                                }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.parsed || 0;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = ((value / total) * 100).toFixed(1);
                                    return `${label}: ${value} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
            
        } catch (error) {
            console.error('Error loading CWE chart:', error);
        }
    }
}

// Initialize analytics dashboard when DOM is loaded
let analytics;
document.addEventListener('DOMContentLoaded', () => {
    analytics = new AnalyticsDashboard();
});

// Export for global access
window.analytics = analytics;