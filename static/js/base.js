'use strict';

/**
 * Base.js - Core JavaScript for the Open CVE Report base layout
 *
 * Purpose:
 * - Manages interactions for the sidebar toggle on small screens.
 * - Handles theme switching (dark/light mode) and saves user preference.
 * - Initializes Bootstrap components (Tooltips, Dropdowns, Alerts).
 * - Implements a simple system alert mechanism (e.g., for online status).
 * - Adds a class to the HTML element when JavaScript is enabled.
 *
 * Dependencies:
 * - Requires Bootstrap 5.3.2 (specifically Collapse and Dropdown components, and utility classes).
 * - Assumes corresponding CSS styles are available (especially in base.css and theme files).
 * - Assumes Bootstrap JS bundle is loaded before this script executes (due to 'defer').
 *
 * Version: 2.2.0
 * Last Updated: April 2025
 */

(function() {

  // =========================================================================
  // 1. Element Selection
  // =========================================================================
  // Declare variables to hold DOM elements
  let htmlEl, bodyEl, sidebarToggle, sidebar, mainContent, navbar, footer, sidebarScrim,
      darkModeToggle, sidebarLinks, dropdownToggles, systemAlertsContainer;

  /**
   * Assigns DOM elements to variables.
   * Called after DOMContentLoaded.
   */
  function selectElements() {
    htmlEl = document.documentElement;
    bodyEl = document.body;
    sidebarToggle = document.getElementById('sidebarToggle');
    sidebar = document.getElementById('sidebar');
    mainContent = document.getElementById('main-content');
    navbar = document.querySelector('header.navbar');
    footer = document.querySelector('footer.footer');
    sidebarScrim = document.querySelector('.sidebar-scrim');
    darkModeToggle = document.querySelector('.dark-mode-toggle');
    // Note: sidebarLinks and dropdownToggles might be dynamically added/removed,
    // so selecting them once might not be sufficient if content changes after load.
    // Event delegation or re-selection might be needed for dynamic content,
    // but for static base layout elements, selecting once is fine.
    sidebarLinks = document.querySelectorAll('.sidebar-nav .sidebar-link');
    dropdownToggles = document.querySelectorAll('[data-bs-toggle="dropdown"]');
    systemAlertsContainer = document.getElementById('system-alerts');
  }

  // =========================================================================
  // 2. Basic Checks
  // =========================================================================
  /**
   * Checks if essential DOM elements are present.
   * Logs a warning if any required element is missing.
   * @returns {boolean} True if all required elements are found, false otherwise.
   */
  function checkRequiredElements() {
    const requiredElements = [
      { el: htmlEl, name: 'html' },
      { el: bodyEl, name: 'body' },
      { el: sidebarToggle, name: 'sidebarToggle button' },
      { el: sidebar, name: 'sidebar nav' },
      { el: mainContent, name: 'main-content area' },
      { el: navbar, name: 'navbar header' },
      { el: footer, name: 'footer' },
      { el: sidebarScrim, name: 'sidebar scrim' },
      { el: systemAlertsContainer, name: 'system alerts container' }
      // darkModeToggle is optional, so not marked as required here
    ];

    let allFound = true;
    requiredElements.forEach(item => {
      if (!item.el) {
        console.warn(`Open CVE Report Base JS Warning: Required element "${item.name}" not found.`);
        allFound = false;
      }
    });
    return allFound;
  }

  // =========================================================================
  // 3. Sidebar Functionality
  // =========================================================================
  /**
   * Initializes the sidebar toggle functionality.
   * Handles click events for the toggle button and the scrim.
   * Adjusts sidebar and scrim classes and ARIA attributes.
   */
  function initializeSidebar() {
    // Check if essential sidebar elements are present
    if (!sidebarToggle || !sidebar || !sidebarScrim || !mainContent || !navbar) {
        console.warn("Essential sidebar elements not found. Sidebar functionality disabled.");
        return; // Exit if required elements are missing
    }

    /**
     * Toggles the sidebar state (expanded/collapsed).
     */
    const toggleSidebar = () => {
      const isExpanded = sidebar.classList.toggle('expanded');
      sidebarToggle.setAttribute('aria-expanded', isExpanded);

      // Toggle scrim visibility only on small screens (breakpoint < 768px)
      if (window.innerWidth < 768) { // Use the same breakpoint as CSS media query
         sidebarScrim.classList.toggle('visible', isExpanded);
         // Prevent body scrolling when sidebar is open on small screens
         bodyEl.classList.toggle('overflow-hidden', isExpanded);
      } else {
           // On larger screens, always hide scrim and ensure body scrolling is normal
           sidebarScrim.classList.remove('visible');
           bodyEl.classList.remove('overflow-hidden');
      }
    };

    // Add event listener for the sidebar toggle button click
    sidebarToggle.addEventListener('click', toggleSidebar);

    // Add event listener to close sidebar when clicking the scrim (on small screens)
    sidebarScrim.addEventListener('click', () => {
        if (sidebar.classList.contains('expanded') && window.innerWidth < 768) {
             toggleSidebar(); // Use the same toggle function to ensure state consistency
        }
    });

    // Optional: Close sidebar when a link is clicked (useful for SPA navigation)
    // This might need adjustment based on how your application handles page navigation.
    if (sidebarLinks) {
      sidebarLinks.forEach(link => {
        link.addEventListener('click', () => {
          // Only close if sidebar is expanded and on small screens
          if (sidebar.classList.contains('expanded') && window.innerWidth < 768) {
             // Delay closing slightly to allow click event to register
             setTimeout(toggleSidebar, 100);
          }
        });
      });
    }

    /**
     * Handles window resize events to adjust sidebar/scrim state based on breakpoint.
     */
    const handleResize = () => {
      // If resizing to a large screen (>= 768px)
      if (window.innerWidth >= 768) {
        // Ensure scrim is hidden
        sidebarScrim.classList.remove('visible');
         // Ensure body scrolling is enabled
         bodyEl.classList.remove('overflow-hidden');
         // On large screens, sidebar state (expanded/collapsed) might persist
         // or be controlled differently (e.g., always open).
         // The CSS handles positioning with margin-left based on .expanded class.
      } else {
          // If resizing to a small screen (< 768px)
           // If sidebar is currently expanded, show the scrim and disable body scrolling
           if (sidebar.classList.contains('expanded')) {
               sidebarScrim.classList.add('visible');
               bodyEl.classList.add('overflow-hidden');
           }
      }
       // Update aria-expanded state on toggle button based on current visual state
       // This can be complex if CSS handles state change, but we can approximate
       // based on the 'expanded' class presence.
       sidebarToggle.setAttribute('aria-expanded', sidebar.classList.contains('expanded'));
    };

    // Add resize listener
    window.addEventListener('resize', handleResize);

    // Set initial state on page load based on window size
    handleResize();
     console.log('Sidebar Functionality Initialized');
  }

  // =========================================================================
  // 4. Theme Toggling (Dark/Light Mode)
  // =========================================================================
  /**
   * Initializes theme switching based on user preference (local storage) or system setting.
   * Toggles 'data-theme' attribute on the html element and updates toggle button state.
   */
  function initializeTheme() {
    // Check if required elements are present
    if (!darkModeToggle || !htmlEl) {
      console.warn("Dark mode toggle button or html element not found. Theme switching disabled.");
      return; // Exit if required elements are missing
    }

    const themeStorageKey = 'data-theme'; // Key for local storage
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)'); // System preference media query

    /**
     * Sets the theme attribute on the HTML element and updates UI.
     * @param {'light' | 'dark'} theme - The theme to set ('light' or 'dark').
     */
    const setTheme = (theme) => {
      htmlEl.setAttribute(themeStorageKey, theme);

      // Update aria-pressed state on the toggle button for accessibility
      const isDarkMode = theme === 'dark';
      darkModeToggle.setAttribute('aria-pressed', isDarkMode);
       // Update the icon inside the toggle button
       const iconEl = darkModeToggle.querySelector('.dark-mode-icon');
       if(iconEl) {
            // Remove existing icon classes (sun and moon)
            iconEl.classList.remove('bi-moon', 'bi-sun');
            if (isDarkMode) {
                iconEl.classList.add('bi-sun'); // Show sun icon in dark mode
                iconEl.setAttribute('aria-label', 'Switch to light mode'); // Update accessible label
                darkModeToggle.setAttribute('title', 'Switch to light mode'); // Update tooltip
            } else {
                iconEl.classList.add('bi-moon'); // Show moon icon in light mode
                 iconEl.setAttribute('aria-label', 'Switch to dark mode'); // Update accessible label
                 darkModeToggle.setAttribute('title', 'Switch to dark mode'); // Update tooltip
            }
       }
        // Dispatch a custom event after theme change - useful for other components
        document.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme: theme } }));
         console.log(`Theme set to: ${theme}`);
    };

    /**
     * Gets the user's preferred theme from local storage.
     * @returns {'light' | 'dark' | null} The stored theme or null if no preference is set.
     */
    const getStoredTheme = () => localStorage.getItem(themeStorageKey);

    /**
     * Toggles the theme between 'light' and 'dark'.
     * Updates local storage preference.
     */
    const toggleTheme = () => {
      const currentTheme = htmlEl.getAttribute(themeStorageKey);
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark'; // Toggle theme
      setTheme(newTheme); // Apply the new theme
      localStorage.setItem(themeStorageKey, newTheme); // Save the preference to local storage
    };

    // --- Initial Theme Application ---
    const storedTheme = getStoredTheme(); // Check for a user-set preference
    if (storedTheme) {
      setTheme(storedTheme); // Apply the stored theme if found
    } else {
      // Otherwise, apply the system preference
      setTheme(prefersDark.matches ? 'dark' : 'light');
    }

    // --- Event Listeners ---
    // Listen for system theme changes (only if user hasn't set a manual preference)
    prefersDark.addEventListener('change', (e) => {
        if (!getStoredTheme()) { // Only react to system changes if no preference is stored
            setTheme(e.matches ? 'dark' : 'light');
        }
    });

    // Add click listener to the dark mode toggle button
    darkModeToggle.addEventListener('click', toggleTheme);

     console.log('Theme Toggling Initialized');
  }

  // =========================================================================
  // 5. Accessibility Enhancements
  // =========================================================================
   /**
   * Initializes accessibility features.
   * - Adds a class to the body for keyboard navigation focus styles.
   * - Listens for reduced motion preference.
   */
  function initializeAccessibility() {
    // Add a class to the body when keyboard is used for navigation (Tab key)
    // This allows CSS to apply different focus styles for keyboard vs mouse users
    document.body.addEventListener('mousedown', () => {
      document.body.classList.remove('keyboard-navigation');
    });

    document.body.addEventListener('keydown', (e) => {
      if (e.key === 'Tab') {
        document.body.classList.add('keyboard-navigation');
      }
    });

    // Listen for prefers-reduced-motion
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

    /**
     * Adds or removes a class to the html element based on reduced motion preference.
     * @param {MediaQueryListEvent} e - The media query list event.
     */
    const handleReducedMotionChange = (e) => {
        if (e.matches) {
            htmlEl.classList.add('reduce-motion');
            console.log("Reduced motion preference detected: Enabled.");
        } else {
            htmlEl.classList.remove('reduce-motion');
             console.log("Reduced motion preference detected: Disabled.");
        }
    };

    // Initial check and add listener
    handleReducedMotionChange(prefersReducedMotion); // Set initial state
    prefersReducedMotion.addEventListener('change', handleReducedMotionChange); // Listen for changes

     console.log('Accessibility Enhancements Initialized');
  }


  // =========================================================================
  // 6. Bootstrap Component Initialization
  // =========================================================================
   /**
    * Initializes Bootstrap Tooltips.
    * Requires Bootstrap's JS bundle.
    */
   function initializeTooltips() {
       // Select all elements with data-bs-toggle="tooltip"
       const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
       // Initialize each tooltip
       tooltipTriggerList.map(function (tooltipTriggerEl) {
           return new bootstrap.Tooltip(tooltipTriggerEl)
       });
        // console.log('Bootstrap Tooltips Initialized'); // Log only if needed
   }

    /**
     * Initializes Bootstrap Dropdowns.
     * Requires Bootstrap's JS bundle.
     * Note: Bootstrap's JS often auto-initializes dropdowns, but explicit init is safer.
     */
    function initializeDropdowns() {
         // Select all elements with data-bs-toggle="dropdown"
        const dropdownElementList = [].slice.call(document.querySelectorAll('[data-bs-toggle="dropdown"]'))
        // Initialize each dropdown
        dropdownElementList.map(function (dropdownToggleEl) {
            return new bootstrap.Dropdown(dropdownToggleEl)
        });
         // console.log('Bootstrap Dropdowns Initialized'); // Log only if needed
    }

    /**
     * Initializes Bootstrap Alerts.
     * Provides a basic showAlert function to create and display alerts dynamically.
     * Requires Bootstrap's JS bundle for the dismiss button functionality.
     */
    function initializeAlertSystem() {
        // Check if the container for alerts exists
        if (!systemAlertsContainer) {
            console.warn("System alerts container not found. Alert system disabled.");
            return; // Exit if the container is missing
        }

        /**
         * Displays a system alert message.
         * @param {string} message - The message to display.
         * @param {'primary' | 'secondary' | 'success' | 'danger' | 'warning' | 'info' | 'light' | 'dark'} type - The Bootstrap alert type (color scheme).
         * @param {number} duration - Duration in milliseconds before the alert auto-dismisses (0 for permanent).
         * @param {string} [icon='info-circle'] - Bootstrap icon class name (e.g., 'info-circle', 'check-circle', 'exclamation-triangle').
         * @returns {string} The ID of the created alert element, or null if failed.
         */
        window.showAlert = function(message, type = 'info', duration = 5000, icon = 'info-circle') {
            // Basic validation
            if (!message || typeof message !== 'string') {
                console.error("showAlert requires a valid message string.");
                return null;
            }
             if (!systemAlertsContainer) {
                 console.error("System alerts container is not available.");
                 return null;
             }

            const alertId = `alert-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`; // Generate a unique ID

            const alertDiv = document.createElement('div');
            alertDiv.id = alertId;
            // Apply Bootstrap alert classes and utility classes
            alertDiv.className = `alert alert-${type} alert-dismissible fade show d-flex align-items-center`;
            alertDiv.setAttribute('role', 'alert'); // ARIA role for accessibility

            // Construct the alert HTML content
            alertDiv.innerHTML = `
                <i class="bi bi-${icon} me-2 fs-5" aria-hidden="true"></i>
                <div>${message}</div>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Fechar"></button>
            `;

            // Append the new alert to the container
            systemAlertsContainer.appendChild(alertDiv);

            // If a duration is specified (greater than 0), set a timeout to dismiss the alert
            if (duration > 0) {
                // Use Bootstrap's built-in 'closed.bs.alert' event for cleanup after CSS transition
                 alertDiv.addEventListener('closed.bs.alert', function () {
                    // Remove the element from the DOM after the fade-out transition
                    alertDiv.remove();
                 });
                setTimeout(() => {
                    // Get the Bootstrap Alert instance to trigger its hide method
                    const alertToDismiss = bootstrap.Alert.getInstance(alertDiv);
                     if (alertToDismiss) {
                         // Calling hide() triggers the fade-out animation and then the 'closed.bs.alert' event
                         alertToDismiss.hide();
                     } else {
                         // Fallback: If Bootstrap JS is not fully initialized or instance not found, just remove
                         alertDiv.remove();
                     }
                }, duration);
            }

            return alertId; // Return the generated ID for potential manual control later
        };

        console.log('System Alert Module Initialized');

        // Example usage (can be removed or triggered by other parts of the app)
        // showAlert('Bem-vindo ao Open CVE Report!', 'success', 8000);
        // showAlert('Você está offline. Algumas funcionalidades podem estar limitadas.', 'warning', 0); // Permanent alert
    }


    // =========================================================================
    // 7. Online Status Detection
    // =========================================================================
     /**
      * Handles online/offline status changes and displays system alerts.
      * Requires the showAlert function from initializeAlertSystem to be available.
      */
    function initializeOnlineStatusDetection() {
        // Ensure the showAlert function is available before proceeding
         if (typeof window.showAlert !== 'function') {
             console.warn("showAlert function not available. Online status alerts disabled.");
             return; // Exit if the dependency is not met
         }

        let offlineAlertId = null; // Variable to store the ID of the permanent offline alert

        /**
         * Updates the online status and displays/hides alerts accordingly.
         */
        const updateOnlineStatus = () => {
            const isOnline = navigator.onLine; // Check browser's online status

            if (!isOnline) { // If currently offline
                // Display a permanent offline alert if one is not already shown
                if (offlineAlertId === null) {
                     // Use showAlert with duration 0 for a permanent alert
                    offlineAlertId = showAlert('Você está atualmente offline. Algumas funcionalidades podem não estar disponíveis.', 'warning', 0, 'exclamation-triangle');
                     console.log('Detected offline status. Offline alert displayed.');
                }
            } else { // If currently online
                // If online, hide/remove the previously shown offline alert
                if (offlineAlertId !== null) {
                    const alertElement = document.getElementById(offlineAlertId);
                    if (alertElement) {
                         // Get the Bootstrap Alert instance and hide it
                        const alertInstance = bootstrap.Alert.getInstance(alertElement);
                        if (alertInstance) {
                            alertInstance.hide(); // This triggers the fade-out animation and removal
                        } else {
                             // Fallback if Bootstrap JS is not fully initialized
                             alertElement.remove();
                        }
                    }
                    offlineAlertId = null; // Reset the alert ID after dismissing
                     console.log('Detected online status. Offline alert removed.');
                }
                 // Optionally show a temporary "You are back online" message
                 // showAlert('Você voltou a ficar online.', 'success', 5000, 'check-circle');
            }
        };

        // Add event listeners for online and offline events
        window.addEventListener('online', updateOnlineStatus);
        window.addEventListener('offline', updateOnlineStatus);

        // Perform an initial check of the online status on page load
        updateOnlineStatus();

         console.log('Online Status Detection Initialized');
    }


  // =========================================================================
  // 8. Initialization on DOM Ready
  // =========================================================================
  // Wait for the DOM to be fully loaded before initializing scripts
  document.addEventListener('DOMContentLoaded', function() {
    selectElements(); // Select all necessary DOM elements

    // Perform basic checks to ensure essential elements are available
    if (!checkRequiredElements()) {
        console.error("Essential elements for base layout not found. Some base layout features may not work correctly.");
        // Decide whether to continue initialization of other components or stop
        // For now, we log a warning and continue with potentially independent components
    }

    // Initialize core base layout features that don't strictly depend on Bootstrap JS yet
    initializeSidebar(); // Sidebar toggle logic
    initializeTheme(); // Theme switching (depends on local storage and media query)
    initializeAccessibility(); // Accessibility features (keyboard nav, reduced motion)


    // Initialize Bootstrap components and features that depend on them
    // Use setTimeout with 0 delay to ensure Bootstrap JS is processed first if loaded deferred
    // This helps avoid errors if base.js loads immediately but bootstrap.bundle.min.js hasn't finished executing
     setTimeout(() => {
        // Check if bootstrap is available globally (from bootstrap.bundle.min.js)
        if (typeof bootstrap === 'undefined') {
            console.error("Bootstrap JS bundle not loaded. Skipping initialization of Bootstrap components and dependent features.");
            // Optionally display a fallback error message to the user
            // showAlert('Erro ao carregar recursos. Algumas funcionalidades podem não estar disponíveis.', 'danger', 0);
            return; // Stop further initialization that relies on Bootstrap JS
        }

        initializeTooltips(); // Initialize Bootstrap tooltips
        initializeDropdowns(); // Initialize Bootstrap dropdowns

         // Initialize the system alert mechanism and then the online status detection
         // which relies on the alert mechanism.
        initializeAlertSystem();
        initializeOnlineStatusDetection();


        // Dispatch a custom event indicating that the base layout JS initialization is complete
        // Other scripts can listen for this event if they need to ensure base setup is done
        document.dispatchEvent(new Event('baseLayoutReady'));
         console.log('Base Layout JavaScript Initialization Complete');
     }, 0); // Delay execution until event loop is clear, allowing other defer scripts to run


    // Add here any other initializations needed specifically for the base layout
    // (e.g., event listeners for other base elements that don't fit the above categories)
  });

})(); // End of IIFE (Immediately Invoked Function Expression)