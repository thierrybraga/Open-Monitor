// Evitar múltiplos carregamentos do script
if (window.__AUTH_JS_LOADED__) {
    console.warn('Auth page script already loaded, skipping re-init');
} else {
    window.__AUTH_JS_LOADED__ = true;
// ========================================
// Funcionalidades de Autenticação Modernas
// ========================================

// Configuração de alternância de visibilidade da senha
function setupPasswordToggle() {
    // Toggle para campo de senha principal
    const togglePassword = document.getElementById('togglePassword');
    const passwordField = document.getElementById('password');
    const passwordIcon = document.getElementById('togglePasswordIcon');
    
    if (togglePassword && passwordField && passwordIcon) {
        togglePassword.addEventListener('click', function() {
            const type = passwordField.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordField.setAttribute('type', type);
            
            if (type === 'text') {
                passwordIcon.classList.remove('bi-eye');
                passwordIcon.classList.add('bi-eye-slash');
            } else {
                passwordIcon.classList.remove('bi-eye-slash');
                passwordIcon.classList.add('bi-eye');
            }
        });
    }
    
    // Toggle para campo de confirmação de senha
    const toggleConfirmPassword = document.getElementById('toggleConfirmPassword');
    const confirmPasswordField = document.getElementById('confirm_password');
    const confirmPasswordIcon = document.getElementById('toggleConfirmPasswordIcon');
    
    if (toggleConfirmPassword && confirmPasswordField && confirmPasswordIcon) {
        toggleConfirmPassword.addEventListener('click', function() {
            const type = confirmPasswordField.getAttribute('type') === 'password' ? 'text' : 'password';
            confirmPasswordField.setAttribute('type', type);
            
            if (type === 'text') {
                confirmPasswordIcon.classList.remove('bi-eye');
                confirmPasswordIcon.classList.add('bi-eye-slash');
            } else {
                confirmPasswordIcon.classList.remove('bi-eye-slash');
                confirmPasswordIcon.classList.add('bi-eye');
            }
        });
    }
}

// Função global para alternar visibilidade da senha usada pelo template
function togglePassword(fieldId) {
    const field = document.getElementById(fieldId);
    if (!field) return;

    const eyeId = fieldId === 'password' ? 'password-eye' : `${fieldId}-eye`;
    const eyeIcon = document.getElementById(eyeId);
    const newType = field.getAttribute('type') === 'password' ? 'text' : 'password';
    field.setAttribute('type', newType);

    if (eyeIcon) {
        if (newType === 'text') {
            eyeIcon.classList.remove('bi-eye');
            eyeIcon.classList.add('bi-eye-slash');
        } else {
            eyeIcon.classList.remove('bi-eye-slash');
            eyeIcon.classList.add('bi-eye');
        }
    }
}

// Verificação da força da senha aprimorada
function checkPasswordStrength() {
    const passwordField = document.getElementById('password');
    const strengthFill = document.getElementById('passwordStrengthFill');
    const strengthText = document.getElementById('passwordStrengthText');
    
    if (!passwordField || !strengthFill || !strengthText) return;
    
    const password = passwordField.value;
    let strength = 0;
    let feedback = '';
    let color = '';
    let gradient = '';
    
    if (password.length === 0) {
        strengthText.textContent = 'Digite uma senha';
        strengthFill.style.width = '0%';
        strengthFill.style.background = '';
        strengthText.style.color = 'var(--text-muted)';
        return;
    }
    
    // Critérios de força aprimorados
    if (password.length >= 8) strength++;
    if (password.match(/[a-z]/)) strength++;
    if (password.match(/[A-Z]/)) strength++;
    if (password.match(/[0-9]/)) strength++;
    if (password.match(/[^a-zA-Z0-9]/)) strength++;
    
    // Bônus para senhas mais longas
    if (password.length >= 12) strength += 0.5;
    if (password.length >= 16) strength += 0.5;
    
    // Aplica cores e gradientes modernos baseado na força
    switch (Math.floor(strength)) {
        case 0:
        case 1:
            feedback = '🔴 Muito fraca';
            color = '#ef4444';
            gradient = 'linear-gradient(90deg, #ef4444, #dc2626)';
            strengthFill.style.width = '20%';
            break;
        case 2:
            feedback = '🟡 Fraca';
            color = '#f59e0b';
            gradient = 'linear-gradient(90deg, #f59e0b, #d97706)';
            strengthFill.style.width = '40%';
            break;
        case 3:
            feedback = '🟠 Boa';
            color = '#3b82f6';
            gradient = 'linear-gradient(90deg, #3b82f6, #2563eb)';
            strengthFill.style.width = '60%';
            break;
        case 4:
            feedback = '🟢 Forte';
            color = '#10b981';
            gradient = 'linear-gradient(90deg, #10b981, #059669)';
            strengthFill.style.width = '80%';
            break;
        case 5:
        default:
            feedback = '🔒 Muito forte';
            color = '#10b981';
            gradient = 'linear-gradient(90deg, #10b981, #047857, #065f46)';
            strengthFill.style.width = '100%';
            break;
    }
    
    // Aplica o gradiente e animação
    strengthFill.style.background = gradient;
    strengthText.textContent = feedback;
    strengthText.style.color = color;
    
    // Adiciona classe para animação
    strengthFill.classList.add('password-strength-fill');
    
    // Também verifica se as senhas coincidem
    checkPasswordMatch();
}

// Verificação de correspondência de senhas aprimorada
function checkPasswordMatch() {
    const password = document.getElementById('password');
    const confirmPassword = document.getElementById('confirm_password');
    const matchDiv = document.getElementById('passwordMatch');
    const mismatchDiv = document.getElementById('passwordMismatch');
    
    if (!password || !confirmPassword) return;
    
    // Limpa estados anteriores
    if (matchDiv) matchDiv.style.display = 'none';
    if (mismatchDiv) mismatchDiv.style.display = 'none';
    
    if (confirmPassword.value === '') {
        confirmPassword.classList.remove('is-valid', 'is-invalid');
        return;
    }
    
    if (password.value === confirmPassword.value && password.value !== '') {
        // Senhas coincidem
        if (matchDiv) {
            matchDiv.style.display = 'block';
            matchDiv.textContent = '✓ As senhas coincidem';
            matchDiv.className = 'password-match';
        }
        confirmPassword.classList.remove('is-invalid');
        confirmPassword.classList.add('is-valid');
        
        // Adiciona animação de sucesso
        addElementAnimation(confirmPassword, 'pulse-success');
    } else {
        // Senhas não coincidem
        if (mismatchDiv) {
            mismatchDiv.style.display = 'block';
            mismatchDiv.textContent = '⚠ As senhas não coincidem';
            mismatchDiv.className = 'password-mismatch';
        }
        confirmPassword.classList.remove('is-valid');
        confirmPassword.classList.add('is-invalid');
        
        // Adiciona animação de erro
        addElementAnimation(confirmPassword, 'shake');
    }
}

// Validação em tempo real dos campos
function setupRealTimeValidation() {
    const inputs = document.querySelectorAll('.form-control');
    
    inputs.forEach(input => {
        input.addEventListener('blur', function() {
            Utils.validateField(this);
        });
        
        input.addEventListener('input', function() {
            // Remove estado de erro ao digitar
            this.classList.remove('is-invalid');
            const feedback = this.parentNode.querySelector('.invalid-feedback');
            if (feedback) {
                feedback.style.display = 'none';
            }
            clearAvailabilityFeedback(this);
        });
    });
    
    // Configurar verificação de disponibilidade para username e email
    const usernameField = document.querySelector('input[name="username"]');
    const emailField = document.querySelector('input[name="email"]');
    
    if (usernameField) {
        usernameField.addEventListener('input', () => {
            clearAvailabilityFeedback(usernameField);
            checkAvailability(usernameField, 'username');
        });
    }
    
    if (emailField) {
        emailField.addEventListener('input', () => {
            clearAvailabilityFeedback(emailField);
            checkAvailability(emailField, 'email');
        });
    }
}

// Validação individual de campo
function validateField(field) {
    const value = field.value.trim();
    let isValid = true;
    let message = '';
    
    // Validação por tipo de campo
    switch (field.type) {
        case 'email':
            // Validação mais robusta de email
            const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
            if (!emailRegex.test(value)) {
                isValid = false;
                message = 'Digite um e-mail válido (exemplo: usuario@dominio.com)';
            } else {
                // Verificações adicionais para emails válidos
                if (value.length > 255) {
                    isValid = false;
                    message = 'E-mail muito longo (máximo 255 caracteres)';
                } else if (value.includes('..') || value.startsWith('.') || value.endsWith('.')) {
                    isValid = false;
                    message = 'Formato de e-mail inválido';
                }
            }
            break;
            
        case 'password':
            if (value.length < 8) {
                isValid = false;
                message = 'A senha deve ter pelo menos 8 caracteres';
            }
            break;
            
        default:
            if (field.hasAttribute('required') && value === '') {
                isValid = false;
                message = 'Este campo é obrigatório';
            }
    }
    
    // Aplica o estado visual
    if (isValid) {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
        clearFieldError(field);
    } else {
        field.classList.remove('is-valid');
        field.classList.add('is-invalid');
        showFieldError(field, message);
    }
    
    return isValid;
}

// Exibe erro no campo com melhor UX
function showFieldError(field, message) {
    let feedback = field.parentNode.querySelector('.invalid-feedback');
    
    if (!feedback) {
        feedback = document.createElement('div');
        feedback.className = 'invalid-feedback';
        feedback.setAttribute('aria-live', 'assertive');
        feedback.setAttribute('aria-atomic', 'true');
        field.parentNode.appendChild(feedback);
    }
    
    feedback.textContent = message;
    feedback.style.display = 'block';
    
    // Adiciona animação suave ao feedback
    feedback.classList.add('fade-in');
    
    // Atualizar acessibilidade
    if (typeof updateAriaInvalid === 'function') {
        updateAriaInvalid(field, false);
    }
}

// Remove erro do campo
function clearFieldError(field) {
    const feedback = field.parentNode.querySelector('.invalid-feedback');
    if (feedback) {
        feedback.style.display = 'none';
        feedback.classList.remove('fade-in');
    }
    
    // Atualizar acessibilidade
    if (typeof updateAriaInvalid === 'function') {
        updateAriaInvalid(field, true);
    }
}

// Verifica disponibilidade de username/email em tempo real
window.authAvailabilityTimeout = window.authAvailabilityTimeout || null;
function checkAvailability(field, type) {
    const value = field.value.trim();
    
    // Limpar timeout anterior
    if (window.authAvailabilityTimeout) {
        clearTimeout(window.authAvailabilityTimeout);
    }
    
    // Remove loading anterior
    hideFieldLoading(field);
    
    // Se campo estiver vazio, não verificar
    if (!value) {
        clearAvailabilityFeedback(field);
        return;
    }
    
    // Mostra loading imediatamente
    showFieldLoading(field, 'Verificando...');
    
    // Debounce - aguardar 500ms após parar de digitar
    window.authAvailabilityTimeout = setTimeout(async () => {
        try {
            const response = await fetch('/auth/check-availability', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    type: type,
                    value: value
                })
            });
            
            const data = await response.json();
            
            // Remove loading
            hideFieldLoading(field);
            
            if (response.ok) {
                // Mostrar feedback de disponibilidade
                showAvailabilityFeedback(field, data.available, data.message);
            } else {
                console.error('Erro ao verificar disponibilidade:', data.error);
                showAvailabilityFeedback(field, false, 'Erro ao verificar disponibilidade');
            }
        } catch (error) {
            console.error('Erro na requisição:', error);
            hideFieldLoading(field);
            showAvailabilityFeedback(field, false, 'Erro de conexão');
        }
    }, 800);
}

