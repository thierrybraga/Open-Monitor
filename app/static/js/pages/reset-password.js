// reset-password.js - comportamento específico da página de redefinição de senha
// Reutiliza utilitários de auth.js para força e correspondência de senha

(function() {
  'use strict';

  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  function ensureInvalidFeedback(inputEl, message) {
    var feedback = document.getElementById(inputEl.id === 'password' ? 'passwordFeedback' : 'confirmPasswordFeedback');
    if (!feedback) {
      feedback = document.createElement('div');
      feedback.className = 'invalid-feedback';
      inputEl.parentNode.insertBefore(feedback, inputEl.nextSibling);
    }
    feedback.textContent = message || 'Por favor, corrija este campo.';
  }

  function clearInvalid(inputEl) {
    inputEl.classList.remove('is-invalid');
    var feedbackId = inputEl.id === 'password' ? 'passwordFeedback' : 'confirmPasswordFeedback';
    var feedback = document.getElementById(feedbackId) || inputEl.nextElementSibling;
    if (feedback && feedback.classList && feedback.classList.contains('invalid-feedback')) {
      feedback.textContent = '';
      feedback.style.display = 'none';
    }
  }

  ready(function() {
    var form = document.querySelector('.auth-form');
    var password = document.getElementById('password');
    var confirmPassword = document.getElementById('confirm_password');
    var submitBtn = document.getElementById('reset-btn');
    var btnText = submitBtn ? submitBtn.querySelector('.btn-text') : null;
    var btnLoading = submitBtn ? submitBtn.querySelector('.btn-loading') : null;
    if (!form || !password || !confirmPassword) return;

    // Listeners para força e correspondência (funções de auth.js)
    password.addEventListener('input', function() {
      try { if (typeof window.checkPasswordStrength === 'function') window.checkPasswordStrength(); } catch (e) {}
      try { if (typeof window.checkPasswordMatch === 'function') window.checkPasswordMatch(); } catch (e) {}
      clearInvalid(password);
    });
    confirmPassword.addEventListener('input', function() {
      try { if (typeof window.checkPasswordMatch === 'function') window.checkPasswordMatch(); } catch (e) {}
      clearInvalid(confirmPassword);
    });

    form.addEventListener('submit', function(e) {
      var pwd = (password.value || '').trim();
      var conf = (confirmPassword.value || '').trim();

      // Validações básicas
      if (!pwd) {
        e.preventDefault();
        password.classList.add('is-invalid');
        ensureInvalidFeedback(password, 'Por favor, digite sua nova senha.');
        password.focus();
        return;
      }
      if (!conf) {
        e.preventDefault();
        confirmPassword.classList.add('is-invalid');
        ensureInvalidFeedback(confirmPassword, 'Por favor, confirme sua nova senha.');
        confirmPassword.focus();
        return;
      }
      if (pwd.length < 8) {
        e.preventDefault();
        password.classList.add('is-invalid');
        ensureInvalidFeedback(password, 'A senha deve ter pelo menos 8 caracteres.');
        password.focus();
        return;
      }
      if (pwd !== conf) {
        e.preventDefault();
        confirmPassword.classList.add('is-invalid');
        ensureInvalidFeedback(confirmPassword, 'As senhas não coincidem.');
        confirmPassword.focus();
        return;
      }

      // Estado de carregamento do botão
      if (submitBtn && btnText && btnLoading) {
        submitBtn.setAttribute('disabled', 'disabled');
        btnText.style.display = 'none';
        btnLoading.style.display = 'inline-flex';
      }
    });
  });
})();