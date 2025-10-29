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
    initializeAjaxSubmissions();
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
                    profilePicturePreview.src = profilePicturePreview.dataset.originalSrc || '/static/images/avatar-placeholder.svg';
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
    const tooltipEls = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    if (tooltipEls.length && window.bootstrap && bootstrap.Tooltip) {
        tooltipEls.forEach(el => {
            if (!bootstrap.Tooltip.getInstance(el)) {
                new bootstrap.Tooltip(el);
            }
        });
    }
}

/**
 * Validate email format
 */
function validateEmail(email) {
    const emailInput = document.getElementById('email');
    
    if (email && !Utils.validateEmail(email)) {
        emailInput.setCustomValidity('Please enter a valid email address');
        emailInput.classList.add('is-invalid');
    } else {
        emailInput.setCustomValidity('');
        emailInput.classList.remove('is-invalid');
    }
}

/**
 * Format Brazilian phone number input
 */
function formatPhoneNumber(input) {
    let value = input.value.replace(/\D/g, '');
    
    // Limita a 11 dígitos (DDD + 9 dígitos para celular)
    if (value.length > 11) {
        value = value.substring(0, 11);
    }
    
    // Aplica formatação baseada no comprimento
    if (value.length === 0) {
        input.value = '';
    } else if (value.length <= 2) {
        // Apenas DDD
        input.value = `(${value}`;
    } else if (value.length <= 6) {
        // DDD + primeiros dígitos
        input.value = `(${value.substring(0, 2)}) ${value.substring(2)}`;
    } else if (value.length <= 10) {
        // Telefone fixo: (XX) XXXX-XXXX
        input.value = `(${value.substring(0, 2)}) ${value.substring(2, 6)}-${value.substring(6)}`;
    } else {
        // Celular: (XX) 9XXXX-XXXX
        input.value = `(${value.substring(0, 2)}) ${value.substring(2, 7)}-${value.substring(7)}`;
    }
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
        headers: {
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        credentials: 'same-origin',
        body: formData
    })
    .then(async (response) => {
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            const data = await response.json();
            if (data.success) {
                showAlert('Profile updated successfully!', 'success');
            } else {
                showAlert(data.message || 'An error occurred while updating your profile', 'error');
            }
        } else if (response.redirected) {
            // Fallback: server responded with a redirect
            showAlert('Profile updated successfully!', 'success');
        } else {
            const text = await response.text();
            console.warn('Unexpected non-JSON response for profile update:', text);
            showAlert('Profile updated', 'info');
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

// --- Assets Tab Logic ---
(() => {
  const tbody = document.getElementById('asset-table-body');
  const pageInfo = document.getElementById('page-info');
  const pageSizeSel = document.getElementById('page-size');
  const prevBtn = document.getElementById('prev-page');
  const nextBtn = document.getElementById('next-page');
  const searchInput = document.getElementById('asset-search');
  const selectAllHeader = document.getElementById('select-all-header');
  const selectAllBtn = document.getElementById('select-all-btn');
  const deselectAllBtn = document.getElementById('deselect-all-btn');

  let state = {
    page: 1,
    perPage: pageSizeSel ? parseInt(pageSizeSel.value, 10) : 10,
    total: 0,
    pages: 1,
    items: [],
    filter: ''
  };

  function isAssetsTabActive() {
    const tabPane = document.getElementById('assets');
    return tabPane && tabPane.classList.contains('show') && tabPane.classList.contains('active');
  }

  async function loadAssets(page = 1) {
    if (!tbody) return;
    state.page = page;
    state.perPage = pageSizeSel ? parseInt(pageSizeSel.value, 10) : state.perPage;

    tbody.innerHTML = `<tr><td colspan="6" class="text-center p-4 text-muted">Loading assets...</td></tr>`;
    try {
      const url = `/api/v1/assets?page=${state.page}&per_page=${state.perPage}`;
      const res = await fetch(url, {
        headers: { 'Accept': 'application/json' },
        credentials: 'same-origin'
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const ct = res.headers.get('content-type') || '';
      const raw = await res.text();
      if (!ct.includes('application/json')) {
        throw new Error(`Resposta não-JSON recebida (content-type: ${ct}). Conteúdo: ${raw.substring(0, 120)}...`);
      }
      let json;
      const fallback = { data: [], meta: { page: 1, per_page: 0, total: 0, pages: 1 } };
      try {
        json = (raw && raw.trim()) ? JSON.parse(raw) : fallback;
      } catch (parseErr) {
        console.error('[account.js] JSON inválido recebido em /api/v1/assets:', parseErr, raw);
        // Em caso de corpo vazio ou malformado, utiliza fallback seguro ao invés de falhar
        json = fallback;
      }
      const assets = Array.isArray(json.data) ? json.data : [];
      const meta = json.meta || { page: 1, per_page: assets.length, total: assets.length, pages: 1 };
      state.items = assets;
      state.total = meta.total || assets.length;
      state.pages = meta.pages || 1;
      state.page = meta.page || page;

      renderAssets();
      updatePagination();
    } catch (err) {
      console.error('[account.js] Failed to load assets:', err);
      tbody.innerHTML = `<tr><td colspan="6" class="text-center p-4 text-danger">Falha ao carregar assets.</td></tr>`;
      showAlert('Não foi possível carregar os assets. Verifique sua sessão.', 'danger');
    }
  }

  function renderAssets() {
    if (!tbody) return;
    // Simple client-side filter by IP or Vendor name
    const filter = (searchInput?.value || '').trim().toLowerCase();
    const filtered = state.items.filter(a => {
      const ip = (a.ip_address || '').toLowerCase();
      const vendor = (a.vendor_name || '').toLowerCase();
      const name = (a.name || '').toLowerCase();
      if (!filter) return true;
      return ip.includes(filter) || vendor.includes(filter) || name.includes(filter);
    });

    if (!filtered.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center p-4 text-muted">Nenhum ativo encontrado.</td></tr>`;
      return;
    }

    const rows = filtered.map(a => {
      const ip = a.ip_address || '-';
      const vendor = a.vendor_name || '-';
      // Placeholders for fields not present in model
      const uptime = '-';
      const feature = '-';
      return `
        <tr data-asset-id="${a.id}">
          <td><input type="checkbox" class="row-select" aria-label="Selecionar ativo ${a.id}"></td>
          <td><code>${ip}</code></td>
          <td>${uptime}</td>
          <td>${vendor}</td>
          <td>${feature}</td>
          <td>
            <a href="/assets/${a.id}" class="btn btn-sm btn-outline-primary" title="Ver detalhes" aria-label="Ver detalhes">
              <i class="bi bi-eye"></i>
            </a>
          </td>
        </tr>
      `;
    }).join('');

    tbody.innerHTML = rows;
  }

  function updatePagination() {
    if (pageInfo) {
      pageInfo.textContent = `Page ${state.page} of ${state.pages}`;
    }
    if (prevBtn) prevBtn.disabled = state.page <= 1;
    if (nextBtn) nextBtn.disabled = state.page >= state.pages;
  }

  function bindEvents() {
    // Load assets when assets tab is shown
    const assetsTabBtn = document.getElementById('assets-tab');
    if (assetsTabBtn) {
      assetsTabBtn.addEventListener('shown.bs.tab', () => loadAssets(1));
    }

    // Initial load if already active
    document.addEventListener('DOMContentLoaded', () => {
      // Sempre tentar uma carga inicial; se a aba não estiver visível, os dados já
      // estarão prontos quando o usuário alternar para ela.
      loadAssets(1);
    });

    // Pagination controls
    if (prevBtn) prevBtn.addEventListener('click', () => { if (state.page > 1) loadAssets(state.page - 1); });
    if (nextBtn) nextBtn.addEventListener('click', () => { if (state.page < state.pages) loadAssets(state.page + 1); });
    if (pageSizeSel) pageSizeSel.addEventListener('change', () => loadAssets(1));

    // Filtering
    if (searchInput) searchInput.addEventListener('input', renderAssets);

    // Select all / deselect all
    function setAllSelections(checked) {
      const boxes = tbody?.querySelectorAll('.row-select');
      boxes?.forEach(b => { b.checked = checked; });
      toggleBulkActions();
    }
    function toggleBulkActions() {
      const anySelected = !!tbody?.querySelector('.row-select:checked');
      const delBtn = document.getElementById('delete-selected-btn');
      if (delBtn) delBtn.classList.toggle('d-none', !anySelected);
    }
    if (selectAllHeader) selectAllHeader.addEventListener('change', e => setAllSelections(e.target.checked));
    if (selectAllBtn) selectAllBtn.addEventListener('click', () => setAllSelections(true));
    if (deselectAllBtn) deselectAllBtn.addEventListener('click', () => setAllSelections(false));
    tbody?.addEventListener('change', e => { if (e.target.classList.contains('row-select')) toggleBulkActions(); });

    // Sorting on current page (simple)
    document.querySelectorAll('#assets .sortable').forEach(th => {
      th.addEventListener('click', () => {
        const key = th.dataset.sort;
        const mapping = { ip: 'ip_address', vendor: 'vendor_name', uptime: null };
        const field = mapping[key];
        if (!field) return; // skip uptime
        state.items.sort((a, b) => {
          const av = (a[field] || '').toString().toLowerCase();
          const bv = (b[field] || '').toString().toLowerCase();
          return av.localeCompare(bv);
        });
        renderAssets();
      });
    });
  }

  // Initialize bindings
  bindEvents();
})();

// --- Vendors Tab Logic ---
(() => {
  const listEl = document.getElementById('vendor-list');
  const searchEl = document.getElementById('vendor-search-input');
  const saveBtn = document.getElementById('save-vendor-preferences');
  const clearBtn = document.getElementById('clear-vendor-selection');
  const countEl = document.getElementById('vendor-selected-count');

  let allVendors = [];
  let selected = new Set();
  let initialized = false;

  async function fetchVendors() {
    const res = await fetch('/api/v1/vendors', { credentials: 'same-origin', headers: { 'Accept': 'application/json' } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.data || [];
  }
  async function fetchPrefs() {
    const res = await fetch('/api/v1/account/vendor-preferences', { credentials: 'same-origin', headers: { 'Accept': 'application/json' } });
    if (!res.ok) return [];
    const data = await res.json();
    const ids = Array.isArray(data.vendor_ids) ? data.vendor_ids : [];
    return ids;
  }
  function updateCount() {
    if (countEl) countEl.textContent = selected.size.toString();
  }
  function render() {
    if (!listEl) return;
    const filter = (searchEl?.value || '').trim().toLowerCase();
    const items = allVendors.filter(v => !filter || (v.name || '').toLowerCase().includes(filter));
    if (!items.length) {
      listEl.innerHTML = `<li class="list-group-item text-muted">No vendors found</li>`;
      updateCount();
      return;
    }
    listEl.innerHTML = items.map(v => {
      const checked = selected.has(Number(v.id)) ? 'checked' : '';
      const safeName = (v.name || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      return `
        <li class="list-group-item d-flex align-items-center justify-content-between">
          <div class="form-check">
            <input class="form-check-input vendor-check" type="checkbox" value="${v.id}" id="vendor-${v.id}" ${checked}>
            <label class="form-check-label" for="vendor-${v.id}">${safeName}</label>
          </div>
        </li>
      `;
    }).join('');
    updateCount();
  }
  function bind() {
    if (searchEl) searchEl.addEventListener('input', render);
    if (listEl) listEl.addEventListener('change', (e) => {
      const target = e.target;
      if (target && target.classList.contains('vendor-check')) {
        const id = parseInt(target.value, 10);
        if (target.checked) selected.add(id);
        else selected.delete(id);
        updateCount();
      }
    });
    if (clearBtn) clearBtn.addEventListener('click', () => {
      selected.clear();
      render();
    });
    if (saveBtn) saveBtn.addEventListener('click', async () => {
      try {
        const body = JSON.stringify({ vendor_ids: Array.from(selected) });
        const res = await fetch('/api/v1/account/vendor-preferences', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
          credentials: 'same-origin',
          body
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        showAlert('Vendor preferences saved', 'success');
      } catch (err) {
        console.error('[account.js] Save vendor preferences failed:', err);
        showAlert('Failed to save vendor preferences', 'danger');
      }
    });

    // Lazy init when the tab is shown
    const vendorsTabBtn = document.getElementById('vendors-tab');
    if (vendorsTabBtn) vendorsTabBtn.addEventListener('shown.bs.tab', init);

    // If the tab is already active on load, init immediately
    document.addEventListener('DOMContentLoaded', () => {
      const pane = document.getElementById('vendors');
      if (pane && pane.classList.contains('show') && pane.classList.contains('active')) {
        init();
      }
    });
  }
  async function init() {
    if (initialized) return;
    initialized = true;
    try {
      const [vendors, prefIds] = await Promise.all([fetchVendors(), fetchPrefs()]);
      allVendors = vendors;
      selected = new Set(prefIds.map(Number));
      render();
    } catch (err) {
      console.error('[account.js] Load vendors/prefs failed:', err);
      if (listEl) listEl.innerHTML = `<li class="list-group-item text-danger">Failed to load vendors</li>`;
    }
  }

  bind();
})();

function initializeAjaxSubmissions() {
  // Profile form AJAX submission
  if (profileForm) {
    profileForm.addEventListener('submit', function(event) {
      event.preventDefault();
      event.stopPropagation();
      // trigger validation
      const isValid = profileForm.checkValidity();
      profileForm.classList.add('was-validated');
      if (!isValid) {
        showAlert('Please fix validation errors in your profile.', 'warning');
        return;
      }
      const formData = new FormData(profileForm);
      submitProfileForm(formData);
    });
  }

  // Password form AJAX submission
  if (passwordForm) {
    passwordForm.addEventListener('submit', function(event) {
      event.preventDefault();
      event.stopPropagation();
      const isValid = passwordForm.checkValidity();
      passwordForm.classList.add('was-validated');
      if (!isValid) {
        showAlert('Please fix validation errors in your password form.', 'warning');
        return;
      }
      const formData = new FormData(passwordForm);
      submitPasswordForm(formData);
    });
  }
}

/**
 * Handle AJAX form submission for password changes
 */
function submitPasswordForm(formData) {
  fetch('/account', {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
      'X-Requested-With': 'XMLHttpRequest'
    },
    credentials: 'same-origin',
    body: formData
  })
  .then(async (response) => {
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const data = await response.json();
      if (data.success) {
        showAlert('Password changed successfully!', 'success');
        // Clear password fields for security
        try {
          passwordForm?.reset();
          passwordForm?.classList.remove('was-validated');
        } catch (_) {}
      } else {
        showAlert(data.message || 'An error occurred while changing your password', 'error');
      }
    } else if (response.redirected) {
      showAlert('Password changed successfully!', 'success');
      try {
        passwordForm?.reset();
        passwordForm?.classList.remove('was-validated');
      } catch (_) {}
    } else {
      const text = await response.text();
      console.warn('Unexpected non-JSON response for password change:', text);
      showAlert('Password updated', 'info');
    }
  })
  .catch(error => {
    console.error('Error:', error);
    showAlert('An error occurred while changing your password', 'error');
  });
}