// Mostra feedback de disponibilidade
function showAvailabilityFeedback(field, available, message) {
    let feedback = field.parentNode.querySelector('.availability-feedback');
    
    if (!feedback) {
        feedback = document.createElement('div');
        feedback.className = 'availability-feedback';
        field.parentNode.appendChild(feedback);
    }
    
    feedback.textContent = message;
    feedback.className = `availability-feedback ${available ? 'text-success' : 'text-warning'}`;
    feedback.style.display = 'block';
    feedback.classList.add('fade-in');
    
    // Se não disponível, adicionar classe de erro ao campo
    if (!available) {
        field.classList.add('is-invalid');
        field.classList.remove('is-valid');
    }
}

// Remove feedback de disponibilidade
function clearAvailabilityFeedback(field) {
    const feedback = field.parentNode.querySelector('.availability-feedback');
    if (feedback) {
        feedback.style.display = 'none';
        feedback.classList.remove('fade-in');
    }
}

// Mostra erro de campo
function showFieldError(field, message) {
    field.classList.add('is-invalid');
    field.classList.remove('is-valid');
    
    let feedback = field.parentNode.querySelector('.invalid-feedback');
    if (!feedback) {
        feedback = document.createElement('div');
        feedback.className = 'invalid-feedback';
        field.parentNode.appendChild(feedback);
    }
    
    feedback.textContent = message;
    feedback.style.display = 'block';
}

