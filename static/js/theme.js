/**
 * 🌓 SISTEMA DE TEMA CLARO/ESCURO
 * ================================
 * 
 * Este módulo gerencia a alternância entre temas claro e escuro,
 * persistindo a preferência do usuário no localStorage.
 */

(function() {
    'use strict';

    // Constantes
    const THEME_KEY = 'open-monitor-theme';
    const THEME_LIGHT = 'light';
    const THEME_DARK = 'dark';
    const THEME_AUTO = 'auto';
    
    // Elementos DOM
    let themeToggleBtn = null;
    let backToTopBtn = null;
    let themeText = null;
    let themeIconLight = null;
    let themeIconDark = null;
    let body = null;

    /**
     * Inicializa o sistema de temas e funcionalidades do footer
     */
    function initTheme() {
        body = document.body;
        themeToggleBtn = document.getElementById('theme-toggle');
        backToTopBtn = document.getElementById('back-to-top');
        themeText = document.getElementById('theme-text');
        themeIconLight = document.getElementById('theme-icon-light');
        themeIconDark = document.getElementById('theme-icon-dark');
        
        if (!themeToggleBtn) {
            console.warn('Theme toggle button not found');
            return;
        }

        // Carrega o tema salvo ou usa o padrão do sistema
        const savedTheme = getSavedTheme();
        const initialTheme = savedTheme || getSystemTheme();
        
        // Aplica o tema inicial
        applyTheme(initialTheme);
        
        // Adiciona event listeners
        themeToggleBtn.addEventListener('click', toggleTheme);
        
        if (backToTopBtn) {
            backToTopBtn.addEventListener('click', scrollToTop);
            // Mostra/esconde o botão baseado na posição do scroll
            window.addEventListener('scroll', handleScroll);
        }
        
        // Inicializa tooltips do Bootstrap se disponível
        if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
            initTooltips();
        }
        
        // Escuta mudanças na preferência do sistema
        if (window.matchMedia) {
            const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            mediaQuery.addListener(handleSystemThemeChange);
        }
    }

    /**
     * Obtém o tema salvo no localStorage
     */
    function getSavedTheme() {
        try {
            return localStorage.getItem(THEME_KEY);
        } catch (e) {
            console.warn('Could not access localStorage:', e);
            return null;
        }
    }

    /**
     * Salva o tema no localStorage
     */
    function saveTheme(theme) {
        try {
            localStorage.setItem(THEME_KEY, theme);
        } catch (e) {
            console.warn('Could not save theme to localStorage:', e);
        }
    }

    /**
     * Obtém a preferência de tema do sistema
     */
    function getSystemTheme() {
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return THEME_DARK;
        }
        return THEME_LIGHT;
    }

    /**
     * Aplica o tema especificado
     */
    function applyTheme(theme) {
        if (!body) return;

        // Remove classes de tema existentes
        body.classList.remove('theme-light', 'theme-dark');
        
        // Aplica a nova classe de tema
        if (theme === THEME_DARK) {
            body.classList.add('theme-dark');
        } else {
            body.classList.add('theme-light');
        }

        // Atualiza o atributo data-theme para CSS
        body.setAttribute('data-theme', theme);
        
        // Atualiza a aparência do botão
        updateToggleButton(theme);
        
        // Dispara evento customizado para outros scripts
        dispatchThemeChangeEvent(theme);
    }

    /**
     * Atualiza a aparência do botão de toggle
     */
    function updateToggleButton(theme) {
        if (!themeToggleBtn) return;

        const isDark = theme === THEME_DARK;
        const ariaLabel = isDark ? 'Alternar para tema claro' : 'Alternar para tema escuro';
        const title = isDark ? 'Tema claro' : 'Tema escuro';
        
        themeToggleBtn.setAttribute('aria-label', ariaLabel);
        themeToggleBtn.setAttribute('title', title);
        
        // Atualiza os ícones
        if (themeIconLight && themeIconDark) {
            if (isDark) {
                themeIconLight.classList.add('d-none');
                themeIconDark.classList.remove('d-none');
            } else {
                themeIconLight.classList.remove('d-none');
                themeIconDark.classList.add('d-none');
            }
        }
        
        // Atualiza o texto do tema
        if (themeText) {
            themeText.textContent = isDark ? 'Escuro' : 'Claro';
        }
        
        // Atualiza o atributo data-bs-theme para Bootstrap
        document.documentElement.setAttribute('data-bs-theme', theme);
        
        // Adiciona classe de animação temporariamente
        themeToggleBtn.classList.add('switching');
        setTimeout(() => {
            themeToggleBtn.classList.remove('switching');
        }, 300);
    }

    /**
     * Rola suavemente para o topo da página
     */
    function scrollToTop() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    }

    /**
     * Manipula o evento de scroll para mostrar/esconder o botão "Voltar ao Topo"
     */
    function handleScroll() {
        if (!backToTopBtn) return;
        
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const showThreshold = 300; // Mostra o botão após 300px de scroll
        
        if (scrollTop > showThreshold) {
            backToTopBtn.style.opacity = '1';
            backToTopBtn.style.visibility = 'visible';
        } else {
            backToTopBtn.style.opacity = '0';
            backToTopBtn.style.visibility = 'hidden';
        }
    }

    /**
     * Inicializa os tooltips do Bootstrap
     */
    function initTooltips() {
        try {
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl, {
                    delay: { show: 500, hide: 100 },
                    placement: 'top'
                });
            });
        } catch (e) {
            console.warn('Could not initialize tooltips:', e);
        }
    }

    /**
     * Alterna entre os temas
     */
    function toggleTheme() {
        const currentTheme = getCurrentTheme();
        const newTheme = currentTheme === THEME_DARK ? THEME_LIGHT : THEME_DARK;
        
        applyTheme(newTheme);
        saveTheme(newTheme);
    }

    /**
     * Obtém o tema atual
     */
    function getCurrentTheme() {
        if (!body) return THEME_LIGHT;
        return body.classList.contains('theme-dark') ? THEME_DARK : THEME_LIGHT;
    }

    /**
     * Manipula mudanças na preferência do sistema
     */
    function handleSystemThemeChange(e) {
        // Só aplica mudança automática se não houver preferência salva
        const savedTheme = getSavedTheme();
        if (!savedTheme) {
            const systemTheme = e.matches ? THEME_DARK : THEME_LIGHT;
            applyTheme(systemTheme);
        }
    }

    /**
     * Dispara evento customizado quando o tema muda
     */
    function dispatchThemeChangeEvent(theme) {
        const event = new CustomEvent('themechange', {
            detail: { theme: theme }
        });
        document.dispatchEvent(event);
    }

    /**
     * API pública para outros scripts
     */
    window.ThemeManager = {
        getCurrentTheme: getCurrentTheme,
        setTheme: function(theme) {
            if ([THEME_LIGHT, THEME_DARK].includes(theme)) {
                applyTheme(theme);
                saveTheme(theme);
            }
        },
        toggleTheme: toggleTheme,
        getSystemTheme: getSystemTheme,
        scrollToTop: scrollToTop,
        initTooltips: initTooltips
    };

    /**
     * Adiciona estilos CSS para o botão "Voltar ao Topo"
     */
    function addBackToTopStyles() {
        const style = document.createElement('style');
        style.textContent = `
            #back-to-top {
                opacity: 0;
                visibility: hidden;
                transition: opacity 0.3s ease, visibility 0.3s ease, transform 0.3s ease;
            }
            
            #back-to-top.show {
                opacity: 1;
                visibility: visible;
            }
        `;
        document.head.appendChild(style);
    }

    // Inicializa quando o DOM estiver pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            addBackToTopStyles();
            initTheme();
        });
    } else {
        addBackToTopStyles();
        initTheme();
    }

})();