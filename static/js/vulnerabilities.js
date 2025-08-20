/**
 * Vulnerabilities Page JavaScript
 * Handles table interactions, sorting, pagination, and action buttons
 */

(function() {
    'use strict';

    // DOM Elements
    let currentCveId = null;
    let sortDirection = {};
    let currentPage = 1;
    let currentFilters = {};
    let debounceTimers = {};
    let isInitialized = false;
    let eventListeners = [];

    // Debounce utility
    function debounce(func, wait, key = 'default') {
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(debounceTimers[key]);
                func(...args);
            };
            clearTimeout(debounceTimers[key]);
            debounceTimers[key] = setTimeout(later, wait);
        };
    }

    // Event listener tracker for cleanup
    function addEventListenerTracked(element, event, handler, options) {
        element.addEventListener(event, handler, options);
        eventListeners.push({ element, event, handler, options });
    }

    // Initialize when DOM is loaded
    document.addEventListener('DOMContentLoaded', function() {
        if (!isInitialized) {
            initializeVulnerabilitiesPage();
        }
    });

    function initializeVulnerabilitiesPage() {
        initializeTableSorting();
        initializeActionButtons();
        initializeModals();
        initializePagination();
        initializeFilters();
        
        isInitialized = true;
        console.log('Vulnerabilities page initialized successfully');
    }

    // Table Sorting with debounce
    function initializeTableSorting() {
        const sortableHeaders = document.querySelectorAll('.sortable');
        
        sortableHeaders.forEach(header => {
            const debouncedSort = debounce((sortField, headerElement) => {
                handleSort(sortField, headerElement);
            }, 200, 'sort');
            
            const handler = function() {
                const sortField = this.dataset.sort;
                debouncedSort(sortField, this);
            };
            
            addEventListenerTracked(header, 'click', handler);
        });
    }

    function handleSort(field, headerElement) {
        // Toggle sort direction
        if (!sortDirection[field]) {
            sortDirection[field] = 'asc';
        } else {
            sortDirection[field] = sortDirection[field] === 'asc' ? 'desc' : 'asc';
        }

        // Update visual indicators
        updateSortIndicators(headerElement, sortDirection[field]);
        
        // Apply sorting
        sortTable(field, sortDirection[field]);
    }

    function updateSortIndicators(activeHeader, direction) {
        // Reset all sort icons
        document.querySelectorAll('.sort-icon').forEach(icon => {
            icon.className = 'bi bi-chevron-expand sort-icon';
        });
        
        // Update active header icon
        const icon = activeHeader.querySelector('.sort-icon');
        if (direction === 'asc') {
            icon.className = 'bi bi-chevron-up sort-icon';
        } else {
            icon.className = 'bi bi-chevron-down sort-icon';
        }
    }

    function sortTable(field, direction) {
        const table = document.getElementById('vulnerabilities-table');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        
        rows.sort((a, b) => {
            let aValue, bValue;
            
            switch(field) {
                case 'cve_id':
                    aValue = a.querySelector('.cve-badge').textContent.trim();
                    bValue = b.querySelector('.cve-badge').textContent.trim();
                    break;
                case 'severity':
                    const severityOrder = { 'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1 };
                    aValue = severityOrder[a.querySelector('.severity-badge').textContent.trim()] || 0;
                    bValue = severityOrder[b.querySelector('.severity-badge').textContent.trim()] || 0;
                    break;
                case 'cvss_score':
                    aValue = parseFloat(a.querySelector('.cvss-score').textContent.trim()) || 0;
                    bValue = parseFloat(b.querySelector('.cvss-score').textContent.trim()) || 0;
                    break;
                case 'published_date':
                    aValue = new Date(a.querySelector('.date-text').textContent.trim().split('/').reverse().join('-'));
                    bValue = new Date(b.querySelector('.date-text').textContent.trim().split('/').reverse().join('-'));
                    break;
                default:
                    return 0;
            }
            
            if (direction === 'asc') {
                return aValue > bValue ? 1 : aValue < bValue ? -1 : 0;
            } else {
                return aValue < bValue ? 1 : aValue > bValue ? -1 : 0;
            }
        });
        
        // Clear tbody and append sorted rows
        tbody.innerHTML = '';
        rows.forEach(row => tbody.appendChild(row));
    }

    // Action Buttons
    function initializeActionButtons() {
        // Mitigate buttons
        document.addEventListener('click', function(e) {
            if (e.target.closest('.mitigate-btn')) {
                const btn = e.target.closest('.mitigate-btn');
                currentCveId = btn.dataset.cveId;
                showMitigateModal();
            }
        });

        // Ticket buttons
        document.addEventListener('click', function(e) {
            if (e.target.closest('.ticket-btn')) {
                const btn = e.target.closest('.ticket-btn');
                currentCveId = btn.dataset.cveId;
                showTicketModal();
            }
        });
    }

    function showMitigateModal() {
        const modal = new bootstrap.Modal(document.getElementById('mitigateModal'));
        
        // Update modal title with CVE ID
        const modalTitle = document.querySelector('#mitigateModalLabel');
        modalTitle.innerHTML = `<i class="bi bi-shield-check"></i> Mitigar Vulnerabilidade ${currentCveId}`;
        
        modal.show();
    }

    function showTicketModal() {
        const modal = new bootstrap.Modal(document.getElementById('ticketModal'));
        
        // Update modal title and pre-fill ticket title
        const modalTitle = document.querySelector('#ticketModalLabel');
        modalTitle.innerHTML = `<i class="bi bi-ticket-perforated"></i> Abrir Ticket para ${currentCveId}`;
        
        const ticketTitle = document.getElementById('ticketTitle');
        ticketTitle.value = `Vulnerabilidade ${currentCveId} - Ação Necessária`;
        
        modal.show();
    }

    // Modals
    function initializeModals() {
        // Mitigate confirmation
        const confirmMitigateBtn = document.getElementById('confirmMitigate');
        if (confirmMitigateBtn) {
            confirmMitigateBtn.addEventListener('click', handleMitigate);
        }

        // Ticket confirmation
        const confirmTicketBtn = document.getElementById('confirmTicket');
        if (confirmTicketBtn) {
            confirmTicketBtn.addEventListener('click', handleCreateTicket);
        }
    }

    function handleMitigate() {
        const notes = document.getElementById('mitigationNotes').value;
        const status = document.getElementById('mitigationStatus').value;
        
        if (!notes.trim()) {
            showAlert('Por favor, adicione notas de mitigação.', 'warning');
            return;
        }
        
        showLoading(true);
        
        // Send mitigation request
        fetch(`/api/vulnerabilities/${currentCveId}/mitigate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                notes: notes,
                status: status
            })
        })
        .then(response => response.json())
        .then(data => {
            showLoading(false);
            
            if (data.success) {
                showAlert('Vulnerabilidade mitigada com sucesso!', 'success');
                
                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('mitigateModal'));
                modal.hide();
                
                // Refresh page or update row
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            } else {
                showAlert(data.message || 'Erro ao mitigar vulnerabilidade.', 'danger');
            }
        })
        .catch(error => {
            showLoading(false);
            console.error('Error:', error);
            showAlert('Erro de conexão. Tente novamente.', 'danger');
        });
    }

    function handleCreateTicket() {
        const title = document.getElementById('ticketTitle').value;
        const description = document.getElementById('ticketDescription').value;
        const priority = document.getElementById('ticketPriority').value;
        
        if (!title.trim() || !description.trim()) {
            showAlert('Por favor, preencha título e descrição do ticket.', 'warning');
            return;
        }
        
        showLoading(true);
        
        // Send ticket creation request
        fetch('/api/v1/tickets', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                title: title,
                description: description,
                priority: priority,
                cve_id: currentCveId
            })
        })
        .then(response => response.json())
        .then(data => {
            showLoading(false);
            
            if (data.success) {
                showAlert('Ticket criado com sucesso!', 'success');
                
                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('ticketModal'));
                modal.hide();
                
                // Clear form
                document.getElementById('ticketForm').reset();
            } else {
                showAlert(data.message || 'Erro ao criar ticket.', 'danger');
            }
        })
        .catch(error => {
            showLoading(false);
            console.error('Error:', error);
            showAlert('Erro de conexão. Tente novamente.', 'danger');
        });
    }

    // Pagination
    function initializePagination() {
        // Handle pagination clicks
        document.addEventListener('click', function(e) {
            if (e.target.closest('.page-link')) {
                e.preventDefault();
                const link = e.target.closest('.page-link');
                const href = link.getAttribute('href');
                
                if (href && href !== '#') {
                    loadPage(href);
                }
            }
        });
    }

    function loadPage(url) {
        showLoading(true);
        
        fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.text())
        .then(html => {
            // Parse the response and update the table
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            
            const newTable = doc.querySelector('#vulnerabilities-table');
            const newPagination = doc.querySelector('.pagination-section');
            
            if (newTable) {
                document.getElementById('vulnerabilities-table').replaceWith(newTable);
            }
            
            if (newPagination) {
                const currentPagination = document.querySelector('.pagination-section');
                if (currentPagination) {
                    currentPagination.replaceWith(newPagination);
                }
            }
            
            showLoading(false);
            
            // Reinitialize action buttons for new content
            initializeActionButtons();
        })
        .catch(error => {
            showLoading(false);
            console.error('Error loading page:', error);
            showAlert('Erro ao carregar página.', 'danger');
        });
    }

    // Filters
    function initializeFilters() {
        const filtersForm = document.querySelector('.filters-form');
        if (filtersForm) {
            filtersForm.addEventListener('submit', function(e) {
                e.preventDefault();
                applyFilters();
            });
        }
    }

    function applyFilters() {
        const form = document.querySelector('.filters-form');
        const formData = new FormData(form);
        const params = new URLSearchParams();
        
        for (let [key, value] of formData.entries()) {
            if (value) {
                params.append(key, value);
            }
        }
        
        const url = window.location.pathname + '?' + params.toString();
        loadPage(url);
    }

    // Utility Functions
    function showLoading(show) {
        const loadingOverlay = document.getElementById('table-loading');
        if (loadingOverlay) {
            if (show) {
                loadingOverlay.classList.remove('d-none');
            } else {
                loadingOverlay.classList.add('d-none');
            }
        }
    }

    function showAlert(message, type = 'info') {
        // Create alert element
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        document.body.appendChild(alertDiv);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }

    function getCSRFToken() {
        const token = document.querySelector('meta[name="csrf-token"]');
        return token ? token.getAttribute('content') : '';
    }

    // Cleanup function for memory management
    function cleanup() {
        // Clear all debounce timers
        Object.keys(debounceTimers).forEach(key => {
            clearTimeout(debounceTimers[key]);
        });
        
        // Remove all tracked event listeners
        eventListeners.forEach(({ element, event, handler, options }) => {
            if (element && element.removeEventListener) {
                element.removeEventListener(event, handler, options);
            }
        });
        
        // Reset state
        currentCveId = null;
        sortDirection = {};
        currentPage = 1;
        currentFilters = {};
        debounceTimers = {};
        eventListeners = [];
        isInitialized = false;
    }

    // Cleanup on page unload
    window.addEventListener('beforeunload', cleanup);

    // Export functions for global access if needed
    window.VulnerabilitiesPage = {
        showAlert: showAlert,
        showLoading: showLoading,
        loadPage: loadPage,
        cleanup: cleanup
    };

})();