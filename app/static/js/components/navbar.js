/**
 * NAVBAR - CONSOLIDATED JAVASCRIPT
 * Modern, Clean, Optimized Functionality
 * =====================================
 */

class NavbarManager {
  constructor() {
    this.elements = {};
    this.config = {
      refreshTimeout: 1000,
      syncUpdateInterval: 30000, // 30 seconds
      animationDuration: 300
    };
    
    this.init();
  }

  /**
   * Initialize navbar functionality
   */
  init() {
    this.cacheElements();
    this.validateElements();
    this.bindEvents();
    this.updateLastSyncTime();
  }

  /**
   * Cache DOM elements for better performance
   */
  cacheElements() {
    this.elements = {
      navbar: document.querySelector('header.navbar'),
      sidebarToggle: document.querySelector('.sidebar-toggle'),
      refreshButton: document.getElementById('refreshButton'),
      lastSyncTime: document.getElementById('lastSyncTime'),
      accountDropdown: document.getElementById('accountDropdown'),
      syncBadge: document.querySelector('.sync-badge')
    };

    // Validate critical elements
    this.validateElements();
  }

  /**
   * Validate that critical elements exist
   */
  validateElements() {
    const critical = ['navbar', 'refreshButton'];
    const missing = critical.filter(key => !this.elements[key]);
    
    if (missing.length > 0) {
      console.warn('NavbarManager: Missing critical elements:', missing);
    }
  }

  /**
   * Bind event listeners
   */
  bindEvents() {
    // Refresh button
    if (this.elements.refreshButton) {
      this.elements.refreshButton.addEventListener('click', (e) => {
        this.handleRefresh(e);
      });
    }

    // Sidebar toggle
    if (this.elements.sidebarToggle) {
      this.elements.sidebarToggle.addEventListener('click', (e) => {
        this.handleSidebarToggle(e);
      });
    }

    // Account dropdown
    if (this.elements.accountDropdown) {
      this.elements.accountDropdown.addEventListener('click', (e) => {
        this.handleAccountDropdown(e);
      });
    }

    // Sync badge hover effects
    if (this.elements.syncBadge) {
      this.elements.syncBadge.addEventListener('mouseenter', () => {
        this.handleSyncBadgeHover(true);
      });
      
      this.elements.syncBadge.addEventListener('mouseleave', () => {
        this.handleSyncBadgeHover(false);
      });
    }

    // Keyboard navigation
    this.bindKeyboardEvents();

    // Window events
    window.addEventListener('resize', () => {
      this.handleResize();
    });
  }

  /**
   * Handle refresh button click
   */
  async handleRefresh(event) {
    event.preventDefault();
    
    const button = this.elements.refreshButton;
    if (!button || button.classList.contains('refreshing')) {
      return;
    }

    try {
      // Add refreshing state
      button.classList.add('refreshing');
      button.disabled = true;

      // Simulate API call (replace with actual implementation)
      await this.performSync();

      // Update sync time
      this.updateLastSyncTime();

      // Show success feedback
      this.showSyncNotification('success', 'Dados atualizados com sucesso!');

    } catch (error) {
      console.error('Sync failed:', error);
      this.showSyncNotification('error', 'Erro ao atualizar dados');
    } finally {
      // Remove refreshing state
      setTimeout(() => {
        button.classList.remove('refreshing');
        button.disabled = false;
      }, this.config.refreshTimeout);
    }
  }

  /**
   * Handle sidebar toggle
   */
  handleSidebarToggle(event) {
    event.preventDefault();
    
    const sidebar = document.getElementById('sidebar');
    const toggle = this.elements.sidebarToggle;
    
    if (sidebar && toggle) {
      const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', !isExpanded);
      
      // Trigger Bootstrap offcanvas if available
      if (window.bootstrap && window.bootstrap.Offcanvas) {
        const offcanvas = window.bootstrap.Offcanvas.getOrCreateInstance(sidebar);
        offcanvas.toggle();
      }
    }
  }



  /**
   * Handle account dropdown
   */
  handleAccountDropdown(event) {
    // Bootstrap dropdown handles most of this
    // Add any custom logic here if needed
  }

