/**
 * Loading Manager
 * Global JavaScript for managing loading states and feedback
 */

class LoadingManager {
    constructor() {
        this.init();
    }

    init() {
        this.setupFormSubmissions();
        this.setupButtonLoading();
        this.setupProgressIndicator();
        this.setupToastNotifications();
    }

    /**
     * Setup automatic loading states for form submissions
     */
    setupFormSubmissions() {
        document.addEventListener('submit', (e) => {
            const form = e.target;
            if (form.tagName === 'FORM') {
                const submitBtn = form.querySelector('button[type="submit"]');
                if (submitBtn && !submitBtn.disabled) {
                    this.setButtonLoading(submitBtn, true);
                }
            }
        });
    }

    /**
     * Setup loading states for buttons with data attributes
     */
    setupButtonLoading() {
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('button');
            if (btn && btn.hasAttribute('data-loading')) {
                const loadingText = btn.getAttribute('data-loading');
                this.setButtonLoading(btn, true, loadingText);
            }
        });
    }

    /**
     * Set button loading state
     * @param {HTMLElement} button - The button element
     * @param {boolean} loading - Whether to show loading state
     * @param {string} loadingText - Optional loading text
     */
    setButtonLoading(button, loading, loadingText = null) {
        if (!button) return;

        const btnText = button.querySelector('.btn-text');
        const btnLoading = button.querySelector('.btn-loading');

        if (loading) {
            button.disabled = true;
            button.classList.add('loading');
            
            if (btnText) btnText.classList.add('d-none');
            if (btnLoading) {
                btnLoading.classList.remove('d-none');
                if (loadingText) {
                    const textElement = btnLoading.querySelector('span:not(.spinner-border-sm)');
                    if (textElement) textElement.textContent = loadingText;
                }
            }
        } else {
            button.disabled = false;
            button.classList.remove('loading');
            
            if (btnText) btnText.classList.remove('d-none');
            if (btnLoading) btnLoading.classList.add('d-none');
        }
    }

    /**
     * Set form loading state
     * @param {HTMLElement} form - The form element
     * @param {boolean} loading - Whether to show loading state
     */
    setFormLoading(form, loading) {
        if (!form) return;

        if (loading) {
            form.classList.add('form-loading');
            const inputs = form.querySelectorAll('input, select, textarea, button');
            inputs.forEach(input => input.disabled = true);
        } else {
            form.classList.remove('form-loading');
            const inputs = form.querySelectorAll('input, select, textarea, button');
            inputs.forEach(input => input.disabled = false);
        }
    }

    /**
     * Set card loading state
     * @param {HTMLElement} card - The card element
     * @param {boolean} loading - Whether to show loading state
     */
    setCardLoading(card, loading) {
        if (!card) return;

        if (loading) {
            card.classList.add('loading');
        } else {
            card.classList.remove('loading');
        }
    }

    /**
     * Setup progress indicator
     */
    setupProgressIndicator() {
        // Create progress indicator if it doesn't exist
        if (!document.querySelector('.progress-indicator')) {
            const progressIndicator = document.createElement('div');
            progressIndicator.className = 'progress-indicator';
            progressIndicator.innerHTML = '<div class="progress-bar"></div>';
            document.body.appendChild(progressIndicator);
        }
    }

    /**
     * Show/hide progress indicator
     * @param {boolean} show - Whether to show the progress indicator
     * @param {number} progress - Progress percentage (0-100)
     */
    setProgress(show, progress = 0) {
        const indicator = document.querySelector('.progress-indicator');
        const bar = indicator?.querySelector('.progress-bar');
        
        if (!indicator || !bar) return;

        if (show) {
            indicator.style.display = 'block';
            bar.style.width = `${Math.min(100, Math.max(0, progress))}%`;
        } else {
            indicator.style.display = 'none';
            bar.style.width = '0%';
        }
    }

    /**
     * Simulate progress for indeterminate operations
     * @param {number} duration - Duration in milliseconds
     */
    simulateProgress(duration = 3000) {
        this.setProgress(true, 0);
        
        let progress = 0;
        const interval = 50;
        const increment = (100 / duration) * interval;
        
        const timer = setInterval(() => {
            progress += increment;
            if (progress >= 90) {
                clearInterval(timer);
                this.setProgress(true, 90);
            } else {
                this.setProgress(true, progress);
            }
        }, interval);
        
        return timer;
    }

    /**
     * Complete progress animation
     */
    completeProgress() {
        this.setProgress(true, 100);
        setTimeout(() => {
            this.setProgress(false);
        }, 300);
    }

    /**
     * Setup toast notifications
     */
    setupToastNotifications() {
        // Auto-hide toasts after 5 seconds
        document.addEventListener('DOMContentLoaded', () => {
            const toasts = document.querySelectorAll('.toast');
            toasts.forEach(toast => {
                if (!toast.hasAttribute('data-bs-autohide')) {
                    toast.setAttribute('data-bs-autohide', 'true');
                    toast.setAttribute('data-bs-delay', '5000');
                }
            });
        });
    }

    /**
     * Show toast notification
     * @param {string} message - Toast message
     * @param {string} type - Toast type (success, error, warning, info)
     * @param {number} duration - Duration in milliseconds
     */
    showToast(message, type = 'info', duration = 5000) {
        const toastContainer = document.querySelector('.toast-container') || this.createToastContainer();
        
        const toastId = 'toast-' + Date.now();
        const iconMap = {
            success: 'bi-check-circle',
            error: 'bi-exclamation-triangle',
            warning: 'bi-exclamation-triangle',
            info: 'bi-info-circle'
        };
        
        const colorMap = {
            success: 'text-success',
            error: 'text-danger',
            warning: 'text-warning',
            info: 'text-primary'
        };
        
        const toastHTML = `
            <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true" data-bs-autohide="true" data-bs-delay="${duration}">
                <div class="toast-header">
                    <i class="bi ${iconMap[type]} ${colorMap[type]} me-2"></i>
                    <strong class="me-auto">${type.charAt(0).toUpperCase() + type.slice(1)}</strong>
                    <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        `;
        
        toastContainer.insertAdjacentHTML('beforeend', toastHTML);
        
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement);
        toast.show();
        
        // Remove toast element after it's hidden
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
        
        return toast;
    }

    /**
     * Create toast container if it doesn't exist
     */
    createToastContainer() {
        const container = document.createElement('div');
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1055';
        document.body.appendChild(container);
        return container;
    }

    /**
     * Create skeleton loader
     * @param {HTMLElement} element - Element to apply skeleton to
     * @param {number} lines - Number of skeleton lines
     */
    createSkeleton(element, lines = 3) {
        if (!element) return;
        
        const skeletonHTML = Array(lines).fill(0).map((_, i) => 
            `<div class="skeleton mb-2" style="height: 1rem; width: ${Math.random() * 40 + 60}%; border-radius: 0.25rem;"></div>`
        ).join('');
        
        element.innerHTML = skeletonHTML;
        element.classList.add('loading');
    }

    /**
     * Remove skeleton loader
     * @param {HTMLElement} element - Element to remove skeleton from
     * @param {string} originalContent - Original content to restore
     */
    removeSkeleton(element, originalContent = '') {
        if (!element) return;
        
        element.classList.remove('loading');
        element.innerHTML = originalContent;
    }

    /**
     * Debounce function for performance
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in milliseconds
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
     * Handle AJAX requests with loading states
     * @param {string} url - Request URL
     * @param {Object} options - Fetch options
     * @param {HTMLElement} loadingElement - Element to show loading state
     */
    async fetchWithLoading(url, options = {}, loadingElement = null) {
        try {
            if (loadingElement) {
                if (loadingElement.tagName === 'BUTTON') {
                    this.setButtonLoading(loadingElement, true);
                } else {
                    this.setCardLoading(loadingElement, true);
                }
            }
            
            this.setProgress(true, 10);
            
            const response = await fetch(url, options);
            
            this.setProgress(true, 70);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            this.completeProgress();
            
            return data;
        } catch (error) {
            this.setProgress(false);
            this.showToast(`Error: ${error.message}`, 'error');
            throw error;
        } finally {
            if (loadingElement) {
                if (loadingElement.tagName === 'BUTTON') {
                    this.setButtonLoading(loadingElement, false);
                } else {
                    this.setCardLoading(loadingElement, false);
                }
            }
        }
    }
}

// Initialize loading manager when DOM is ready
let loadingManager;
document.addEventListener('DOMContentLoaded', () => {
    loadingManager = new LoadingManager();
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LoadingManager;
} else if (typeof window !== 'undefined') {
    window.LoadingManager = LoadingManager;
    window.loadingManager = loadingManager;
}