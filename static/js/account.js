/**
 * Account Page JavaScript
 * Handles profile editing, password changes, and form interactions
 */

// DOM Elements
const profileForm = document.getElementById('profile-form');
const passwordForm = document.getElementById('password-form');
const resetBtn = document.getElementById('reset-btn');
const profilePictureInput = document.getElementById('profile_picture');
const profilePicturePreview = document.querySelector('.profile-picture img');

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeProfilePicture();
    initializeFormValidation();
    initializePasswordStrength();
    initializeFormReset();
    initializeTooltips();
});

/**
 * Initialize profile picture upload and preview
 */
function initializeProfilePicture() {
    if (profilePictureInput && profilePicturePreview) {
        profilePictureInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                // Validate file type
                const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif'];
                if (!allowedTypes.includes(file.type)) {
                    showAlert('Please select a valid image file (JPEG, PNG, or GIF)', 'error');
                    return;
                }
                
                // Validate file size (max 5MB)
                if (file.size > 5 * 1024 * 1024) {
                    showAlert('Image file size must be less than 5MB', 'error');
                    return;
                }
                
                // Preview the image
                const reader = new FileReader();
                reader.onload = function(e) {
                    profilePicturePreview.src = e.target.result;
                };
                reader.readAsDataURL(file);
            }
        });
    }
}

/**
 * Initialize form validation
 */
function initializeFormValidation() {
    // Bootstrap form validation
    const forms = document.querySelectorAll('.needs-validation');
    
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });
    
    // Custom email validation
    const emailInput = document.getElementById('email');
    if (emailInput) {
        emailInput.addEventListener('blur', function() {
            validateEmail(this.value);
        });
    }
    
    // Phone number formatting
    const phoneInput = document.getElementById('phone');
    if (phoneInput) {
        phoneInput.addEventListener('input', function() {
            formatPhoneNumber(this);
        });
    }
}

/**
 * Initialize password strength indicator
 */
function initializePasswordStrength() {
    const newPasswordInput = document.getElementById('new_password');
    if (newPasswordInput) {
        // Create password strength indicator
        const strengthIndicator = document.createElement('div');
        strengthIndicator.className = 'password-strength mt-2';
        strengthIndicator.innerHTML = `
            <div class="strength-bar">
                <div class="strength-fill"></div>
            </div>
            <div class="strength-text">Password strength: <span class="strength-level">Weak</span></div>
        `;
        newPasswordInput.parentNode.appendChild(strengthIndicator);
        
        newPasswordInput.addEventListener('input', function() {
            updatePasswordStrength(this.value, strengthIndicator);
        });
    }
}

/**
 * Initialize form reset functionality
 */
function initializeFormReset() {
    if (resetBtn) {
        resetBtn.addEventListener('click', function() {
            if (confirm('Are you sure you want to reset all changes?')) {
                // Reset profile form
                if (profileForm) {
                    profileForm.reset();
                    profileForm.classList.remove('was-validated');
                }
                
                // Reset profile picture preview
                if (profilePicturePreview) {
                    profilePicturePreview.src = profilePicturePreview.dataset.originalSrc || '/static/images/default-avatar.png';
                }
                
                showAlert('Form has been reset', 'info');
            }
        });
    }
}

/**
 * Initialize Bootstrap tooltips
 */
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * Validate email format
 */
function validateEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const emailInput = document.getElementById('email');
    
    if (email && !emailRegex.test(email)) {
        emailInput.setCustomValidity('Please enter a valid email address');
        emailInput.classList.add('is-invalid');
    } else {
        emailInput.setCustomValidity('');
        emailInput.classList.remove('is-invalid');
    }
}

/**
 * Format phone number input
 */
function formatPhoneNumber(input) {
    let value = input.value.replace(/\D/g, '');
    
    if (value.length >= 11) {
        value = value.replace(/(\d{2})(\d{2})(\d{5})(\d{4})/, '+$1 ($2) $3-$4');
    } else if (value.length >= 7) {
        value = value.replace(/(\d{2})(\d{2})(\d{4,5})/, '+$1 ($2) $3');
    } else if (value.length >= 4) {
        value = value.replace(/(\d{2})(\d{2})/, '+$1 ($2)');
    } else if (value.length >= 2) {
        value = value.replace(/(\d{2})/, '+$1');
    }
    
    input.value = value;
}

/**
 * Update password strength indicator
 */
function updatePasswordStrength(password, indicator) {
    const strengthFill = indicator.querySelector('.strength-fill');
    const strengthLevel = indicator.querySelector('.strength-level');
    
    let strength = 0;
    let level = 'Weak';
    let color = '#dc3545';
    
    // Check password criteria
    if (password.length >= 8) strength++;
    if (/[a-z]/.test(password)) strength++;
    if (/[A-Z]/.test(password)) strength++;
    if (/\d/.test(password)) strength++;
    if (/[^\w\s]/.test(password)) strength++;
    
    // Determine strength level
    switch (strength) {
        case 0:
        case 1:
            level = 'Very Weak';
            color = '#dc3545';
            break;
        case 2:
            level = 'Weak';
            color = '#fd7e14';
            break;
        case 3:
            level = 'Fair';
            color = '#ffc107';
            break;
        case 4:
            level = 'Good';
            color = '#20c997';
            break;
        case 5:
            level = 'Strong';
            color = '#198754';
            break;
    }
    
    // Update indicator
    strengthFill.style.width = `${(strength / 5) * 100}%`;
    strengthFill.style.backgroundColor = color;
    strengthLevel.textContent = level;
    strengthLevel.style.color = color;
}

/**
 * Show alert message
 */
function showAlert(message, type = 'info') {
    // Remove existing alerts
    const existingAlerts = document.querySelectorAll('.alert-custom');
    existingAlerts.forEach(alert => alert.remove());
    
    // Create new alert
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show alert-custom`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Insert alert at the top of the main content
    const mainContent = document.querySelector('.col-lg-9');
    if (mainContent) {
        mainContent.insertBefore(alertDiv, mainContent.firstChild);
    }
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (alertDiv && alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

/**
 * Handle AJAX form submission for profile updates
 */
function submitProfileForm(formData) {
    fetch('/account', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Profile updated successfully!', 'success');
        } else {
            showAlert(data.message || 'An error occurred while updating your profile', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('An error occurred while updating your profile', 'error');
    });
}

/**
 * Handle tab switching with URL hash
 */
function initializeTabSwitching() {
    // Handle hash changes
    window.addEventListener('hashchange', function() {
        const hash = window.location.hash;
        if (hash) {
            const tabButton = document.querySelector(`[data-bs-target="${hash}"]`);
            if (tabButton) {
                const tab = new bootstrap.Tab(tabButton);
                tab.show();
            }
        }
    });
    
    // Set initial tab based on hash
    const initialHash = window.location.hash;
    if (initialHash) {
        const tabButton = document.querySelector(`[data-bs-target="${initialHash}"]`);
        if (tabButton) {
            const tab = new bootstrap.Tab(tabButton);
            tab.show();
        }
    }
    
    // Update hash when tab changes
    const tabButtons = document.querySelectorAll('[data-bs-toggle="tab"]');
    tabButtons.forEach(button => {
        button.addEventListener('shown.bs.tab', function(e) {
            const target = e.target.getAttribute('data-bs-target');
            if (target) {
                window.location.hash = target;
            }
        });
    });
}

// Initialize tab switching
document.addEventListener('DOMContentLoaded', initializeTabSwitching);