  /**
   * Handle sync badge hover
   */
  handleSyncBadgeHover(isHovering) {
    const badge = this.elements.syncBadge;
    if (!badge) return;

    if (isHovering) {
      badge.style.transform = 'translateY(-1px)';
    } else {
      badge.style.transform = '';
    }
  }

  /**
   * Bind keyboard events for accessibility
   */
  bindKeyboardEvents() {
    document.addEventListener('keydown', (event) => {
      // Escape key to close dropdowns
      if (event.key === 'Escape') {
        this.closeAllDropdowns();
      }

      // Alt + R for refresh
      if (event.altKey && event.key === 'r') {
        event.preventDefault();
        if (this.elements.refreshButton) {
          this.elements.refreshButton.click();
        }
      }

      // Alt + M for menu toggle (mobile)
      if (event.altKey && event.key === 'm') {
        event.preventDefault();
        if (this.elements.sidebarToggle) {
          this.elements.sidebarToggle.click();
        }
      }
    });
  }

  /**
   * Handle window resize
   */
  handleResize() {
    // Debounce resize events
    clearTimeout(this.resizeTimeout);
    this.resizeTimeout = setTimeout(() => {
      this.updateResponsiveElements();
    }, 250);
  }

  /**
   * Update responsive elements based on screen size
   */
  updateResponsiveElements() {
    const isMobile = window.innerWidth < 768;
    const isTablet = window.innerWidth < 992;

    // Update sidebar toggle visibility
    if (this.elements.sidebarToggle) {
      this.elements.sidebarToggle.style.display = isMobile ? 'flex' : 'none';
    }

    // Update sync badge visibility - now handled by Bootstrap classes d-none d-lg-flex
    // Removing manual style override to let Bootstrap classes work properly
    if (this.elements.syncBadge) {
      // Clear any inline styles that might override Bootstrap classes
      this.elements.syncBadge.style.display = '';
    }
  }



  /**
   * Update last sync time display
   */
  async updateLastSyncTime() {
    if (!this.elements.lastSyncTime) return;

    try {
      // Buscar dados reais de sincronização da API
      const response = await fetch('/api/v1/sync/status');
      const data = await response.json();
      
      if (data.status === 'success') {
        // Atualizar texto do badge
        this.elements.lastSyncTime.textContent = data.last_sync_formatted;
        this.elements.lastSyncTime.setAttribute('datetime', data.last_sync_time);
        this.elements.lastSyncTime.setAttribute('title', `Última sincronização: ${data.message}`);
        
      } else if (data.status === 'never_synced') {
        this.elements.lastSyncTime.textContent = 'Nunca sincronizado';
        this.elements.lastSyncTime.setAttribute('title', 'Nenhuma sincronização encontrada');
        
      } else {
        // Fallback para erro
        this.elements.lastSyncTime.textContent = 'Erro ao carregar';
      }
      
    } catch (error) {
      console.warn('Erro ao buscar status de sincronização:', error);
      
      // Fallback para horário atual se a API falhar
      const now = new Date();
      const timeString = now.toLocaleTimeString('pt-BR', { 
        hour: '2-digit', 
        minute: '2-digit',
        hour12: false 
      });
      
      this.elements.lastSyncTime.textContent = timeString;
      this.elements.lastSyncTime.setAttribute('datetime', now.toISOString());
      this.elements.lastSyncTime.setAttribute('title', 'Horário atual (API indisponível)');
    }
  }



  /**
   * Start automatic sync time updates
   */
  startSyncTimer() {
    // Update every 30 seconds
    setInterval(() => {
      this.updateLastSyncTime();
    }, this.config.syncUpdateInterval);
  }

  /**
   * Perform sync operation - força sincronização com NVD
   */
  async performSync() {
    try {
      // Fazer requisição para forçar sincronização NVD
      const response = await fetch('/api/v1/sync/trigger', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCSRFToken()
        },
        body: JSON.stringify({
          full: false, // Sincronização incremental por padrão
          max_pages: null
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || `Erro HTTP: ${response.status}`);
      }

      // Log de sucesso
      console.log('Sincronização NVD iniciada:', data);
      
      // Aguardar um tempo mínimo para feedback visual
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      return data;
      
    } catch (error) {
      console.error('Erro na sincronização NVD:', error);
      throw error;
    }
  }

