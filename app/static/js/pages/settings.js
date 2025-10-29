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

        // Notification settings
        const notificationToggles = document.querySelectorAll('.notification-toggle');
        notificationToggles.forEach(toggle => {
            toggle.addEventListener('change', this.handleNotificationChange.bind(this));
        });

        // Save settings button
        const saveButton = document.getElementById('save-settings');
        if (saveButton) {
            saveButton.addEventListener('click', this.saveSettings.bind(this));
        }

        // Reset settings button
        const resetButton = document.getElementById('reset-settings');
        if (resetButton) {
            resetButton.addEventListener('click', this.resetSettings.bind(this));
        }
    }

    loadUserSettings() {
        // Load user settings from localStorage or API
        const savedSettings = localStorage.getItem('userSettings');
        if (savedSettings) {
            const settings = JSON.parse(savedSettings);
            this.applySettings(settings);
        }
    }

    handleThemeChange(event) {
        const theme = event.target.value;
        document.documentElement.setAttribute('data-theme', theme);
        this.updateSetting('theme', theme);
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
        // Apply theme
        if (settings.theme) {
            document.documentElement.setAttribute('data-theme', settings.theme);
            const themeSelect = document.getElementById('theme-select');
            if (themeSelect) {
                themeSelect.value = settings.theme;
            }
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
        
        fetch('/api/user/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
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