// Remove erro de campo
function clearFieldError(field) {
    field.classList.remove('is-invalid');
    const feedback = field.parentNode.querySelector('.invalid-feedback');
    if (feedback) {
        feedback.style.display = 'none';
    }
}

// Função para adicionar animações aos elementos
function addElementAnimation(element, animationClass = 'fade-in') {
    if (element) {
        element.classList.add(animationClass);
    }
}

// Validação do formulário antes do envio
function validateForm(form) {
    const inputs = form.querySelectorAll('.form-control[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!validateField(input)) {
            isValid = false;
        }
    });
    
    // Validação específica para confirmação de senha
    const password = form.querySelector('#password');
    const confirmPassword = form.querySelector('#confirm_password');
    
    if (password && confirmPassword && password.value !== confirmPassword.value) {
        showFieldError(confirmPassword, 'As senhas não coincidem');
        confirmPassword.classList.add('is-invalid');
        isValid = false;
    }
    
    return isValid;
}

// Configuração de loading do botão de envio
function setupSubmitButton() {
    const authForms = document.querySelectorAll('.auth-form');
    
    authForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitButton = form.querySelector('.auth-submit-btn');
            if (!submitButton) return;
            
            // Valida o formulário antes do envio
            if (!validateForm(form)) {
                e.preventDefault();
                return;
            }
            
            // Mostra overlay de loading
            showLoadingOverlay(form);
            
            // Mostra estado de loading no botão
            const btnText = submitButton.querySelector('.btn-text');
            const btnLoading = submitButton.querySelector('.btn-loading');
            
            if (btnText && btnLoading) {
                btnText.style.display = 'none';
                btnLoading.style.display = 'inline-flex';
                submitButton.disabled = true;
                
                // Atualizar estados de acessibilidade
                if (typeof updateButtonAriaStates === 'function') {
                    updateButtonAriaStates(submitButton, true, true);
                }
            }
            
            // Simula progresso de envio
            simulateFormProgress();
        });
    });
}

