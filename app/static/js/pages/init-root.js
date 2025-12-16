(function() {
  'use strict';

  function ready(fn) {
    if (document.readyState !== 'loading') {
      fn();
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
  }

  function toggleTacacs() {
    const section = document.getElementById('tacacs-section');
    if (section) {
      const isVisible = section.style.display !== 'none';
      section.style.display = isVisible ? 'none' : 'block';
    }
  }

  function validateField(input) {
    if (!input) return true;
    if (input.hasAttribute('required') && !input.value.trim()) {
      input.classList.add('is-invalid');
      return false;
    }
    input.classList.remove('is-invalid');
    return true;
  }

  function validateForm(form) {
    const inputs = form.querySelectorAll('.form-control[required]');
    let ok = true;
    inputs.forEach(inp => { if (!validateField(inp)) ok = false; });
    const password = form.querySelector('#password');
    if (password && password.value.trim().length < 8) {
      password.classList.add('is-invalid');
      ok = false;
    }
    return ok;
  }

  function setupSubmit() {
    const form = document.getElementById('init-root-form');
    if (!form) return;
    form.addEventListener('submit', function(e) {
      const btn = document.getElementById('init-root-btn');
      if (!validateForm(form)) {
        e.preventDefault();
        return;
      }
      if (btn) {
        const text = btn.querySelector('.btn-text');
        const loading = btn.querySelector('.btn-loading');
        if (text && loading) {
          text.style.display = 'none';
          loading.style.display = 'inline-flex';
          btn.disabled = true;
        }
      }
    });
  }

  ready(function() {
    const btn = document.getElementById('toggle-tacacs');
    if (btn) btn.addEventListener('click', toggleTacacs);
    setupSubmit();
    const terms = document.getElementById('terms_accepted');
    if (terms) terms.checked = true;
  });
})();
