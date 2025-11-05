/**
 * Settings Page JavaScript
 * Handles user settings, preferences, and configuration management
 */

class SettingsManager {
    constructor() {
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadUserSettings();
    }

    bindEvents() {
        // Theme settings
        const themeSelect = document.getElementById('theme-select');
        if (themeSelect) {
            themeSelect.addEventListener('change', this.handleThemeChange.bind(this));
        }

        const languageSelect = document.getElementById('language');
        if (languageSelect) {
            languageSelect.addEventListener('change', (e) => {
                const lang = e.target.value;
                this.updateSetting('general.language', lang);
            });
        }

        const timezoneSelect = document.getElementById('timezone');
        if (timezoneSelect) {
            timezoneSelect.addEventListener('change', (e) => {
                const tz = e.target.value;
                this.updateSetting('general.timezone', tz);
            });
        }

        // Notification settings
        const notificationToggles = document.querySelectorAll('.notification-toggle');
        notificationToggles.forEach(toggle => {
            toggle.addEventListener('change', this.handleNotificationChange.bind(this));
        });

        // Save settings button
        const saveButton = document.getElementById('save-settings');
        if (saveButton) {
            saveButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.saveSettings();
            });
        }

        // Reset settings button
        const resetButton = document.getElementById('reset-settings');
        if (resetButton) {
            resetButton.addEventListener('click', this.resetSettings.bind(this));
        }
    }

    async loadUserSettings() {
        // Preferir carregar do backend; fallback para localStorage
        try {
            const resp = await fetch('/api/v1/account/user-settings', {
                method: 'GET',
                headers: { 'Accept': 'application/json' },
                credentials: 'include',
            });
            if (resp.ok) {
                const data = await resp.json();
                if (data && data.success && data.settings) {
                    localStorage.setItem('userSettings', JSON.stringify(data.settings));
                    this.applySettings(data.settings);
                    return;
                }
            }
        } catch (err) {
            console.warn('Falha ao carregar configurações do servidor, usando localStorage.', err);
        }
        const savedSettings = localStorage.getItem('userSettings');
        if (savedSettings) {
            const settings = JSON.parse(savedSettings);
            this.applySettings(settings);
        }
    }

    handleThemeChange(event) {
        const theme = event.target.value;
        document.documentElement.setAttribute('data-theme', theme);
        this.updateSetting('general.theme', theme);
    }

    handleNotificationChange(event) {
        const setting = event.target.dataset.setting;
        const enabled = event.target.checked;
        this.updateSetting(`notifications.${setting}`, enabled);
    }

    updateSetting(key, value) {
        const settings = this.getSettings();
        this.setNestedProperty(settings, key, value);
        localStorage.setItem('userSettings', JSON.stringify(settings));
    }

    setNestedProperty(obj, path, value) {
        const keys = path.split('.');
        let current = obj;
        for (let i = 0; i < keys.length - 1; i++) {
            if (!current[keys[i]]) {
                current[keys[i]] = {};
            }
            current = current[keys[i]];
        }
        current[keys[keys.length - 1]] = value;
    }

    getSettings() {
        const saved = localStorage.getItem('userSettings');
        return saved ? JSON.parse(saved) : {};
    }

    applySettings(settings) {
        // Aplicar tema
        const theme = settings?.general?.theme;
        if (theme) {
            document.documentElement.setAttribute('data-theme', theme);
            const themeSelect = document.getElementById('theme-select');
            if (themeSelect) {
                themeSelect.value = theme;
            }
        }

        // Aplicar idioma e fuso horário
        const languageSelect = document.getElementById('language');
        if (languageSelect && settings?.general?.language) {
            languageSelect.value = settings.general.language;
        }
        const timezoneSelect = document.getElementById('timezone');
        if (timezoneSelect && settings?.general?.timezone) {
            timezoneSelect.value = settings.general.timezone;
        }

        // Apply notification settings
        if (settings.notifications) {
            Object.keys(settings.notifications).forEach(key => {
                const toggle = document.querySelector(`[data-setting="${key}"]`);
                if (toggle) {
                    toggle.checked = settings.notifications[key];
                }
            });
        }
    }

    saveSettings() {
        // Save settings to server
        const settings = this.getSettings();
        
        fetch('/api/v1/account/user-settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify(settings)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.showMessage('Settings saved successfully!', 'success');
            } else {
                this.showMessage('Failed to save settings.', 'error');
            }
        })
        .catch(error => {
            console.error('Error saving settings:', error);
            this.showMessage('Error saving settings.', 'error');
        });
    }

    resetSettings() {
        if (confirm('Are you sure you want to reset all settings to default?')) {
            localStorage.removeItem('userSettings');
            location.reload();
        }
    }

    showMessage(message, type) {
        // Create and show a toast message
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} toast-message`;
        toast.textContent = message;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new SettingsManager();
});