// Mostra overlay de loading
function showLoadingOverlay(form, message = 'Processando...') {
    let overlay = form.querySelector('.loading-overlay');
    
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'loading-overlay';
        overlay.innerHTML = `
            <div class="loading-spinner"></div>
            <div class="loading-text">${message}</div>
            <div class="progress-container">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 0%"></div>
                </div>
                <div class="progress-text">0%</div>
            </div>
        `;
        form.style.position = 'relative';
        form.appendChild(overlay);
    }
    
    overlay.classList.add('active');
    return overlay;
}

// Remove overlay de loading
function hideLoadingOverlay(form) {
    const overlay = form.querySelector('.loading-overlay');
    if (overlay) {
        overlay.classList.remove('active');
        setTimeout(() => {
            if (overlay.parentElement) {
                overlay.remove();
            }
        }, 400);
    }
}

// Simula progresso do formulário
function simulateFormProgress() {
    const progressFill = document.querySelector('.progress-fill');
    const progressText = document.querySelector('.progress-text');
    const loadingText = document.querySelector('.loading-text');
    
    if (!progressFill || !progressText) return;
    
    let progress = 0;
    const steps = [
        { progress: 20, message: 'Validando dados...' },
        { progress: 40, message: 'Verificando disponibilidade...' },
        { progress: 60, message: 'Processando informações...' },
        { progress: 80, message: 'Finalizando...' },
        { progress: 100, message: 'Concluído!' }
    ];
    
    let currentStep = 0;
    
    const updateProgress = () => {
        if (currentStep < steps.length) {
            const step = steps[currentStep];
            progress = step.progress;
            
            progressFill.style.width = `${progress}%`;
            progressText.textContent = `${progress}%`;
            
            if (loadingText) {
                loadingText.textContent = step.message;
            }
            
            currentStep++;
            
            // Intervalo variável para simular processamento real
            const delay = currentStep === 1 ? 800 : currentStep === steps.length ? 500 : 600;
            setTimeout(updateProgress, delay);
        }
    };
    
    // Inicia após um pequeno delay
    setTimeout(updateProgress, 300);
}

// Atualiza progresso manualmente
function updateProgress(percentage, message = '') {
    const progressFill = document.querySelector('.progress-fill');
    const progressText = document.querySelector('.progress-text');
    const loadingText = document.querySelector('.loading-text');
    
    if (progressFill) {
        progressFill.style.width = `${percentage}%`;
    }
    
    if (progressText) {
        progressText.textContent = `${percentage}%`;
    }
    
    if (loadingText && message) {
        loadingText.textContent = message;
    }
}

// Mostra loading em campos específicos
function showFieldLoading(field, message = 'Verificando...') {
    const parent = field.parentElement;
    let loadingIndicator = parent.querySelector('.field-loading');
    
    if (!loadingIndicator) {
        loadingIndicator = document.createElement('div');
        loadingIndicator.className = 'field-loading';
        loadingIndicator.innerHTML = `
            <div class="field-spinner"></div>
            <span class="field-loading-text">${message}</span>
        `;
        parent.appendChild(loadingIndicator);
    }
    
    loadingIndicator.style.display = 'flex';
    field.style.paddingRight = '80px';
}

// Remove loading de campos específicos
function hideFieldLoading(field) {
    const parent = field.parentElement;
    const loadingIndicator = parent.querySelector('.field-loading');
    
    if (loadingIndicator) {
        loadingIndicator.style.display = 'none';
        field.style.paddingRight = '';
    }
}

