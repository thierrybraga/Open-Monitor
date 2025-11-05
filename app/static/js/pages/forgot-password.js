// forgot-password.js - validação do formulário de recuperação de senha
// Segue o padrão do sistema (sem inline script, compatível com CSP via nonce)

(function() {
  'use strict';

  function ready(fn) {
    if (document.readyState !== 'loading') {
      fn();
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
  }

  function ensureInvalidFeedback(inputEl, message) {
    var feedback = inputEl.nextElementSibling;
    if (!feedback || !feedback.classList || !feedback.classList.contains('invalid-feedback')) {
      feedback = document.createElement('div');
      feedback.className = 'invalid-feedback';
      inputEl.parentNode.insertBefore(feedback, inputEl.nextSibling);
    }
    feedback.textContent = message || 'Por favor, corrija este campo.';
  }

  function clearInvalid(inputEl) {
    inputEl.classList.remove('is-invalid');
    var feedback = inputEl.nextElementSibling;
    if (feedback && feedback.classList && feedback.classList.contains('invalid-feedback')) {
      feedback.textContent = '';
    }
  }

  ready(function() {
    var form = document.querySelector('.auth-form');
    var emailInput = document.getElementById('email');
    var submitBtn = document.getElementById('forgot-btn');
    var btnText = submitBtn ? submitBtn.querySelector('.btn-text') : null;
    var btnLoading = submitBtn ? submitBtn.querySelector('.btn-loading') : null;
    if (!form || !emailInput) return;

    // Remover mensagens inválidas ao digitar
    emailInput.addEventListener('input', function() {
      if (emailInput.value.trim().length > 0) {
        clearInvalid(emailInput);
      }
    });

    form.addEventListener('submit', function(e) {
      var emailValue = (emailInput.value || '').trim();

      if (!emailValue) {
        e.preventDefault();
        emailInput.classList.add('is-invalid');
        ensureInvalidFeedback(emailInput, 'Por favor, digite seu e-mail.');
        emailInput.focus();
        return;
      }

      // Validação básica de e-mail
      var emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(emailValue)) {
        e.preventDefault();
        emailInput.classList.add('is-invalid');
        ensureInvalidFeedback(emailInput, 'Por favor, digite um e-mail válido.');
        emailInput.focus();
        return;
      }

      // OK: limpar estados inválidos e permitir submissão
      clearInvalid(emailInput);

      // Estado de carregamento do botão
      if (submitBtn && btnText && btnLoading) {
        submitBtn.setAttribute('disabled', 'disabled');
        btnText.style.display = 'none';
        btnLoading.style.display = 'inline-flex';
      }
    });
  });
})();