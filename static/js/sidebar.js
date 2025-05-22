/**
 * sidebar.js - Gerencia o comportamento e interações da sidebar
 */

document.addEventListener('DOMContentLoaded', function() {
  // Elementos principais
  const sidebar = document.getElementById('sidebar');
  const sidebarCollapseBtn = document.getElementById('sidebarCollapseBtn');

  /**
   * Alterna o estado de colapso da sidebar
   */
  function toggleSidebar() {
    if (!sidebar) return;

    sidebar.classList.toggle('collapsed');

    // Alterna o ícone do botão
    const icon = this.querySelector('i');
    if (icon) {
      if (sidebar.classList.contains('collapsed')) {
        icon.classList.replace('bi-chevron-left', 'bi-chevron-right');
      } else {
        icon.classList.replace('bi-chevron-right', 'bi-chevron-left');
      }
    }

    // Opcional: salva a preferência do usuário no localStorage
    localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
  }

  /**
   * Verifica o tamanho da tela e ajusta a sidebar para dispositivos móveis
   */
  function checkScreenSize() {
    if (!sidebar) return;

    if (window.innerWidth < 768) {
      sidebar.classList.add('collapsed');
    } else {
      // Restaura o estado anterior para telas maiores (opcional)
      const wasCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
      if (wasCollapsed) {
        sidebar.classList.add('collapsed');
      } else {
        sidebar.classList.remove('collapsed');
      }
    }
  }

  /**
   * Inicializa tooltips para itens da sidebar quando colapsada
   */
  function initTooltips() {
    if (typeof bootstrap !== 'undefined') {
      const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
      tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
      });
    }
  }

  /**
   * Configura os eventos de hover para expandir a sidebar automaticamente
   */
  function setupHoverEvents() {
    if (!sidebar) return;

    // Verifica se está no desktop (apenas neste caso ativa os eventos de hover)
    if (window.innerWidth >= 768) {
      sidebar.addEventListener('mouseenter', handleSidebarHoverEnter);
      sidebar.addEventListener('mouseleave', handleSidebarHoverLeave);
    }
  }

  /**
   * Manipulador do evento de passar o mouse sobre a sidebar
   */
  function handleSidebarHoverEnter() {
    if (this.classList.contains('collapsed')) {
      this.classList.add('hover-expanded');
    }
  }

  /**
   * Manipulador do evento de tirar o mouse da sidebar
   */
  function handleSidebarHoverLeave() {
    this.classList.remove('hover-expanded');
  }

  /**
   * Restaura as preferências do usuário do localStorage (opcional)
   */
  function restoreUserPreferences() {
    if (!sidebar) return;

    // Se estiver no mobile, ignora as preferências salvas
    if (window.innerWidth < 768) return;

    const wasCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
    if (wasCollapsed) {
      sidebar.classList.add('collapsed');

      // Atualiza o ícone do botão para corresponder ao estado
      const icon = sidebarCollapseBtn ? sidebarCollapseBtn.querySelector('i') : null;
      if (icon) {
        icon.classList.replace('bi-chevron-left', 'bi-chevron-right');
      }
    }
  }

  // Inicialização dos eventos
  if (sidebarCollapseBtn) {
    sidebarCollapseBtn.addEventListener('click', toggleSidebar);
  }

  // Eventos e configurações iniciais
  checkScreenSize();
  setupHoverEvents();
  initTooltips();
  restoreUserPreferences();

  // Monitorar redimensionamento da janela
  window.addEventListener('resize', function() {
    checkScreenSize();
    setupHoverEvents();
  });
});