// Configuração de máscara para telefone brasileiro
function setupPhoneMask() {
    const phoneField = document.getElementById('phone');
    if (phoneField) {
        phoneField.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            
            // Limita a 11 dígitos (DDD + 9 dígitos para celular)
            if (value.length > 11) {
                value = value.substring(0, 11);
            }
            
            // Aplica formatação baseada no comprimento
            if (value.length === 0) {
                e.target.value = '';
            } else if (value.length <= 2) {
                // Apenas DDD
                e.target.value = `(${value}`;
            } else if (value.length <= 6) {
                // DDD + primeiros dígitos
                e.target.value = `(${value.substring(0, 2)}) ${value.substring(2)}`;
            } else if (value.length <= 10) {
                // Telefone fixo: (XX) XXXX-XXXX
                e.target.value = `(${value.substring(0, 2)}) ${value.substring(2, 6)}-${value.substring(6)}`;
            } else {
                // Celular: (XX) 9XXXX-XXXX
                e.target.value = `(${value.substring(0, 2)}) ${value.substring(2, 7)}-${value.substring(7)}`;
            }
        });
        
        // Validação em tempo real para DDD e formato
        phoneField.addEventListener('blur', function(e) {
            const value = e.target.value.replace(/\D/g, '');
            
            if (value.length > 0) {
                // Verifica se o DDD é válido (11-99)
                if (value.length >= 2) {
                    const ddd = parseInt(value.substring(0, 2));
                    if (ddd < 11 || ddd > 99) {
                        showFieldError(e.target, 'DDD inválido. Use um código de área válido (11-99).');
                        return;
                    }
                }
                
                // Verifica formato para celular (11 dígitos)
                if (value.length === 11 && value.charAt(2) !== '9') {
                    showFieldError(e.target, 'Para celulares, o terceiro dígito deve ser 9.');
                    return;
                }
                
                // Verifica formato para telefone fixo (10 dígitos)
                if (value.length === 10) {
                    const thirdDigit = parseInt(value.charAt(2));
                    if (thirdDigit < 2 || thirdDigit > 5) {
                        showFieldError(e.target, 'Para telefones fixos, o terceiro dígito deve ser entre 2 e 5.');
                        return;
                    }
                }
                
                // Verifica se não são todos os dígitos iguais
                if (new Set(value).size === 1) {
                    showFieldError(e.target, 'Número de telefone inválido.');
                    return;
                }
                
                // Remove mensagens de erro se tudo estiver correto
                clearFieldError(e.target);
            }
        });
    }
}

// Configuração de tooltips e mensagens de ajuda
function setupTooltips() {
    // Adiciona tooltips aos campos de formulário
    const formFields = {
        'email': {
            tooltip: 'Digite um endereço de e-mail válido que será usado para login',
            help: 'Exemplo: usuario@dominio.com'
        },
        'username': {
            tooltip: 'Nome de usuário único para sua conta (3-20 caracteres)',
            help: 'Apenas letras, números e underscore são permitidos'
        },
        'password': {
            tooltip: 'Crie uma senha forte para proteger sua conta',
            help: 'Mínimo 8 caracteres com letras, números e símbolos',
            panel: {
                title: 'Requisitos da Senha',
                content: [
                    'Pelo menos 8 caracteres',
                    'Uma letra maiúscula (A-Z)',
                    'Uma letra minúscula (a-z)',
                    'Um número (0-9)',
                    'Um caractere especial (!@#$%^&*)'
                ]
            }
        },
        'confirm_password': {
            tooltip: 'Digite novamente sua senha para confirmação',
            help: 'Deve ser idêntica à senha digitada acima'
        },
        'phone': {
            tooltip: 'Número de telefone brasileiro com DDD',
            help: 'Formato: (11) 99999-9999 ou (11) 9999-9999'
        }
    };
    
    Object.keys(formFields).forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            addTooltipToField(field, formFields[fieldId]);
        }
    });
}

// Adiciona tooltip a um campo específico
function addTooltipToField(field, config) {
    const formGroup = field.closest('.form-group');
    if (!formGroup) return;
    
    const label = formGroup.querySelector('label');
    if (label && config.tooltip) {
        // Adiciona ícone de ajuda ao label
        const tooltipContainer = document.createElement('span');
        tooltipContainer.className = 'tooltip-container';
        
        const helpIcon = document.createElement('i');
        helpIcon.className = 'bi bi-question-circle tooltip-trigger';
        helpIcon.setAttribute('tabindex', '0');
        helpIcon.setAttribute('role', 'button');
        helpIcon.setAttribute('aria-label', 'Mostrar ajuda para este campo');
        
        const tooltip = document.createElement('div');
        tooltip.className = 'tooltip';
        tooltip.textContent = config.tooltip;
        
        tooltipContainer.appendChild(helpIcon);
        tooltipContainer.appendChild(tooltip);
        label.appendChild(tooltipContainer);
        
        // Tornar tooltip acessível
        if (typeof makeTooltipAccessible === 'function') {
            makeTooltipAccessible(helpIcon, tooltip);
        }
    }
    
    // Adiciona texto de ajuda
    if (config.help) {
        const helpText = document.createElement('div');
        helpText.className = 'form-help';
        helpText.setAttribute('aria-live', 'polite');
        helpText.innerHTML = `
            <i class="bi bi-info-circle help-icon"></i>
            <span>${config.help}</span>
        `;
        field.parentNode.appendChild(helpText);
    }
    
    // Adiciona painel de ajuda interativo
    if (config.panel) {
        const helpPanel = document.createElement('div');
        helpPanel.className = `help-panel ${field.id === 'password' ? 'password-help' : ''}`;
        helpPanel.setAttribute('role', 'region');
        helpPanel.setAttribute('aria-label', 'Ajuda para este campo');
        helpPanel.setAttribute('aria-hidden', 'true');
        
        const listItems = config.panel.content.map(item => `<li>${item}</li>`).join('');
        helpPanel.innerHTML = `
            <div class="help-title">
                <i class="bi bi-lightbulb"></i>
                ${config.panel.title}
            </div>
            <ul>${listItems}</ul>
        `;
        
        field.parentNode.appendChild(helpPanel);
        
        // Mostra/esconde painel no foco
        field.addEventListener('focus', () => {
            formGroup.classList.add('focused');
            helpPanel.classList.add('active');
            helpPanel.setAttribute('aria-hidden', 'false');
        });
        
        field.addEventListener('blur', () => {
            setTimeout(() => {
                formGroup.classList.remove('focused');
                helpPanel.classList.remove('active');
                helpPanel.setAttribute('aria-hidden', 'true');
            }, 200);
        });
    }
}

