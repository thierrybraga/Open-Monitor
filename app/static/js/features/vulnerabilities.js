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

    // Performance optimizations
    let virtualScrollEnabled = false;
    let visibleRowsCache = new Map();
    let filterCache = new Map();
    let lastFilterHash = '';
    
    // Using consolidated debounce from Utils.js
    
    // Virtual scrolling for large datasets
    function initializeVirtualScrolling() {
        const table = document.getElementById('vulnerabilities-table');
        const tbody = table?.querySelector('tbody');
        
        if (!tbody) return;
        
        const rows = tbody.querySelectorAll('tr');
        if (rows.length < 100) return; // Only enable for large datasets
        
        virtualScrollEnabled = true;
        const container = table.closest('.table-responsive');
        
        if (container) {
            container.style.maxHeight = '600px';
            container.style.overflowY = 'auto';
            
            // Implement intersection observer for visible rows
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    const row = entry.target;
                    if (entry.isIntersecting) {
                        // Load row content if not already loaded
                        if (row.dataset.lazy === 'true') {
                            loadRowContent(row);
                        }
                    }
                });
            }, {
                root: container,
                rootMargin: '50px'
            });
            
            rows.forEach(row => observer.observe(row));
        }
    }
    
    function loadRowContent(row) {
        // Simulate lazy loading of row content
        row.dataset.lazy = 'false';
        row.classList.remove('skeleton-row');
    }
    
    // Optimized filtering with caching
    function optimizedFilterTable(filters) {
        const filterHash = JSON.stringify(filters);
        
        // Check cache first
        if (filterHash === lastFilterHash && filterCache.has(filterHash)) {
            const cachedResults = filterCache.get(filterHash);
            applyFilterResults(cachedResults);
            return;
        }
        
        const table = document.getElementById('vulnerabilities-table');
        if (!table) return;
        
        const rows = table.querySelectorAll('tbody tr');
        const results = {
            visibleRows: [],
            hiddenRows: [],
            visibleCount: 0
        };
        
        // Use requestAnimationFrame for better performance
        const processRows = (startIndex = 0) => {
            const batchSize = 50; // Process in batches
            const endIndex = Math.min(startIndex + batchSize, rows.length);
            
            for (let i = startIndex; i < endIndex; i++) {
                const row = rows[i];
                const shouldShow = matchesFilters(row, filters);
                
                if (shouldShow) {
                    results.visibleRows.push(row);
                    results.visibleCount++;
                } else {
                    results.hiddenRows.push(row);
                }
            }
            
            if (endIndex < rows.length) {
                // Continue processing in next frame
                requestAnimationFrame(() => processRows(endIndex));
            } else {
                // Finished processing, cache and apply results
                filterCache.set(filterHash, results);
                lastFilterHash = filterHash;
                applyFilterResults(results);
                
                // Clean old cache entries (keep only last 5)
                if (filterCache.size > 5) {
                    const firstKey = filterCache.keys().next().value;
                    filterCache.delete(firstKey);
                }
            }
        };
        
        requestAnimationFrame(() => processRows());
    }
    
    function applyFilterResults(results) {
        // Apply visibility changes in batches
        const applyBatch = (rows, display, startIndex = 0) => {
            const batchSize = 25;
            const endIndex = Math.min(startIndex + batchSize, rows.length);
            
            for (let i = startIndex; i < endIndex; i++) {
                rows[i].style.display = display;
            }
            
            if (endIndex < rows.length) {
                requestAnimationFrame(() => applyBatch(rows, display, endIndex));
            }
        };
        
        requestAnimationFrame(() => {
            applyBatch(results.visibleRows, '');
            applyBatch(results.hiddenRows, 'none');
            
            // Update UI elements
            updateResultsCounter(results.visibleCount, results.visibleRows.length + results.hiddenRows.length);
            toggleEmptyState(results.visibleCount === 0);
        });
    }
    
    // Memory management
    function cleanupPerformanceData() {
        visibleRowsCache.clear();
        filterCache.clear();
        lastFilterHash = '';
    }
    
    // Performance monitoring
    function measureTablePerformance(operation, callback) {
        const startTime = performance.now();
        const startMemory = performance.memory ? performance.memory.usedJSHeapSize : 0;
        
        const result = callback();
        
        const endTime = performance.now();
        const endMemory = performance.memory ? performance.memory.usedJSHeapSize : 0;
        
        console.debug(`Performance [${operation}]:`, {
            duration: `${(endTime - startTime).toFixed(2)}ms`,
            memoryDelta: performance.memory ? `${((endMemory - startMemory) / 1024 / 1024).toFixed(2)}MB` : 'N/A'
        });
        
        return result;
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

    // Accessibility functions
    function initializeAccessibility() {
        // Add ARIA labels and roles
        const table = document.getElementById('vulnerabilities-table');
        if (table) {
            table.setAttribute('role', 'table');
            table.setAttribute('aria-label', 'Tabela de vulnerabilidades');
        }
        
        // Make sortable headers keyboard accessible
        const sortableHeaders = document.querySelectorAll('.sortable');
        sortableHeaders.forEach(header => {
            header.setAttribute('tabindex', '0');
            header.setAttribute('role', 'button');
            header.setAttribute('aria-sort', 'none');
        });
        
        // Add skip link for keyboard users
        addSkipLink();
        
        // Initialize focus management
        initializeFocusManagement();
    }
    
    function addSkipLink() {
        const skipLink = document.createElement('a');
        skipLink.href = '#vulnerabilities-table';
        skipLink.className = 'skip-link';
        skipLink.textContent = 'Pular para tabela de vulnerabilidades';
        skipLink.style.cssText = `
            position: absolute;
            top: -40px;
            left: 6px;
            background: #000;
            color: #fff;
            padding: 8px;
            text-decoration: none;
            z-index: 1000;
            border-radius: 4px;
        `;
        
        skipLink.addEventListener('focus', function() {
            this.style.top = '6px';
        });
        
        skipLink.addEventListener('blur', function() {
            this.style.top = '-40px';
        });
        
        document.body.insertBefore(skipLink, document.body.firstChild);
    }
    
    function initializeFocusManagement() {
        // Manage focus for dynamic content
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'childList') {
                    // Re-initialize accessibility for new content
                    const newButtons = mutation.target.querySelectorAll('.mitigate-btn, .ticket-btn');
                    newButtons.forEach(btn => {
                        if (!btn.hasAttribute('aria-label')) {
                            const cveId = btn.dataset.cveId;
                            const action = btn.classList.contains('mitigate-btn') ? 'Mitigar' : 'Criar ticket para';
                            btn.setAttribute('aria-label', `${action} vulnerabilidade ${cveId}`);
                        }
                    });
                }
            });
        });
        
        const tableContainer = document.querySelector('#vulnerabilities-table tbody');
        if (tableContainer) {
            observer.observe(tableContainer, { childList: true, subtree: true });
        }
    }
    
    function announceToScreenReader(message) {
        const announcement = document.createElement('div');
        announcement.setAttribute('aria-live', 'polite');
        announcement.setAttribute('aria-atomic', 'true');
        announcement.className = 'sr-only';
        announcement.textContent = message;
        
        document.body.appendChild(announcement);
        
        setTimeout(() => {
            document.body.removeChild(announcement);
        }, 1000);
    }
    
    function trapFocus(e) {
        if (e.key !== 'Tab') return;
        
        const modal = e.currentTarget;
        const focusableElements = modal.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        
        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];
        
        if (e.shiftKey) {
            if (document.activeElement === firstElement) {
                lastElement.focus();
                e.preventDefault();
            }
        } else {
            if (document.activeElement === lastElement) {
                firstElement.focus();
                e.preventDefault();
            }
        }
    }
    
    // Enhanced keyboard navigation for table
    function initializeKeyboardNavigation() {
        const table = document.getElementById('vulnerabilities-table');
        if (!table) return;
        
        // Add keyboard navigation to table rows
        const tbody = table.querySelector('tbody');
        if (tbody) {
            tbody.addEventListener('keydown', function(e) {
                const currentRow = e.target.closest('tr');
                if (!currentRow) return;
                
                const rows = Array.from(tbody.querySelectorAll('tr:not([style*="display: none"])'));
                const currentIndex = rows.indexOf(currentRow);
                
                let targetRow = null;
                
                switch (e.key) {
                    case 'ArrowDown':
                        e.preventDefault();
                        targetRow = rows[currentIndex + 1] || rows[0];
                        break;
                    case 'ArrowUp':
                        e.preventDefault();
                        targetRow = rows[currentIndex - 1] || rows[rows.length - 1];
                        break;
                    case 'Home':
                        e.preventDefault();
                        targetRow = rows[0];
                        break;
                    case 'End':
                        e.preventDefault();
                        targetRow = rows[rows.length - 1];
                        break;
                    case 'Enter':
                    case ' ':
                        e.preventDefault();
                        // Focus on first action button in the row
                        const actionBtn = currentRow.querySelector('.mitigate-btn, .ticket-btn');
                        if (actionBtn) {
                            actionBtn.focus();
                        }
                        break;
                }
                
                if (targetRow) {
                    targetRow.focus();
                    // Announce row change to screen readers
                    const cveId = targetRow.dataset.cveId;
                    const severity = targetRow.querySelector('.severity-badge')?.textContent;
                    if (cveId && severity) {
                        announceToScreenReader(`Linha ${currentIndex + 1}: ${cveId}, severidade ${severity}`);
                    }
                }
            });
            
            // Make table rows focusable
            const rows = tbody.querySelectorAll('tr');
            rows.forEach((row, index) => {
                row.setAttribute('tabindex', index === 0 ? '0' : '-1');
                row.setAttribute('role', 'row');
                
                // Add focus styles
                row.addEventListener('focus', function() {
                    this.classList.add('table-row-focused');
                });
                
                row.addEventListener('blur', function() {
                    this.classList.remove('table-row-focused');
                });
            });
        }
        
        // Enhanced keyboard support for filters
        const filterInputs = document.querySelectorAll('#search-input, #severity, #cvss-filter, #date-filter');
        filterInputs.forEach(input => {
            input.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') {
                    this.value = '';
                    this.dispatchEvent(new Event('input', { bubbles: true }));
                    announceToScreenReader('Filtro limpo');
                }
            });
        });
        
        // Global keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            // Alt + F to focus search
            if (e.altKey && e.key === 'f') {
                e.preventDefault();
                const searchInput = document.getElementById('search-input');
                if (searchInput) {
                    searchInput.focus();
                    announceToScreenReader('Foco no campo de busca');
                }
            }
            
            // Alt + T to focus table
            if (e.altKey && e.key === 't') {
                e.preventDefault();
                const firstRow = document.querySelector('#vulnerabilities-table tbody tr[tabindex="0"]');
                if (firstRow) {
                    firstRow.focus();
                    announceToScreenReader('Foco na tabela de vulnerabilidades');
                }
            }
            
            // Alt + C to clear all filters
            if (e.altKey && e.key === 'c') {
                e.preventDefault();
                clearAllFilters();
                announceToScreenReader('Todos os filtros foram limpos');
            }
        });
    }

    function initializeVulnerabilitiesPage() {
        initializeTableSorting();
        initializeActionButtons();
        initializeModals();
        initializePagination();
        initializeFilters();
        initializeVirtualScrolling();
        initializeAccessibility();

        // Atualizar contador de resultados e estado vazio no carregamento inicial
        const tableEl = document.getElementById('vulnerabilities-table');
        const tbodyEl = tableEl ? tableEl.querySelector('tbody') : null;
        const allRows = tbodyEl ? Array.from(tbodyEl.querySelectorAll('tr')) : [];
        const visibleCount = allRows.filter(r => r.style.display !== 'none').length;
        if (typeof updateResultsCounter === 'function') {
            updateResultsCounter(visibleCount, allRows.length);
        }
        if (typeof toggleEmptyState === 'function') {
            toggleEmptyState(visibleCount === 0);
        }
        
        isInitialized = true;
        console.log('Vulnerabilities page initialized successfully');
    }

    // Table Sorting with debounce
    function initializeTableSorting() {
        const sortableHeaders = document.querySelectorAll('.sortable');
        sortableHeaders.forEach(header => {
            const debouncedSort = Utils.debounce((sortField, headerElement) => {
                handleSort(sortField, headerElement);
            }, 200, 'sort');
            const handler = function() {
                const sortField = this.dataset.sort;
                debouncedSort(sortField, this);
            };
            const keyHandler = function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handler.call(this);
                }
            };
            addEventListenerTracked(header, 'click', handler);
            addEventListenerTracked(header, 'keydown', keyHandler);
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
        // Reset all sort icons and ARIA attributes
        document.querySelectorAll('.sortable').forEach(header => {
            header.setAttribute('aria-sort', 'none');
            const icon = header.querySelector('.sort-icon');
            if (icon) {
                // Support both Font Awesome and Bootstrap Icons
                if (icon.classList.contains('fa') || icon.classList.contains('fas') || icon.classList.contains('fa-sort') || icon.classList.contains('fa-sort-up') || icon.classList.contains('fa-sort-down')) {
                    icon.className = 'fas fa-sort sort-icon';
                } else {
                    icon.className = 'bi bi-chevron-expand sort-icon';
                }
            }
        });
        
        // Update active header icon and ARIA
        const icon = activeHeader.querySelector('.sort-icon');
        if (direction === 'asc') {
            if (icon) {
                if (icon.classList.contains('fa') || icon.classList.contains('fas')) {
                    icon.className = 'fas fa-sort-up sort-icon';
                } else {
                    icon.className = 'bi bi-chevron-up sort-icon';
                }
            }
            activeHeader.setAttribute('aria-sort', 'ascending');
        } else {
            if (icon) {
                if (icon.classList.contains('fa') || icon.classList.contains('fas')) {
                    icon.className = 'fas fa-sort-down sort-icon';
                } else {
                    icon.className = 'bi bi-chevron-down sort-icon';
                }
            }
            activeHeader.setAttribute('aria-sort', 'descending');
        }
        
        // Announce sort change to screen readers
        const columnName = activeHeader.textContent.trim();
        const sortDirection = direction === 'asc' ? 'crescente' : 'decrescente';
        announceToScreenReader(`Tabela ordenada por ${columnName} em ordem ${sortDirection}`);
    }

    function sortTable(field, direction) {
        const table = document.getElementById('vulnerabilities-table');
        if (!table) return;
        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        const allRows = Array.from(tbody.querySelectorAll('tr'));
        const visibleRows = allRows.filter(row => row.style.display !== 'none');
        const hiddenRows = allRows.filter(row => row.style.display === 'none');

        const parseDate = (text) => {
            if (!text) return new Date(0);
            const trimmed = text.trim();
            if (/^\d{2}\/\d{2}\/\d{4}$/.test(trimmed)) {
                // dd/mm/yyyy -> yyyy-mm-dd
                return new Date(trimmed.split('/').reverse().join('-'));
            }
            // Assume ISO yyyy-mm-dd or Date-parsable string
            return new Date(trimmed);
        };

        const severityOrder = { critical: 4, high: 3, medium: 2, low: 1 };

        visibleRows.sort((a, b) => {
            let aValue, bValue;
            switch(field) {
                case 'cve_id': {
                    const aText = a.querySelector('td:nth-child(1)')?.textContent.trim() || '';
                    const bText = b.querySelector('td:nth-child(1)')?.textContent.trim() || '';
                    aValue = aText;
                    bValue = bText;
                    break;
                }
                case 'severity': {
                    const aText = a.querySelector('.severity-badge')?.textContent.toLowerCase().trim() || '';
                    const bText = b.querySelector('.severity-badge')?.textContent.toLowerCase().trim() || '';
                    aValue = severityOrder[aText] || 0;
                    bValue = severityOrder[bText] || 0;
                    break;
                }
                case 'cvss_score': {
                    const aCvssText = a.querySelector('td:nth-child(6)')?.textContent.trim() || 
                                      (a.querySelector('td:nth-child(3)')?.textContent.match(/cvss:\s*([\d.]+)/i)?.[1] || '0');
                    const bCvssText = b.querySelector('td:nth-child(6)')?.textContent.trim() || 
                                      (b.querySelector('td:nth-child(3)')?.textContent.match(/cvss:\s*([\d.]+)/i)?.[1] || '0');
                    aValue = parseFloat(aCvssText) || 0;
                    bValue = parseFloat(bCvssText) || 0;
                    break;
                }
                case 'published_date': {
                    const aDateText = a.querySelector('td:nth-child(7)')?.textContent.trim() || 
                                      (a.querySelector('td:nth-child(3)')?.textContent.match(/(\d{2}\/\d{2}\/\d{4})/)?.[1] || '');
                    const bDateText = b.querySelector('td:nth-child(7)')?.textContent.trim() || 
                                      (b.querySelector('td:nth-child(3)')?.textContent.match(/(\d{2}\/\d{2}\/\d{4})/)?.[1] || '');
                    aValue = parseDate(aDateText);
                    bValue = parseDate(bDateText);
                    break;
                }
                default:
                    return 0;
            }

            if (direction === 'asc') {
                return aValue > bValue ? 1 : aValue < bValue ? -1 : 0;
            } else {
                return aValue < bValue ? 1 : aValue > bValue ? -1 : 0;
            }
        });

        // Clear tbody and append sorted visible rows followed by hidden rows to preserve ordering
        tbody.innerHTML = '';
        visibleRows.forEach(row => tbody.appendChild(row));
        hiddenRows.forEach(row => tbody.appendChild(row));
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
    const modal = window.getModalInstance(document.getElementById('mitigateModal'));
        
        // Update modal title with CVE ID
        const modalTitle = document.querySelector('#mitigateModalLabel');
        modalTitle.innerHTML = `<i class="bi bi-shield-check"></i> Mitigar Vulnerabilidade ${currentCveId}`;
        
        modal.show();
    }

    function showTicketModal() {
    const modal = window.getModalInstance(document.getElementById('ticketModal'));
        
        // Update modal title and pre-fill ticket title
        const modalTitle = document.querySelector('#ticketModalLabel');
        modalTitle.innerHTML = `<i class="bi bi-ticket-perforated"></i> Abrir Ticket para ${currentCveId}`;
        
        const ticketTitle = document.getElementById('ticketTitle');
        ticketTitle.value = `Vulnerabilidade ${currentCveId} - Ação Necessária`;
        
        modal.show();
    }

    // Modals
    function initializeModals() {
        let previousFocus = null;
        
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
        
        // Focus management for modals
        const modals = ['mitigateModal', 'ticketModal'];
        modals.forEach(modalId => {
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.addEventListener('shown.bs.modal', function() {
                    const firstInput = modal.querySelector('textarea, input, select, button');
                    if (firstInput) firstInput.focus();
                });
                
                modal.addEventListener('hidden.bs.modal', function() {
                    if (previousFocus) {
                        previousFocus.focus();
                        previousFocus = null;
                    }
                });
                
                // Trap focus in modal
                modal.addEventListener('keydown', trapFocus);
            }
        });
        
        // Store focus reference when opening modals
        document.addEventListener('click', function(e) {
            if (e.target.closest('.mitigate-btn, .ticket-btn')) {
                previousFocus = e.target.closest('.mitigate-btn, .ticket-btn');
            }
        });
    }

    function handleMitigate() {
        const notes = document.getElementById('mitigationNotes').value;
        const status = document.getElementById('mitigationStatus').value;
        const confirmBtn = document.getElementById('confirmMitigate');
        
        if (!notes.trim()) {
            showAlert('Por favor, adicione notas de mitigação.', 'warning');
            // Focus back to notes field for accessibility
            document.getElementById('mitigationNotes').focus();
            return;
        }
        
        showButtonLoading(confirmBtn, true);
        
        // Announce action to screen readers
        announceToScreenReader(`Processando mitigação da vulnerabilidade ${currentCveId}`);
        
        // Send mitigation request
        fetch(`/api/vulnerabilities/${currentCveId}/mitigate`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-CSRF-Token': getCSRFToken(),
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                notes: notes,
                status: status
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert('Vulnerabilidade mitigada com sucesso!', 'success');
                
                // Update UI accessibility
                const row = document.querySelector(`tr[data-cve-id="${currentCveId}"]`);
                if (row) {
                    const badge = row.querySelector('.severity-badge');
                    if (badge) {
                        badge.textContent = 'Mitigada';
                        badge.className = 'badge bg-success';
                        badge.setAttribute('aria-label', 'Status: Mitigada');
                    }
                    
                    // Update row accessibility
                    row.setAttribute('aria-describedby', `vuln-${currentCveId}-mitigated`);
                    
                    // Add hidden description for screen readers
                    const description = document.createElement('div');
                    description.id = `vuln-${currentCveId}-mitigated`;
                    description.className = 'visually-hidden';
                    description.textContent = `Vulnerabilidade ${currentCveId} foi mitigada`;
                    row.appendChild(description);
                }
                
                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('mitigateModal'));
                modal.hide();
                
                // Announce completion
                announceToScreenReader(`Vulnerabilidade ${currentCveId} mitigada com sucesso`);
                
                // Refresh page or update row
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            } else {
                showAlert(data.message || 'Erro ao mitigar vulnerabilidade.', 'danger');
                announceToScreenReader('Erro ao processar mitigação');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Erro de conexão. Tente novamente.', 'danger');
            announceToScreenReader('Erro de conexão ao processar mitigação');
        })
        .finally(() => {
            showButtonLoading(confirmBtn, false);
        });
    }

    function handleCreateTicket() {
        const title = document.getElementById('ticketTitle').value;
        const description = document.getElementById('ticketDescription').value;
        const priority = document.getElementById('ticketPriority').value;
        const confirmBtn = document.getElementById('confirmTicket');
        
        if (!title.trim() || !description.trim()) {
            showAlert('Por favor, preencha título e descrição do ticket.', 'warning');
            // Focus on first empty field for accessibility
            if (!title.trim()) {
                document.getElementById('ticketTitle').focus();
            } else {
                document.getElementById('ticketDescription').focus();
            }
            return;
        }
        
        showButtonLoading(confirmBtn, true);
        
        // Announce action to screen readers
        announceToScreenReader(`Criando ticket para vulnerabilidade ${currentCveId}`);
        
        // Send ticket creation request
        fetch('/api/v1/tickets', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-CSRF-Token': getCSRFToken(),
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
            if (data.success) {
                showAlert('Ticket criado com sucesso!', 'success');
                
                // Update UI to show ticket was created
                const row = document.querySelector(`tr[data-cve-id="${currentCveId}"]`);
                if (row) {
                    const actionsCell = row.querySelector('td:last-child');
                    if (actionsCell) {
                        // Add ticket indicator
                        const ticketIndicator = document.createElement('span');
                        ticketIndicator.className = 'badge bg-info ms-1';
                        ticketIndicator.textContent = 'Ticket Criado';
                        ticketIndicator.setAttribute('aria-label', `Ticket ${data.ticket_id || 'criado'} para esta vulnerabilidade`);
                        actionsCell.appendChild(ticketIndicator);
                    }
                }
                
                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('ticketModal'));
                modal.hide();
                
                // Clear form
                document.getElementById('ticketForm').reset();
                
                // Announce completion
                announceToScreenReader(`Ticket ${data.ticket_id || ''} criado com sucesso para vulnerabilidade ${currentCveId}`);
            } else {
                showAlert(data.message || 'Erro ao criar ticket.', 'danger');
                announceToScreenReader('Erro ao criar ticket');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Erro de conexão. Tente novamente.', 'danger');
            announceToScreenReader('Erro de conexão ao criar ticket');
        })
        .finally(() => {
            showButtonLoading(confirmBtn, false);
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
        // Show skeleton loading for better UX
        showSkeletonLoading(true);
        showProgressBar(true);
        
        // Performance monitoring for page loading
        measureTablePerformance('page-loading', () => {
            return fetch(url, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.text())
            .then(html => {
                // Parse the response and update the table/card
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                
                const newCard = doc.querySelector('.table-card') || doc.querySelector('.table-section');
                const newTable = doc.querySelector('#vulnerabilities-table');
                const newPagination = doc.querySelector('.pagination-section');
                
                const currentCard = document.querySelector('.table-card') || document.querySelector('.table-section') || document.getElementById('vulnerabilities-table')?.closest('.table-section');
                
                if (newCard && currentCard) {
                    // Replace the whole container to include table, pagination, empty-state, etc.
                    cleanupPerformanceData();
                    currentCard.replaceWith(newCard);
                } else {
                    // Fallback: replace table and pagination independently
                    if (newTable) {
                        cleanupPerformanceData();
                        const currentTable = document.getElementById('vulnerabilities-table');
                        if (currentTable) currentTable.replaceWith(newTable);
                    }
                    if (newPagination) {
                        const currentPagination = document.querySelector('.pagination-section');
                        if (currentPagination) currentPagination.replaceWith(newPagination);
                    }
                }
                
                // Reinitialize interactive features for new content
                initializeActionButtons();
                initializeTableSorting && initializeTableSorting();
                initializeKeyboardNavigation && initializeKeyboardNavigation();
                initializePagination && initializePagination();
                
                // Update results counter based on current DOM
                const tableEl = document.getElementById('vulnerabilities-table');
                const tbodyEl = tableEl?.querySelector('tbody');
                const allRows = tbodyEl ? Array.from(tbodyEl.querySelectorAll('tr')) : [];
                const visibleCount = allRows.filter(r => r.style.display !== 'none').length;
                updateResultsCounter && updateResultsCounter(visibleCount, allRows.length);
                toggleEmptyState && toggleEmptyState();
                
                // Initialize virtual scrolling for new content if needed
                setTimeout(() => {
                    initializeVirtualScrolling && initializeVirtualScrolling();
                }, 100);
            })
            .catch(error => {
                console.error('Error loading page:', error);
                showAlert('Erro ao carregar página.', 'danger');
            })
            .finally(() => {
                showProgressBar(false);
                showSkeletonLoading(false);
            });
        });
    }

    // Filters
    function initializeFilters() {
        const filtersForm = document.querySelector('.filters-form');
        if (filtersForm) {
        filtersForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const filterBtn = document.getElementById('search-btn');
            if (filterBtn) {
                showButtonLoading(filterBtn, true);
            }
            const promise = applyFilters();
            if (promise && typeof promise.finally === 'function') {
                promise.finally(() => {
                    if (filterBtn) showButtonLoading(filterBtn, false);
                });
            } else {
                setTimeout(() => {
                    if (filterBtn) showButtonLoading(filterBtn, false);
                }, 600);
            }
        });
    }
        
        // Initialize advanced filters
        initializeAdvancedFilters();
        
        // Initialize real-time search
        initializeRealTimeFilters();
    }
    
    function initializeAdvancedFilters() {
        // Toggle do ícone dos filtros avançados
        const advancedToggle = document.querySelector('[data-bs-target="#advanced-filters"]');
        if (advancedToggle) {
            advancedToggle.addEventListener('click', function() {
                const icon = this.querySelector('i');
                const isExpanded = this.getAttribute('aria-expanded') === 'true';
                
                setTimeout(() => {
                    const actualExpanded = document.getElementById('advanced-filters').classList.contains('show');
                    if (actualExpanded) {
                        icon.className = 'fas fa-chevron-up me-2';
                    } else {
                        icon.className = 'fas fa-chevron-down me-2';
                    }
                }, 100);
            });
        }
        
        // Filtros avançados com debounce
        const advancedFilters = [
            'start-date-filter',
            'end-date-filter', 
            'product-filter',
            'mitigation-status-filter',
            'vuln-type-filter'
        ];
        
        advancedFilters.forEach(filterId => {
            const element = document.getElementById(filterId);
            if (element) {
                if (element.type === 'text') {
                    const debouncedFilter = Utils.debounce(() => {
                        applyClientSideFilters();
                    }, 500, filterId);
                    addEventListenerTracked(element, 'input', debouncedFilter);
                } else {
                    addEventListenerTracked(element, 'change', applyClientSideFilters);
                }
            }
        });
    }
    
    function initializeRealTimeFilters() {
        // Busca em tempo real
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            const debouncedSearch = Utils.debounce(() => {
                applyClientSideFilters();
            }, 300, 'search');
            addEventListenerTracked(searchInput, 'input', debouncedSearch);
        }
        
        // Filtros básicos
        const basicFilters = ['cvss-filter', 'date-filter'];
        basicFilters.forEach(filterId => {
            const element = document.getElementById(filterId);
            if (element) {
                addEventListenerTracked(element, 'change', applyClientSideFilters);
            }
        });
        
        // Botão limpar filtros
        const clearBtn = document.getElementById('clear-filters-btn');
        if (clearBtn) {
            addEventListenerTracked(clearBtn, 'click', function(e) {
                e.preventDefault();
                clearAllFilters();
            });
        }
    }
    
    function applyClientSideFilters() {
        const filters = getActiveFilters();
        
        // Use optimized filtering for better performance
        measureTablePerformance('client-side-filtering', () => {
            if (virtualScrollEnabled) {
                optimizedFilterTable(filters);
            } else {
                filterTable(filters);
            }
        });
        
        updateFilterIndicators(filters);
    }
    
    function getActiveFilters() {
        return {
            search: document.getElementById('search-input')?.value || '',
            severity: document.getElementById('severity')?.value || '',
            cvssRange: document.getElementById('cvss-filter')?.value || '',
            dateRange: document.getElementById('date-filter')?.value || '',
            startDate: document.getElementById('start-date-filter')?.value || '',
            endDate: document.getElementById('end-date-filter')?.value || '',
            product: document.getElementById('product-filter')?.value || '',
            mitigationStatus: document.getElementById('mitigation-status-filter')?.value || '',
            vulnType: document.getElementById('vuln-type-filter')?.value || '',
            sortBy: document.getElementById('sort-filter')?.value || 'published_date_desc'
        };
    }
    
    function filterTable(filters) {
        const table = document.getElementById('vulnerabilities-table');
        if (!table) return;
        
        const rows = table.querySelectorAll('tbody tr');
        let visibleCount = 0;
        
        // Use performance monitoring for large datasets
        if (rows.length > 50) {
            measureTablePerformance('standard-filtering', () => {
                rows.forEach(row => {
                    const shouldShow = matchesFilters(row, filters);
                    row.style.display = shouldShow ? '' : 'none';
                    if (shouldShow) visibleCount++;
                });
            });
        } else {
            rows.forEach(row => {
                const shouldShow = matchesFilters(row, filters);
                row.style.display = shouldShow ? '' : 'none';
                if (shouldShow) visibleCount++;
            });
        }
        
        // Atualizar contador de resultados
        updateResultsCounter(visibleCount, rows.length);
        
        // Mostrar estado vazio se necessário
        toggleEmptyState(visibleCount === 0);
        
        // Aplicar ordenação se especificada
        if (filters.sortBy && filters.sortBy !== 'published_date_desc') {
            applySorting(filters.sortBy);
        }
    }
    
    function matchesFilters(row, filters) {
        const cells = row.querySelectorAll('td');
        if (cells.length === 0) return false;
        
        const cveId = cells[0]?.textContent?.toLowerCase() || '';
        const severity = cells[1]?.querySelector('.severity-badge')?.textContent?.toLowerCase() || '';
        const description = cells[2]?.textContent?.toLowerCase() || '';
        
        // CVSS score is in the 5th column (index 4). Fallback to description if needed
        let cvssScore = 0;
        const cvssCell = cells[4];
        const cvssText = cvssCell?.textContent?.trim();
        if (cvssText) {
            cvssScore = parseFloat(cvssText) || 0;
        } else {
            const cvssMatch = description.match(/cvss:\s*([\d.]+)/i);
            if (cvssMatch) {
                cvssScore = parseFloat(cvssMatch[1]) || 0;
            }
        }
        
        let publishedDate = '';
        const dateCell = cells[5];
        const dateText = dateCell?.textContent?.trim();
        if (dateText) {
            publishedDate = dateText;
        } else {
            const dateMatch = description.match(/(\d{2}\/\d{2}\/\d{4})/);
            if (dateMatch) {
                publishedDate = dateMatch[1];
            }
        }
        
        // Filtro de busca
        if (filters.search) {
            const searchTerm = filters.search.toLowerCase();
            if (!cveId.includes(searchTerm) && 
                !description.includes(searchTerm) && 
                !severity.includes(searchTerm)) {
                return false;
            }
        }
        
        // Filtro de severidade
        if (filters.severity && !severity.includes(filters.severity.toLowerCase())) {
            return false;
        }
        
        // Filtro de CVSS Score
        if (filters.cvssRange && cvssScore > 0) {
            const [min, max] = filters.cvssRange.split('-').map(parseFloat);
            if (cvssScore < min || cvssScore > max) {
                return false;
            }
        }
        
        // Filtro de data
        if (filters.dateRange && publishedDate) {
            const days = parseInt(filters.dateRange, 10);
            const cutoffDate = new Date();
            cutoffDate.setDate(cutoffDate.getDate() - days);
            
            let rowDate;
            if (publishedDate.includes('/')) {
                // Format: DD/MM/YYYY
                rowDate = new Date(publishedDate.split('/').reverse().join('-'));
            } else {
                // Assume ISO format YYYY-MM-DD
                rowDate = new Date(publishedDate);
            }
            if (rowDate instanceof Date && !isNaN(rowDate)) {
                if (rowDate < cutoffDate) {
                    return false;
                }
            }
        }
        
        // Filtro de produto
        if (filters.product) {
            const productTerm = filters.product.toLowerCase();
            if (!description.includes(productTerm)) {
                return false;
            }
        }
        
        return true;
    }
    
    function clearAllFilters() {
        // Limpar filtros básicos
        const basicFilters = ['search-input', 'cvss-filter', 'date-filter'];
        basicFilters.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.value = '';
            }
        });
        
        // Limpar filtros avançados
        const advancedFilters = [
            'start-date-filter', 'end-date-filter', 'product-filter',
            'mitigation-status-filter', 'vuln-type-filter'
        ];
        advancedFilters.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.value = '';
            }
        });
        
        // Resetar ordenação
        const sortFilter = document.getElementById('sort-filter');
        if (sortFilter) {
            sortFilter.value = 'published_date_desc';
        }
        
        // Aplicar filtros limpos
        applyClientSideFilters();
    }
    
    function updateResultsCounter(visible, total) {
        let counter = document.getElementById('results-counter');
        if (!counter) {
            // Criar contador se não existir
            counter = document.createElement('div');
            counter.id = 'results-counter';
            counter.className = 'text-muted small mb-3';
            
            const tableCard = document.querySelector('.table-card') || document.querySelector('.table-section');
            if (tableCard) {
                tableCard.insertBefore(counter, tableCard.firstChild);
            }
        }
        
        counter.innerHTML = `<i class="fas fa-info-circle me-1"></i>Mostrando <strong>${visible}</strong> de <strong>${total}</strong> vulnerabilidades`;
    }
    
    function toggleEmptyState(show) {
        const tableContainer = document.querySelector('.table-responsive');
        let emptyState = document.querySelector('.filter-empty-state');
        
        if (show) {
            if (!emptyState) {
                emptyState = document.createElement('div');
                emptyState.className = 'filter-empty-state empty-state';
                emptyState.innerHTML = `
                    <div class="empty-state-icon">
                        <i class="fas fa-filter"></i>
                    </div>
                    <h4 class="empty-state-title">Nenhuma vulnerabilidade encontrada</h4>
                    <p class="empty-state-description">
                        Nenhuma vulnerabilidade corresponde aos filtros aplicados. 
                        Tente ajustar os critérios de busca.
                    </p>
                    <div class="empty-state-action">
                        <button class="btn btn-outline-primary" onclick="VulnerabilitiesPage.clearAllFilters()">
                            <i class="fas fa-times me-2"></i>Limpar Filtros
                        </button>
                    </div>
                `;
                
                const tableCard = document.querySelector('.table-card') || document.querySelector('.table-section');
                if (tableCard) {
                    tableCard.appendChild(emptyState);
                }
            }
            
            if (tableContainer) tableContainer.style.display = 'none';
            emptyState.style.display = 'block';
        } else {
            if (tableContainer) tableContainer.style.display = 'block';
            if (emptyState) emptyState.style.display = 'none';
        }
    }
    
    function updateFilterIndicators(filters) {
        const activeFiltersCount = Object.values(filters).filter(value => 
            value && value !== 'published_date_desc'
        ).length;
        
        // Atualizar badge de filtros ativos
        let badge = document.getElementById('active-filters-badge');
        if (activeFiltersCount > 0) {
            if (!badge) {
                badge = document.createElement('span');
                badge.id = 'active-filters-badge';
                badge.className = 'badge bg-primary ms-2';
                
                const advancedToggle = document.querySelector('[data-bs-target="#advanced-filters"]');
                if (advancedToggle) {
                    advancedToggle.appendChild(badge);
                }
            }
            badge.textContent = activeFiltersCount;
        } else if (badge) {
            badge.remove();
        }
    }
    
    function applySorting(sortBy) {
        const table = document.getElementById('vulnerabilities-table');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr:not([style*="display: none"])'));

        rows.sort((a, b) => {
            let aValue, bValue;
            const parts = sortBy.split('_');
            const direction = parts[parts.length - 1];
            let field = parts[0];
            if (field === 'cvss_score') field = 'cvss';
            if (field === 'published') field = 'published';
            if (field === 'severity') field = 'severity';

            switch(field) {
                case 'published':
                    const aDateText = a.querySelector('td:nth-child(7)')?.textContent.trim() || 
                                     a.querySelector('td:nth-child(3)')?.textContent.match(/(\d{2}\/\d{2}\/\d{4})/)?.[1] || '';
                    const bDateText = b.querySelector('td:nth-child(7)')?.textContent.trim() || 
                                     b.querySelector('td:nth-child(3)')?.textContent.match(/(\d{2}\/\d{2}\/\d{4})/)?.[1] || '';
                    aValue = new Date(aDateText.split('/').reverse().join('-'));
                    bValue = new Date(bDateText.split('/').reverse().join('-'));
                    break;
                case 'cvss':
                    const aCvssText = a.querySelector('td:nth-child(6)')?.textContent.trim() || 
                                      a.querySelector('td:nth-child(3)')?.textContent.match(/cvss:\s*([\d.]+)/i)?.[1] || '0';
                    const bCvssText = b.querySelector('td:nth-child(6)')?.textContent.trim() || 
                                      b.querySelector('td:nth-child(3)')?.textContent.match(/cvss:\s*([\d.]+)/i)?.[1] || '0';
                    aValue = parseFloat(aCvssText) || 0;
                    bValue = parseFloat(bCvssText) || 0;
                    break;
                case 'severity':
                    const severityOrder = { 'critical': 4, 'high': 3, 'medium': 2, 'low': 1 };
                    aValue = severityOrder[a.querySelector('.severity-badge')?.textContent.toLowerCase().trim()] || 0;
                    bValue = severityOrder[b.querySelector('.severity-badge')?.textContent.toLowerCase().trim()] || 0;
                    break;
                default:
                    return 0;
            }

            if (direction === 'desc') {
                return aValue < bValue ? 1 : aValue > bValue ? -1 : 0;
            } else {
                return aValue > bValue ? 1 : aValue < bValue ? -1 : 0;
            }
        });

        // Reordenar apenas as linhas visíveis
        const allRows = Array.from(tbody.querySelectorAll('tr'));
        const hiddenRows = allRows.filter(row => row.style.display === 'none');

        tbody.innerHTML = '';
        rows.forEach(row => tbody.appendChild(row));
        hiddenRows.forEach(row => tbody.appendChild(row));
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
        return loadPage(url);
    }

    // Loading and alerts
    function showLoading(show = true, target = null) {
        if (target) {
            // Show loading for specific element
            if (show) {
                target.classList.add('filter-loading');
            } else {
                target.classList.remove('filter-loading');
            }
        } else {
            // Global loading overlay
            const loadingOverlay = document.getElementById('table-loading');
            if (loadingOverlay) {
                if (show) {
                    loadingOverlay.classList.remove('d-none');
                } else {
                    loadingOverlay.classList.add('d-none');
                }
            }
        }
    }
    
    function showTableLoading(show = true) {
        const tableContainer = document.querySelector('.table-container');
        if (!tableContainer) return;
        
        let overlay = tableContainer.querySelector('.table-loading-overlay');
        
        if (show) {
            if (!overlay) {
                overlay = document.createElement('div');
                overlay.className = 'table-loading-overlay';
                overlay.innerHTML = `
                    <div class="loading-state">
                        <div class="loading-spinner"></div>
                        <div class="loading-text">Carregando vulnerabilidades...</div>
                    </div>
                `;
                tableContainer.appendChild(overlay);
            }
            overlay.style.display = 'flex';
        } else {
            if (overlay) {
                overlay.style.display = 'none';
            }
        }
    }
    
    function showSkeletonLoading(show = true) {
        const tableBody = document.querySelector('#vulnerabilities-table tbody');
        if (!tableBody) return;
        tableBody.innerHTML = '';
        for (let i = 0; i < 10; i++) {
          const row = document.createElement('tr');
          row.innerHTML = `
            <th scope="row"><span class="skeleton-box" style="width: 120px;"></span></th>
            <td><span class="skeleton-box" style="width: 80px;"></span></td>
            <td><span class="skeleton-box" style="width: 260px;"></span></td>
            <td class="d-none-mobile"><span class="skeleton-box" style="width: 160px;"></span></td>
            <td class="d-none-mobile"><span class="skeleton-box" style="width: 160px;"></span></td>
            <td class="d-none-mobile"><span class="skeleton-box" style="width: 80px;"></span></td>
            <td class="d-none-mobile"><span class="skeleton-box" style="width: 120px;"></span></td>
            <td class="text-center"><span class="skeleton-box" style="width: 100px;"></span></td>
          `;
          tableBody.appendChild(row);
        }
      }
    
    function showButtonLoading(button, show = true) {
        if (!button) return;
        
        if (show) {
            button.classList.add('btn-loading');
            button.disabled = true;
        } else {
            button.classList.remove('btn-loading');
            button.disabled = false;
        }
    }
    
    function showProgressBar(show = true, container = null) {
        const targetContainer = container || document.querySelector('.table-card') || document.querySelector('.table-section');
        if (!targetContainer) return;
        
        let progressBar = targetContainer.querySelector('.loading-progress');
        
        if (show) {
            if (!progressBar) {
                progressBar = document.createElement('div');
                progressBar.className = 'loading-progress';
                progressBar.innerHTML = '<div class="loading-progress-bar"></div>';
                targetContainer.insertBefore(progressBar, targetContainer.firstChild);
            }
            progressBar.style.display = 'block';
        } else {
            if (progressBar) {
                progressBar.style.display = 'none';
            }
        }
    }

    // Toast Notification System
    function showToast(message, type = 'info', duration = 5000) {
        // Ensure toast container exists
        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container';
            document.body.appendChild(toastContainer);
        }
        
        // Create toast element
        const toastId = 'toast-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.id = toastId;
        
        // Get icon based on type
        const icons = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };
        
        // Get title based on type
        const titles = {
            success: 'Sucesso',
            error: 'Erro',
            warning: 'Atenção',
            info: 'Informação'
        };
        
        toast.innerHTML = `
            <div class="toast-header">
                <i class="${icons[type]} toast-icon"></i>
                <strong class="toast-title">${titles[type]}</strong>
                <button type="button" class="toast-close" onclick="VulnerabilitiesPage.closeToast('${toastId}')">
                    &times;
                </button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
            <div class="toast-progress" style="width: 100%;"></div>
        `;
        
        toastContainer.appendChild(toast);
        
        // Show toast with animation
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);
        
        // Auto-hide with progress bar animation
        if (duration > 0) {
            const progressBar = toast.querySelector('.toast-progress');
            if (progressBar) {
                progressBar.style.transition = `width ${duration}ms linear`;
                setTimeout(() => {
                    progressBar.style.width = '0%';
                }, 100);
            }
            
            setTimeout(() => {
                closeToast(toastId);
            }, duration);
        }
        
        return toastId;
    }
    
    function closeToast(toastId) {
        const toast = document.getElementById(toastId);
        if (toast) {
            toast.classList.remove('show');
            toast.classList.add('hide');
            
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.remove();
                }
                
                // Clean up empty container
                const container = document.querySelector('.toast-container');
                if (container && container.children.length === 0) {
                    container.remove();
                }
            }, 300);
        }
    }
    
    function closeAllToasts() {
        const toasts = document.querySelectorAll('.toast.show');
        toasts.forEach(toast => {
            closeToast(toast.id);
        });
    }
    
    // Legacy function for backward compatibility
    function showAlert(message, type = 'info') {
        // Map old alert types to toast types
        const typeMap = {
            'success': 'success',
            'danger': 'error',
            'warning': 'warning',
            'info': 'info'
        };
        
        return showToast(message, typeMap[type] || type);
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
        
        // Clean up performance data
        cleanupPerformanceData();
        
        // Reset state
        currentCveId = null;
        sortDirection = {};
        currentPage = 1;
        currentFilters = {};
        debounceTimers = {};
        eventListeners = [];
        isInitialized = false;
        virtualScrollEnabled = false;
    }

    // Cleanup on page unload
    window.addEventListener('beforeunload', cleanup);

    // Export functions for global access if needed
    window.VulnerabilitiesPage = {
        showAlert: showAlert,
        showToast: showToast,
        closeToast: closeToast,
        closeAllToasts: closeAllToasts,
        showLoading: showLoading,
        showTableLoading: showTableLoading,
        showSkeletonLoading: showSkeletonLoading,
        showButtonLoading: showButtonLoading,
        showProgressBar: showProgressBar,
        loadPage: loadPage,
        clearAllFilters: clearAllFilters,
        cleanup: cleanup
    };

})();