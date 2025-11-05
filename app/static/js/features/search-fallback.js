/**
 * Search Page Fallback Functionality
 * Basic functionality for when the main search.js fails to load
 */

console.log('Search fallback loaded');

// Basic form validation
function validateInput(value) {
    const ipRegex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    const domainRegex = /^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*)?$/;
    const urlRegex = /^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$/;
    
    return ipRegex.test(value) || domainRegex.test(value) || urlRegex.test(value);
}

// Basic toast notification
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show position-fixed`;
    toast.style.cssText = 'top: 20px; right: 20px; z-index: 1060; min-width: 300px;';
    
    toast.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 5000);
}

// Initialize basic functionality
document.addEventListener('DOMContentLoaded', function() {
    console.log('Search fallback initialized');
    
    const searchInput = document.getElementById('search-ip');
    const searchForm = document.getElementById('search-form');
    const clearBtn = document.getElementById('clear-form');
    
    // Basic input validation
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const value = this.value.trim();
            if (value === '') {
                this.classList.remove('is-valid', 'is-invalid');
            } else if (validateInput(value)) {
                this.classList.remove('is-invalid');
                this.classList.add('is-valid');
            } else {
                this.classList.remove('is-valid');
                this.classList.add('is-invalid');
            }
        });
    }
    
    // Form submission
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            const value = searchInput.value.trim();
            if (!validateInput(value)) {
                e.preventDefault();
                showToast('Por favor, digite um endereço IP, domínio ou URL válido.', 'error');
                return false;
            }
        });
    }
    
    // Clear button
    if (clearBtn) {
        clearBtn.addEventListener('click', function() {
            if (searchInput) {
                searchInput.value = '';
                searchInput.classList.remove('is-valid', 'is-invalid');
                searchInput.focus();
            }
        });
    }
    
    // Removido: handlers de exemplos rápidos (.example-btn)
});