// Configuração de mensagens contextuais
function setupContextualHelp() {
    // Ajuda para força da senha
    const passwordField = document.getElementById('password');
    if (passwordField) {
        passwordField.addEventListener('input', function() {
            updatePasswordHelp(this.value);
        });
    }
    
    // Ajuda para confirmação de senha
    const confirmField = document.getElementById('confirm_password');
    if (confirmField) {
        confirmField.addEventListener('input', function() {
            updateConfirmPasswordHelp();
        });
    }
}

// Atualiza ajuda da senha baseada na força
function updatePasswordHelp(password) {
    const helpPanel = document.querySelector('.password-help');
    if (!helpPanel) return;
    
    const requirements = [
        { test: password.length >= 8, text: 'Pelo menos 8 caracteres' },
        { test: /[A-Z]/.test(password), text: 'Uma letra maiúscula (A-Z)' },
        { test: /[a-z]/.test(password), text: 'Uma letra minúscula (a-z)' },
        { test: /[0-9]/.test(password), text: 'Um número (0-9)' },
        { test: /[!@#$%^&*(),.?":{}|<>]/.test(password), text: 'Um caractere especial (!@#$%^&*)' }
    ];
    
    const listItems = requirements.map(req => {
        const icon = req.test ? '✓' : '○';
        const className = req.test ? 'text-success' : 'text-muted';
        return `<li class="${className}"><span style="margin-right: 6px;">${icon}</span>${req.text}</li>`;
    }).join('');
    
    const list = helpPanel.querySelector('ul');
    if (list) {
        list.innerHTML = listItems;
    }
}

// Atualiza ajuda da confirmação de senha
function updateConfirmPasswordHelp() {
    const password = document.getElementById('password')?.value || '';
    const confirmPassword = document.getElementById('confirm_password')?.value || '';
    const helpText = document.querySelector('#confirm_password').parentNode.querySelector('.form-help span');
    
    if (helpText && confirmPassword) {
        if (password === confirmPassword) {
            helpText.innerHTML = '<span class="text-success">Senhas coincidem</span>';
        } else {
            helpText.innerHTML = '<span class="text-warning">Senhas nao coincidem</span>';
        }
    }
}

// Configuração de ajuda para disponibilidade
function setupAvailabilityHelp() {
    const usernameField = document.getElementById('username');
    const emailField = document.getElementById('email');
    
    [usernameField, emailField].forEach(field => {
        if (field) {
            field.addEventListener('focus', () => {
                showAvailabilityTip(field);
            });
        }
    });
}

// Mostra dica de disponibilidade
function showAvailabilityTip(field) {
    const fieldType = field.type === 'email' ? 'e-mail' : 'nome de usuário';
    const existingTip = field.parentNode.querySelector('.availability-tip');
    
    if (!existingTip) {
        const tip = document.createElement('div');
        tip.className = 'form-help availability-tip';
        tip.innerHTML = `
            <i class="bi bi-search help-icon"></i>
            <span>Verificaremos se este ${fieldType} está disponível enquanto você digita</span>
        `;
        field.parentNode.appendChild(tip);
        
        // Remove a dica após alguns segundos
        setTimeout(() => {
            if (tip.parentElement) {
                tip.style.opacity = '0';
                setTimeout(() => tip.remove(), 300);
            }
        }, 3000);
    }
}

// Funcionalidades de Acessibilidade
function setupAccessibility() {
    // Detectar navegação por teclado
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Tab') {
            document.body.classList.add('keyboard-navigation');
        }
    });
    
    document.addEventListener('mousedown', function() {
        document.body.classList.remove('keyboard-navigation');
    });
    
    // Adicionar skip links
    addSkipLinks();
    
    // Configurar atributos ARIA
    setupAriaAttributes();
    
    // Configurar navegação por teclado
    setupKeyboardNavigation();
    
    // Configurar anúncios para leitores de tela
    setupScreenReaderAnnouncements();
    
    // Configurar live regions
    setupLiveRegions();
}

