/**
 * responsive.js - Sistema de Responsividade JavaScript
 * Versão: 1.0 - Criado em Janeiro 2025
 * Gerencia comportamentos responsivos e interações móveis
 */

(function() {
    'use strict';

    // ==========================================================================
    // Variáveis e Configurações
    // ==========================================================================

    const BREAKPOINTS = {
        xs: 320,
        sm: 576,
        md: 768,
        lg: 992,
        xl: 1200,
        xxl: 1400
    };

    let currentBreakpoint = getCurrentBreakpoint();
    let sidebarOpen = false;
    let resizeTimeout;

    // ==========================================================================
    // Utilitários
    // ==========================================================================

    /**
     * Obtém o breakpoint atual baseado na largura da janela
     */
    function getCurrentBreakpoint() {
        const width = window.innerWidth;
        if (width < BREAKPOINTS.sm) return 'xs';
        if (width < BREAKPOINTS.md) return 'sm';
        if (width < BREAKPOINTS.lg) return 'md';
        if (width < BREAKPOINTS.xl) return 'lg';
        if (width < BREAKPOINTS.xxl) return 'xl';
        return 'xxl';
    }

    /**
     * Verifica se está em modo mobile
     */
    function isMobile() {
        return window.innerWidth < BREAKPOINTS.md;
    }

    /**
     * Verifica se está em modo tablet
     */
    function isTablet() {
        return window.innerWidth >= BREAKPOINTS.md && window.innerWidth < BREAKPOINTS.lg;
    }

    /**
     * Debounce para otimizar eventos de resize
     */
    function debounce(func, wait) {
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(resizeTimeout);
                func(...args);
            };
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(later, wait);
        };
    }

    // ==========================================================================
    // Gerenciamento da Sidebar
    // ==========================================================================

    /**
     * Inicializa o sistema de sidebar responsiva
     */
    function initSidebar() {
        const sidebar = document.querySelector('.sidebar');
        const sidebarToggle = document.querySelector('.sidebar-toggle');
        const mainContent = document.querySelector('.main-content-area-wrapper');
        
        if (!sidebar || !sidebarToggle) return;

        // Criar overlay para mobile
        createSidebarOverlay();

        // Event listeners
        sidebarToggle.addEventListener('click', toggleSidebar);
        
        // Fechar sidebar ao clicar no overlay
        const overlay = document.querySelector('.sidebar-overlay');
        if (overlay) {
            overlay.addEventListener('click', closeSidebar);
        }

        // Fechar sidebar com ESC
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && sidebarOpen && isMobile()) {
                closeSidebar();
            }
        });

        // Ajustar sidebar baseado no tamanho da tela
        adjustSidebarForScreenSize();
    }

    /**
     * Cria o overlay para fechar a sidebar em mobile
     */
    function createSidebarOverlay() {
        if (document.querySelector('.sidebar-overlay')) return;
        
        const overlay = document.createElement('div');
        overlay.className = 'sidebar-overlay';
        overlay.setAttribute('aria-hidden', 'true');
        document.body.appendChild(overlay);
    }

    /**
     * Alterna a visibilidade da sidebar
     */
    function toggleSidebar() {
        if (sidebarOpen) {
            closeSidebar();
        } else {
            openSidebar();
        }
    }

    /**
     * Abre a sidebar
     */
    function openSidebar() {
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.querySelector('.sidebar-overlay');
        const toggle = document.querySelector('.sidebar-toggle');
        
        if (!sidebar) return;

        sidebar.classList.add('show');
        if (overlay) overlay.classList.add('show');
        if (toggle) toggle.setAttribute('aria-expanded', 'true');
        
        sidebarOpen = true;
        
        // Prevenir scroll do body em mobile
        if (isMobile()) {
            document.body.style.overflow = 'hidden';
        }
        
        // Foco na sidebar para acessibilidade
        sidebar.focus();
        
        // Dispatch evento customizado
        window.dispatchEvent(new CustomEvent('sidebarOpened'));
    }

    /**
     * Fecha a sidebar
     */
    function closeSidebar() {
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.querySelector('.sidebar-overlay');
        const toggle = document.querySelector('.sidebar-toggle');
        
        if (!sidebar) return;

        sidebar.classList.remove('show');
        if (overlay) overlay.classList.remove('show');
        if (toggle) toggle.setAttribute('aria-expanded', 'false');
        
        sidebarOpen = false;
        
        // Restaurar scroll do body
        document.body.style.overflow = '';
        
        // Dispatch evento customizado
        window.dispatchEvent(new CustomEvent('sidebarClosed'));
    }

    /**
     * Ajusta a sidebar baseado no tamanho da tela
     */
    function adjustSidebarForScreenSize() {
        if (isMobile()) {
            // Em mobile, sempre fechar a sidebar
            closeSidebar();
        } else {
            // Em desktop/tablet, remover classes mobile
            const sidebar = document.querySelector('.sidebar');
            const overlay = document.querySelector('.sidebar-overlay');
            
            if (sidebar) sidebar.classList.remove('show');
            if (overlay) overlay.classList.remove('show');
            
            sidebarOpen = false;
            document.body.style.overflow = '';
        }
    }

    // ==========================================================================
    // Gerenciamento de Tabelas Responsivas
    // ==========================================================================

    /**
     * Inicializa tabelas responsivas
     */
    function initResponsiveTables() {
        const tables = document.querySelectorAll('table');
        
        tables.forEach(table => {
            if (!table.closest('.table-responsive')) {
                const wrapper = document.createElement('div');
                wrapper.className = 'table-responsive';
                table.parentNode.insertBefore(wrapper, table);
                wrapper.appendChild(table);
            }
            
            // Adicionar classes para ocultar colunas em mobile
            addMobileTableClasses(table);
        });
    }

    /**
     * Adiciona classes para ocultar colunas menos importantes em mobile
     */
    function addMobileTableClasses(table) {
        const headers = table.querySelectorAll('th');
        const rows = table.querySelectorAll('tbody tr');
        
        // Identificar colunas menos importantes (baseado em palavras-chave)
        const lessImportantColumns = [];
        headers.forEach((header, index) => {
            const text = header.textContent.toLowerCase();
            if (text.includes('data') || text.includes('criado') || text.includes('atualizado') || 
                text.includes('detalhes') || text.includes('observações')) {
                lessImportantColumns.push(index);
            }
        });
        
        // Adicionar classes d-none-mobile
        lessImportantColumns.forEach(colIndex => {
            if (headers[colIndex]) {
                headers[colIndex].classList.add('d-none-mobile');
            }
            
            rows.forEach(row => {
                const cell = row.children[colIndex];
                if (cell) {
                    cell.classList.add('d-none-mobile');
                }
            });
        });
    }

    // ==========================================================================
    // Otimizações de Performance
    // ==========================================================================

    /**
     * Otimiza animações baseado na preferência do usuário
     */
    function optimizeAnimations() {
        const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
        
        function handleMotionPreference(e) {
            if (e.matches) {
                document.documentElement.style.setProperty('--animation-duration-fast', '0.1s');
                document.documentElement.style.setProperty('--animation-duration-normal', '0.15s');
                document.documentElement.style.setProperty('--animation-duration-slow', '0.2s');
            } else {
                document.documentElement.style.removeProperty('--animation-duration-fast');
                document.documentElement.style.removeProperty('--animation-duration-normal');
                document.documentElement.style.removeProperty('--animation-duration-slow');
            }
        }
        
        prefersReducedMotion.addEventListener('change', handleMotionPreference);
        handleMotionPreference(prefersReducedMotion);
    }

    /**
     * Otimiza imagens para dispositivos móveis
     */
    function optimizeImages() {
        if (!isMobile()) return;
        
        const images = document.querySelectorAll('img[data-mobile-src]');
        images.forEach(img => {
            const mobileSrc = img.getAttribute('data-mobile-src');
            if (mobileSrc) {
                img.src = mobileSrc;
            }
        });
    }

    // ==========================================================================
    // Gerenciamento de Orientação
    // ==========================================================================

    /**
     * Gerencia mudanças de orientação
     */
    function handleOrientationChange() {
        // Aguardar a mudança de orientação ser aplicada
        setTimeout(() => {
            adjustSidebarForScreenSize();
            initResponsiveTables();
            
            // Dispatch evento customizado
            window.dispatchEvent(new CustomEvent('orientationChanged', {
                detail: { orientation: screen.orientation?.angle || 0 }
            }));
        }, 100);
    }

    // ==========================================================================
    // Event Listeners e Inicialização
    // ==========================================================================

    /**
     * Gerencia mudanças de tamanho da janela
     */
    const handleResize = debounce(() => {
        const newBreakpoint = getCurrentBreakpoint();
        
        if (newBreakpoint !== currentBreakpoint) {
            currentBreakpoint = newBreakpoint;
            adjustSidebarForScreenSize();
            optimizeImages();
            
            // Dispatch evento customizado
            window.dispatchEvent(new CustomEvent('breakpointChanged', {
                detail: { breakpoint: newBreakpoint }
            }));
        }
    }, 250);

    /**
     * Inicialização principal
     */
    function init() {
        // Aguardar DOM estar pronto
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }
        
        // Inicializar componentes
        initSidebar();
        initResponsiveTables();
        optimizeAnimations();
        optimizeImages();
        
        // Event listeners
        window.addEventListener('resize', handleResize);
        window.addEventListener('orientationchange', handleOrientationChange);
        
        // Marcar como inicializado
        document.documentElement.setAttribute('data-responsive-initialized', 'true');
        
        console.log('Sistema de responsividade inicializado');
    }

    // ==========================================================================
    // API Pública
    // ==========================================================================

    // Expor API pública
    window.ResponsiveManager = {
        isMobile,
        isTablet,
        getCurrentBreakpoint,
        openSidebar,
        closeSidebar,
        toggleSidebar
    };

    // Inicializar
    init();

})();