  /**
   * Obter token CSRF para requisições
   */
  getCSRFToken() {
    const token = document.querySelector('meta[name="csrf-token"]');
    return token ? token.getAttribute('content') : '';
  }

  /**
   * Show sync notification
   */
  showSyncNotification(type, message) {
    // Create notification element if it doesn't exist
    let notification = document.getElementById('sync-notification');
    
    if (!notification) {
      notification = document.createElement('div');
      notification.id = 'sync-notification';
      notification.className = 'sync-notification';
      document.body.appendChild(notification);
    }

    // Set notification content and type
    notification.innerHTML = `
      <i class="bi bi-${type === 'success' ? 'check-circle' : 'exclamation-triangle'}"></i>
      <span>${message}</span>
    `;
    
    notification.className = `sync-notification ${type}`;
    notification.classList.add('show');

    // Auto-hide after 3 seconds
    setTimeout(() => {
      notification.classList.remove('show');
    }, 3000);
  }



  /**
   * Close all open dropdowns
   */
  closeAllDropdowns() {
    const dropdowns = document.querySelectorAll('.dropdown-menu.show');
    dropdowns.forEach(dropdown => {
      const toggle = dropdown.previousElementSibling;
      if (toggle && window.bootstrap && window.bootstrap.Dropdown) {
        const bsDropdown = window.bootstrap.Dropdown.getInstance(toggle);
        if (bsDropdown) {
          bsDropdown.hide();
        }
      }
    });
  }

  /**
   * Add ripple effect to buttons
   */
  addRippleEffect(button, event) {
    const ripple = document.createElement('span');
    const rect = button.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const x = event.clientX - rect.left - size / 2;
    const y = event.clientY - rect.top - size / 2;

    ripple.style.cssText = `
      position: absolute;
      width: ${size}px;
      height: ${size}px;
      left: ${x}px;
      top: ${y}px;
      background: rgba(255, 255, 255, 0.5);
      border-radius: 50%;
      transform: scale(0);
      animation: ripple 0.6s linear;
      pointer-events: none;
    `;

    button.appendChild(ripple);

    setTimeout(() => {
      ripple.remove();
    }, 600);
  }

  /**
   * Destroy navbar manager
   */
  destroy() {
    // Clear timers
    if (this.resizeTimeout) {
      clearTimeout(this.resizeTimeout);
    }

    // Remove event listeners
    Object.values(this.elements).forEach(element => {
      if (element && element.removeEventListener) {
        element.removeEventListener('click', this.handleRefresh);
        element.removeEventListener('click', this.handleSidebarToggle);
        element.removeEventListener('click', this.handleThemeToggle);
      }
    });

    // Clear elements cache
    this.elements = {};
  }
}

// CSS for notifications (injected dynamically)
const notificationCSS = `
.sync-notification {
  position: fixed;
  bottom: 1rem;
  right: 1rem;
  background: var(--navbar-bg);
  backdrop-filter: var(--navbar-backdrop-filter);
  -webkit-backdrop-filter: var(--navbar-backdrop-filter);
  border: 1px solid var(--navbar-border);
  border-radius: 12px;
  padding: 0.75rem 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  transform: translateY(100px);
  opacity: 0;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1040;
  max-width: 300px;
}

.sync-notification.show {
  transform: translateY(0);
  opacity: 1;
}

.sync-notification.success {
  border-left: 4px solid var(--status-success);
}

.sync-notification.error {
  border-left: 4px solid var(--status-danger);
}

.sync-notification i {
  font-size: 1rem;
}

.sync-notification.success i {
  color: var(--status-success);
}

.sync-notification.error i {
  color: var(--status-danger);
}

@keyframes ripple {
  to {
    transform: scale(4);
    opacity: 0;
  }
}
`;

// Inject notification CSS
const style = document.createElement('style');
style.textContent = notificationCSS;
document.head.appendChild(style);

// Initialize navbar manager when DOM is ready
let navbarManager;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    navbarManager = new NavbarManager();
  });
} else {
  navbarManager = new NavbarManager();
}

// Export for global access
window.navbarManager = navbarManager;

// Export class for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = NavbarManager;
}