function addSkipLinks() {
    const skipLink = document.createElement('a');
    skipLink.href = '#main-content';
    skipLink.className = 'skip-link';
    skipLink.textContent = 'Pular para o conteúdo principal';
    skipLink.setAttribute('tabindex', '0');
    
    document.body.insertBefore(skipLink, document.body.firstChild);
    
    // Adicionar ID ao conteúdo principal se não existir
    const mainContent = document.querySelector('.auth-container') || document.querySelector('main');
    if (mainContent && !mainContent.id) {
        mainContent.id = 'main-content';
        mainContent.setAttribute('tabindex', '-1');
    }
}

function setupAriaAttributes() {
    // Configurar formulários com atributos ARIA
    const forms = document.querySelectorAll('.auth-form');
    forms.forEach(form => {
        if (!form.getAttribute('role')) {
            form.setAttribute('role', 'form');
        }
        
        const title = form.querySelector('.auth-header h2');
        if (title && !form.getAttribute('aria-labelledby')) {
            if (!title.id) {
                title.id = 'form-title-' + Math.random().toString(36).substr(2, 9);
            }
            form.setAttribute('aria-labelledby', title.id);
        }
    });
    
    // Configurar campos de formulário
    const formControls = document.querySelectorAll('.form-control');
    formControls.forEach(control => {
        const label = document.querySelector(`label[for="${control.id}"]`);
        if (label && !control.getAttribute('aria-labelledby')) {
            if (!label.id) {
                label.id = control.id + '-label';
            }
            control.setAttribute('aria-labelledby', label.id);
        }
        
        // Adicionar aria-required para campos obrigatórios
        if (control.hasAttribute('required')) {
            control.setAttribute('aria-required', 'true');
        }
        
        // Configurar aria-invalid
        if (control.classList.contains('is-invalid')) {
            control.setAttribute('aria-invalid', 'true');
        } else {
            control.setAttribute('aria-invalid', 'false');
        }
    });
    
    // Configurar botões
    const buttons = document.querySelectorAll('.auth-button, .auth-submit-btn');
    buttons.forEach(button => {
        if (button.disabled) {
            button.setAttribute('aria-disabled', 'true');
        }
        
        if (button.classList.contains('btn-loading')) {
            button.setAttribute('aria-busy', 'true');
        }
    });
    
    // Configurar tooltips
    const tooltips = document.querySelectorAll('.tooltip');
    tooltips.forEach(tooltip => {
        tooltip.setAttribute('role', 'tooltip');
        tooltip.setAttribute('aria-hidden', 'true');
    });
}

function setupKeyboardNavigation() {
    // Navegação por Enter em botões
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && e.target.classList.contains('auth-button')) {
            e.target.click();
        }
        
        // Escape para fechar tooltips
        if (e.key === 'Escape') {
            const visibleTooltips = document.querySelectorAll('.tooltip.show');
            visibleTooltips.forEach(tooltip => {
                tooltip.classList.remove('show');
                tooltip.setAttribute('aria-hidden', 'true');
            });
        }
    });
    
    // Melhorar navegação por Tab
    const focusableElements = 'input, button, select, textarea, a[href], [tabindex]:not([tabindex="-1"])';
    const forms = document.querySelectorAll('.auth-form');
    
    forms.forEach(form => {
        const focusable = form.querySelectorAll(focusableElements);
        const firstFocusable = focusable[0];
        const lastFocusable = focusable[focusable.length - 1];
        
        form.addEventListener('keydown', function(e) {
            if (e.key === 'Tab') {
                if (e.shiftKey) {
                    if (document.activeElement === firstFocusable) {
                        lastFocusable.focus();
                        e.preventDefault();
                    }
                } else {
                    if (document.activeElement === lastFocusable) {
                        firstFocusable.focus();
                        e.preventDefault();
                    }
                }
            }
        });
    });
}

// Função global para anúncios de screen reader
window.announceToScreenReader = function(message, priority = 'polite') {
    let announcer = document.getElementById('screen-reader-announcer');
    if (!announcer) {
        announcer = document.createElement('div');
        announcer.id = 'screen-reader-announcer';
        announcer.className = 'sr-only';
        announcer.setAttribute('aria-live', 'polite');
        announcer.setAttribute('aria-atomic', 'true');
        document.body.appendChild(announcer);
    }
    
    announcer.setAttribute('aria-live', priority);
    announcer.textContent = message;
    
    // Limpar após um tempo
    setTimeout(() => {
        announcer.textContent = '';
    }, 1000);
};

function setupScreenReaderAnnouncements() {
    // Criar região para anúncios se não existir
    if (!document.getElementById('screen-reader-announcer')) {
        const announcer = document.createElement('div');
        announcer.id = 'screen-reader-announcer';
        announcer.className = 'sr-only';
        announcer.setAttribute('aria-live', 'polite');
        announcer.setAttribute('aria-atomic', 'true');
        document.body.appendChild(announcer);
    }
}

