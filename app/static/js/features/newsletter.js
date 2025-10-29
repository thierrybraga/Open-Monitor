/**
 * Newsletter JavaScript - Funcionalidades da página de newsletter
 * Tema minimalista e soft com validação e interações suaves
 */

class NewsletterManager {
  constructor() {
    this.form = null;
    this.submitBtn = null;
    this.resetBtn = null;
    this.successMessage = null;
    this.emailInput = null;
    this.emailToggle = null;
    this.toastContainer = null;
    
    this.init();
  }

  init() {
    // Aguarda o DOM estar pronto
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => this.setupElements());
    } else {
      this.setupElements();
    }
  }

  setupElements() {
    // Seleciona elementos do DOM
    this.form = document.getElementById('notification-form');
    this.submitBtn = document.getElementById('submit-btn');
    this.resetBtn = document.getElementById('reset-btn');
    this.successMessage = document.getElementById('success-message');
    this.emailInput = document.getElementById('email');
    this.emailToggle = document.getElementById('emailToggle');

    // Cria container para toasts se não existir
    this.createToastContainer();

    // Configura event listeners
    this.setupEventListeners();

    // Inicializa estado dos elementos
    this.initializeState();
  }

  createToastContainer() {
    if (!document.querySelector('.toast-container')) {
      const container = document.createElement('div');
      container.className = 'toast-container';
      container.style.cssText = `
        position: fixed;
        top: 1rem;
        right: 1rem;
        z-index: 1100;
        pointer-events: none;
      `;
      document.body.appendChild(container);
    }
    this.toastContainer = document.querySelector('.toast-container');
  }

  setupEventListeners() {
    if (!this.form) return;

    // Validação em tempo real do email
    if (this.emailInput) {
      this.emailInput.addEventListener('input', (e) => this.validateEmailRealTime(e));
      this.emailInput.addEventListener('blur', (e) => this.validateEmailOnBlur(e));
    }

    // Toggle do email
    if (this.emailToggle) {
      this.emailToggle.addEventListener('change', (e) => this.handleEmailToggle(e));
    }

    // Reset do formulário
    if (this.resetBtn) {
      this.resetBtn.addEventListener('click', (e) => this.handleReset(e));
    }

    // Submissão do formulário
    this.form.addEventListener('submit', (e) => this.handleSubmit(e));

    // Outros toggles (futuros)
    this.setupFutureToggles();
  }

  setupFutureToggles() {
    const toggles = ['telegramToggle', 'whatsappToggle', 'phoneToggle'];
    
    toggles.forEach(toggleId => {
      const toggle = document.getElementById(toggleId);
      if (toggle) {
        toggle.addEventListener('change', (e) => {
          const method = e.target.closest('.notification-method');
          if (method) {
            method.classList.toggle('enabled', e.target.checked);
          }
        });
      }
    });
  }

  initializeState() {
    // Inicializa estado do email toggle
    if (this.emailToggle && this.emailInput) {
      this.handleEmailToggle({ target: this.emailToggle });
    }
  }

  validateEmail(email) {
    return Utils.validateEmail(email);
  }

  validateEmailRealTime(event) {
    const email = event.target.value.trim();
    const isValid = email === '' || this.validateEmail(email);
    
    // Remove classes anteriores
    event.target.classList.remove('is-invalid', 'is-valid');
    
    // Adiciona classe apropriada
    if (email !== '') {
      event.target.classList.add(isValid ? 'is-valid' : 'is-invalid');
    }
    
    // Atualiza feedback
    this.updateEmailFeedback(event.target, isValid, email);
  }

  validateEmailOnBlur(event) {
    const email = event.target.value.trim();
    if (email && !this.validateEmail(email)) {
      this.showToast('Por favor, insira um email válido', 'warning');
    }
  }

  updateEmailFeedback(input, isValid, email) {
    const feedback = document.getElementById('email-feedback');
    if (!feedback) return;

    if (!isValid && email !== '') {
      feedback.textContent = 'Por favor, insira um endereço de email válido.';
      feedback.style.display = 'block';
    } else {
      feedback.style.display = 'none';
    }
  }

  handleEmailToggle(event) {
    const isChecked = event.target.checked;
    const method = this.emailInput?.closest('.notification-method');
    
    if (method) {
      method.classList.toggle('enabled', isChecked);
    }
    
    if (this.emailInput) {
      this.emailInput.required = isChecked;
      
      if (isChecked) {
        this.emailInput.focus();
        this.showToast('Email habilitado para notificações', 'info');
      } else {
        this.emailInput.classList.remove('is-invalid', 'is-valid');
        this.showToast('Email desabilitado', 'info');
      }
    }
  }

  handleReset(event) {
    event.preventDefault();
    
    // Reset do formulário
    if (this.form) {
      this.form.reset();
    }
    
    // Remove classes de validação
    document.querySelectorAll('.form-control').forEach(input => {
      input.classList.remove('is-valid', 'is-invalid');
    });
    
    // Remove estado enabled dos métodos
    document.querySelectorAll('.notification-method').forEach(method => {
      method.classList.remove('enabled');
    });
    
    // Esconde mensagem de sucesso
    if (this.successMessage) {
      this.successMessage.classList.add('d-none');
    }
    
    this.showToast('Formulário resetado com sucesso', 'info');
  }

  async handleSubmit(event) {
    event.preventDefault();
    
    // Valida formulário
    if (!this.validateForm()) {
      this.showToast('Por favor, corrija os erros antes de enviar', 'error');
      return;
    }
    
    // Mostra estado de carregamento
    this.setLoadingState(true);
    
    try {
      // Prepara dados do formulário
      const formData = new FormData(this.form);
      
      // Envia formulário
      const response = await fetch(this.form.action, {
        method: 'POST',
        body: formData,
        headers: {
          'X-Requested-With': 'XMLHttpRequest'
        }
      });
      
      const result = await response.json();
      
      if (response.ok && result.success) {
        this.handleSubmitSuccess(result);
      } else {
        this.handleSubmitError(result);
      }
      
    } catch (error) {
      console.error('Erro ao enviar formulário:', error);
      this.handleSubmitError({ message: 'Erro de conexão. Tente novamente.' });
    } finally {
      this.setLoadingState(false);
    }
  }

  validateForm() {
    let isValid = true;
    
    // Valida email se habilitado
    if (this.emailToggle?.checked) {
      const email = this.emailInput?.value.trim();
      if (!email || !this.validateEmail(email)) {
        this.emailInput?.classList.add('is-invalid');
        isValid = false;
      }
    }
    
    return isValid;
  }

  setLoadingState(loading) {
    if (!this.submitBtn) return;
    
    const btnText = this.submitBtn.querySelector('.btn-text');
    const btnLoading = this.submitBtn.querySelector('.btn-loading');
    
    if (loading) {
      btnText?.classList.add('d-none');
      btnLoading?.classList.remove('d-none');
      this.submitBtn.disabled = true;
    } else {
      btnText?.classList.remove('d-none');
      btnLoading?.classList.add('d-none');
      this.submitBtn.disabled = false;
    }
  }

  handleSubmitSuccess(result) {
    // Mostra mensagem de sucesso
    if (this.successMessage) {
      this.successMessage.classList.remove('d-none');
      
      // Esconde após 5 segundos
      setTimeout(() => {
        this.successMessage.classList.add('d-none');
      }, 5000);
    }
    
    this.showToast(result.message || 'Preferências de notificação salvas com sucesso!', 'success');
    
    // Opcional: redirecionar ou atualizar página
    if (result.redirect) {
      setTimeout(() => {
        window.location.href = result.redirect;
      }, 2000);
    }
  }

  handleSubmitError(result) {
    const message = result.message || 'Erro ao salvar preferências. Tente novamente.';
    this.showToast(message, 'error');
    
    // Mostra erros específicos dos campos
    if (result.errors) {
      Object.keys(result.errors).forEach(field => {
        const input = document.getElementById(field);
        if (input) {
          input.classList.add('is-invalid');
          const feedback = document.getElementById(`${field}-feedback`);
          if (feedback) {
            feedback.textContent = result.errors[field][0];
          }
        }
      });
    }
  }

  showToast(message, type = 'info', duration = 5000) {
    // Remove toasts existentes do mesmo tipo
    const existingToasts = this.toastContainer.querySelectorAll(`.toast-${type}`);
    existingToasts.forEach(toast => toast.remove());
    
    // Cria novo toast
    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    toast.style.pointerEvents = 'auto';
    
    // Ícones por tipo
    const icons = {
      success: 'bi-check-circle-fill',
      error: 'bi-x-circle-fill',
      warning: 'bi-exclamation-triangle-fill',
      info: 'bi-info-circle-fill'
    };
    
    toast.innerHTML = `
      <div class="d-flex align-items-center gap-2">
        <i class="bi ${icons[type]} flex-shrink-0"></i>
        <span class="flex-grow-1">${message}</span>
        <button type="button" class="btn-close btn-close-sm ms-2" aria-label="Fechar"></button>
      </div>
    `;
    
    // Adiciona ao container
    this.toastContainer.appendChild(toast);
    
    // Mostra toast com animação
    setTimeout(() => toast.classList.add('show'), 100);
    
    // Configura botão de fechar
    const closeBtn = toast.querySelector('.btn-close');
    closeBtn.addEventListener('click', () => this.hideToast(toast));
    
    // Remove automaticamente
    if (duration > 0) {
      setTimeout(() => this.hideToast(toast), duration);
    }
    
    return toast;
  }

  hideToast(toast) {
    toast.classList.remove('show');
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }

  // Método público para mostrar notificações
  static showNotification(message, type = 'info', duration = 5000) {
    if (window.newsletterManager) {
      return window.newsletterManager.showToast(message, type, duration);
    }
  }
}

// Inicializa o gerenciador quando o script carrega
window.newsletterManager = new NewsletterManager();

// Exporta para uso global
window.NewsletterManager = NewsletterManager;