function setupLiveRegions() {
    // Configurar regiões dinâmicas
    const errorContainers = document.querySelectorAll('.invalid-feedback');
    errorContainers.forEach(container => {
        container.setAttribute('aria-live', 'assertive');
        container.setAttribute('aria-atomic', 'true');
    });
    
    const successContainers = document.querySelectorAll('.valid-feedback');
    successContainers.forEach(container => {
        container.setAttribute('aria-live', 'polite');
        container.setAttribute('aria-atomic', 'true');
    });
    
    // Configurar loading overlay
    const loadingOverlay = document.querySelector('.loading-overlay');
    if (loadingOverlay) {
        loadingOverlay.setAttribute('aria-live', 'polite');
        loadingOverlay.setAttribute('aria-atomic', 'true');
    }
}

function updateAriaInvalid(field, isValid) {
    field.setAttribute('aria-invalid', isValid ? 'false' : 'true');
    
    // Anunciar mudanças de validação
    const fieldName = field.getAttribute('name') || field.id;
    if (isValid) {
        announceToScreenReader(`Campo ${fieldName} válido`);
    } else {
        announceToScreenReader(`Erro no campo ${fieldName}`, 'assertive');
    }
}

function updateButtonAriaStates(button, isLoading = false, isDisabled = false) {
    button.setAttribute('aria-busy', isLoading ? 'true' : 'false');
    button.setAttribute('aria-disabled', isDisabled ? 'true' : 'false');
    
    if (isLoading) {
        announceToScreenReader('Processando formulário, aguarde...');
    }
}

function makeTooltipAccessible(trigger, tooltip) {
    const tooltipId = 'tooltip-' + Math.random().toString(36).substr(2, 9);
    tooltip.id = tooltipId;
    tooltip.setAttribute('role', 'tooltip');
    tooltip.setAttribute('aria-hidden', 'true');
    
    trigger.setAttribute('aria-describedby', tooltipId);
    
    // Eventos de teclado para tooltips
    trigger.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            const isVisible = tooltip.classList.contains('show');
            
            if (isVisible) {
                tooltip.classList.remove('show');
                tooltip.setAttribute('aria-hidden', 'true');
            } else {
                tooltip.classList.add('show');
                tooltip.setAttribute('aria-hidden', 'false');
            }
        }
    });
    
    // Mostrar/esconder com mouse
    trigger.addEventListener('mouseenter', function() {
        tooltip.classList.add('show');
        tooltip.setAttribute('aria-hidden', 'false');
    });
    
    trigger.addEventListener('mouseleave', function() {
        tooltip.classList.remove('show');
        tooltip.setAttribute('aria-hidden', 'true');
    });
}

// Inicialização quando o DOM estiver carregado
document.addEventListener('DOMContentLoaded', function() {
    // Configura todas as funcionalidades
    setupRealTimeValidation();
    setupPasswordToggle();
    setupSubmitButton();
    setupPhoneMask();
    setupTooltips();
    setupContextualHelp();
    setupAvailabilityHelp();
    setupAccessibility();
    
    // Configura os campos de senha se existirem
    const passwordField = document.getElementById('password');
    if (passwordField) {
        passwordField.addEventListener('input', checkPasswordStrength);
    }
    
    const confirmPasswordField = document.getElementById('confirm_password');
    if (confirmPasswordField) {
        confirmPasswordField.addEventListener('input', checkPasswordMatch);
    }
    
    // Adiciona animação de entrada aos formulários
    const authContainer = document.querySelector('.auth-container');
    if (authContainer) {
        authContainer.classList.add('fade-in');
    }
});

// Função para exibir notificações toast modernas
function showToast(message, type = 'info') {
    // Cria container se não existir
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'toast-container';
        document.body.appendChild(toastContainer);
    }
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type} fade-in`;
    toast.innerHTML = `
        <div class="toast-content">
            <i class="bi bi-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">
            <i class="bi bi-x"></i>
        </button>
    `;
    
    toastContainer.appendChild(toast);
    
    // Remove automaticamente após 5 segundos
    setTimeout(() => {
        if (toast.parentElement) {
            toast.classList.add('fade-out');
            setTimeout(() => {
                if (toast.parentElement) {
                    toast.remove();
                }
            }, 300);
        }
    }, 5000);
}

// Exportar funções para uso global
    window.checkPasswordStrength = checkPasswordStrength;
    window.checkPasswordMatch = checkPasswordMatch;
    window.showToast = showToast;
    window.addElementAnimation = addElementAnimation;
    window.showLoadingOverlay = showLoadingOverlay;
    window.hideLoadingOverlay = hideLoadingOverlay;
    window.updateProgress = updateProgress;
    window.showFieldLoading = showFieldLoading;
    window.hideFieldLoading = hideFieldLoading;
    window.simulateFormProgress = simulateFormProgress;
    window.updateAriaInvalid = updateAriaInvalid;
    window.updateButtonAriaStates = updateButtonAriaStates;
    window.makeTooltipAccessible = makeTooltipAccessible;
}