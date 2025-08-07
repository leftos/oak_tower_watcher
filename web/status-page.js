// Status page JavaScript functionality

// VATSIM Controller Ratings mapping
function translateControllerRating(ratingId) {
    const ratingMap = {
        '-1': "Inactive",
        '0': "Suspended",
        '1': "Pilot/Observer",
        '2': "S1",  // Student Controller
        '3': "S2",  // Tower Controller
        '4': "S3",  // TMA Controller
        '5': "C1",  // Enroute Controller
        '6': "C2",  // Senior Controller
        '7': "C3",  // Senior Controller
        '8': "I1",  // Instructor
        '9': "I2",  // Senior Instructor
        '10': "I3", // Senior Instructor
        '11': "SUP" // Supervisor
    };
    
    try {
        const id = String(ratingId);
        return ratingMap[id] || `Unknown (${ratingId})`;
    } catch (error) {
        return `Invalid (${ratingId})`;
    }
}

class OAKTowerStatus {
    constructor() {
        this.autoRefreshEnabled = true;
        this.refreshInterval = 10000; // 10 seconds - faster since we're just getting cached data
        this.refreshTimer = null;
        this.lastServerUpdateTime = null;
        this.dataFetchTime = null;
        this.cacheAgeAtFetch = null;
        
        this.init();
    }

    init() {
        // Add event listeners for buttons
        this.setupEventListeners();
        
        // Start auto-refresh
        this.startAutoRefresh();
        
        // Initial load
        this.loadStatus();
        
        // Update timestamps every second
        setInterval(() => this.updateTimestamps(), 1000);
    }

    setupEventListeners() {
        // Force refresh button
        const forceRefreshBtn = document.getElementById('force-refresh-btn');
        if (forceRefreshBtn) {
            forceRefreshBtn.addEventListener('click', () => this.forceRefresh());
        }

        // Toggle auto-refresh button no longer exists - users can't control monitoring frequency

        // Test notification button
        const testNotificationBtn = document.getElementById('test-notification-btn');
        if (testNotificationBtn) {
            testNotificationBtn.addEventListener('click', () => this.testStatusNotification());
        }
    }

    async loadStatus() {
        // Set up delayed loading state - only show spinner if request takes too long
        let loadingTimeout = null;
        let showedDelayedLoading = false;
        
        try {
            // Set up a delayed loading indicator - show subtle loading indicator only after 1.5 seconds
            loadingTimeout = setTimeout(() => {
                this.showDelayedLoadingIndicator();
                showedDelayedLoading = true;
            }, 1500);
            
            // For now, we'll simulate the API call with mock data
            // In a real implementation, this would call the actual API
            const status = await this.fetchStatus();
            
            // Clear the loading timeout since we got a response
            if (loadingTimeout) {
                clearTimeout(loadingTimeout);
            }
            
            // Hide delayed loading indicator if it was shown
            if (showedDelayedLoading) {
                this.hideDelayedLoadingIndicator();
            }
            
            this.updateUI(status);
            
            // Use cache age in seconds to avoid clock sync issues
            if (status.cacheAge !== undefined) {
                // Store when we fetched this data and the cache age at that time
                this.dataFetchTime = new Date();
                this.cacheAgeAtFetch = status.cacheAge;
                console.debug('Using cache age approach - Cache age at fetch:', status.cacheAge, 'seconds');
            } else if (status.lastUpdated) {
                // Fallback to timestamp parsing if cache age not available
                try {
                    this.lastServerUpdateTime = new Date(status.lastUpdated);
                    const now = new Date();
                    const timeDiff = now - this.lastServerUpdateTime;
                    
                    if (isNaN(this.lastServerUpdateTime.getTime()) || timeDiff < -300000) {
                        console.warn('Server timestamp issue, falling back to current time');
                        this.lastServerUpdateTime = new Date();
                    }
                } catch (error) {
                    console.error('Error parsing server timestamp:', error);
                    this.lastServerUpdateTime = new Date();
                }
            } else {
                // Final fallback to current time
                this.lastServerUpdateTime = new Date();
            }
            
        } catch (error) {
            // Clear the loading timeout on error
            if (loadingTimeout) {
                clearTimeout(loadingTimeout);
            }
            
            // Hide delayed loading indicator if it was shown
            if (showedDelayedLoading) {
                this.hideDelayedLoadingIndicator();
            }
            
            console.error('Error loading status:', error);
            this.showErrorState(error.message);
        }
    }

    async fetchStatus() {
        try {
            // Use cached status from monitoring service to prevent VATSIM API spam
            const response = await fetch('/api/cached-status');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Transform cached API response to match our UI expectations
            return {
                status: data.status,
                facilityName: data.facility_name || 'Monitored Facilities',
                mainControllers: data.main_controllers || [],
                supportingAbove: data.supporting_above || [],
                supportingBelow: data.supporting_below || [],
                config: data.config || {},
                cacheAge: data.cache_age_seconds || 0,
                lastUpdated: data.last_updated,
                monitoringService: data.monitoring_service || {},
                userAuthenticated: data.user_authenticated || false,
                facility_names: data.facility_names || {}
            };
            
        } catch (error) {
            console.error('Cached status fetch error:', error);
            throw error;
        }
    }

    updateUI(status) {
        this.updateMainStatus(status);
        this.updateControllers(status);
        this.updateServiceStats(status);
        this.updateSectionHeaders(status);
    }

    updateMainStatus(status) {
        const indicator = document.getElementById('main-status-indicator');
        const title = document.getElementById('status-title');
        const description = document.getElementById('status-description');

        // Clear existing classes
        indicator.className = 'status-indicator-large';

        // Get facility names from backend configuration instead of deriving from controller lists
        const facilityNames = status.facility_names || {};
        const mainFacilityName = facilityNames.main_facility || this.getFacilityName(status.mainControllers) || 'Main facility';
        const supportingFacilityName = facilityNames.supporting_above || this.getFacilityName(status.supportingAbove) || 'Supporting facility';

        switch (status.status) {
            case 'main_facility_and_supporting_above_online':
                indicator.classList.add('status-online');
                indicator.textContent = '🟣';
                title.textContent = 'Full Coverage Online';
                description.textContent = `${mainFacilityName} and supporting facilities are active`;
                break;
            case 'main_facility_online':
                indicator.classList.add('status-online');
                indicator.textContent = '🟢';
                title.textContent = `${mainFacilityName} Online`;
                description.textContent = `${mainFacilityName} controller is active`;
                break;
            case 'supporting_above_online':
                indicator.classList.add('status-partial');
                indicator.textContent = '🟡';
                title.textContent = `${supportingFacilityName} Online`;
                description.textContent = `${mainFacilityName} offline, but ${supportingFacilityName} active`;
                break;
            case 'all_offline':
                indicator.classList.add('status-offline');
                indicator.textContent = '🔴';
                title.textContent = 'All Facilities Offline';
                description.textContent = 'No controllers currently active';
                break;
            default:
                indicator.classList.add('status-error');
                indicator.textContent = '⚫';
                title.textContent = 'Status Unknown';
                description.textContent = 'Unable to determine current status';
        }

        // Add animation
        indicator.classList.add('status-change');
        setTimeout(() => indicator.classList.remove('status-change'), 500);
    }

    updateControllers(status) {
        // Get facility names from backend configuration
        const facilityNames = status.facility_names || {};
        const mainFacilityName = facilityNames.main_facility || this.getFacilityName(status.mainControllers) || 'main facility';
        
        this.updateControllerSection('main-controllers', status.mainControllers, `No controllers online on ${mainFacilityName}`);
        this.updateControllerSection('supporting-above-controllers', status.supportingAbove, 'No supporting above controllers online');
        this.updateControllerSection('supporting-below-controllers', status.supportingBelow, 'No supporting below controllers online');
    }

    updateControllerSection(elementId, controllers, emptyMessage) {
        const container = document.getElementById(elementId);
        
        if (!controllers || controllers.length === 0) {
            container.innerHTML = `<div class="no-controllers">${emptyMessage}</div>`;
            return;
        }

        container.innerHTML = controllers.map(controller => `
            <div class="controller-item">
                <div class="controller-header">
                    <span class="controller-callsign">${controller.callsign}</span>
                    <span class="controller-frequency">${controller.frequency}</span>
                </div>
                <div class="controller-name">${controller.name || '(No Name Provided)'} (${translateControllerRating(controller.rating)})</div>
                <div class="controller-details">
                    <div>CID: ${controller.cid || 'Unknown'}</div>
                    <div>Online: ${this.formatDuration(controller.logon_time)}</div>
                </div>
            </div>
        `).join('');
    }

    updateServiceStats(status) {
        // Update monitoring status based on service state
        const monitoringStatusElement = document.getElementById('monitoring-status');
        if (status.monitoringService && status.monitoringService.running) {
            monitoringStatusElement.textContent = 'Active';
        } else {
            monitoringStatusElement.textContent = 'Initializing...';
        }
        
        if (status.config && status.config.check_interval) {
            document.getElementById('check-interval').textContent = `${status.config.check_interval} seconds`;
        } else {
            document.getElementById('check-interval').textContent = '60 seconds';
        }
        
        // Update facility name
        const facilityNameElement = document.getElementById('facility-name');
        if (facilityNameElement && status.facilityName) {
            facilityNameElement.textContent = status.facilityName;
        }
    }

    // Removed updateUserConfigStatus - personal configuration card no longer shown

    formatDuration(logonTime) {
        if (!logonTime) return 'Unknown';
        
        const now = new Date();
        const logon = new Date(logonTime);
        const diff = now - logon;
        
        const hours = Math.floor(diff / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        
        if (hours > 0) {
            return `${hours}h ${minutes}m`;
        } else {
            return `${minutes}m`;
        }
    }

    showLoadingState() {
        const sections = ['main-controllers', 'supporting-above-controllers', 'supporting-below-controllers'];
        sections.forEach(id => {
            const element = document.getElementById(id);
            element.innerHTML = `
                <div class="loading-placeholder">
                    <div class="loading"></div>
                    <span>Loading controller data...</span>
                </div>
            `;
        });
    }

    showDelayedLoadingIndicator() {
        // Create a subtle loading indicator overlay without replacing content
        let indicator = document.getElementById('delayed-loading-indicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'delayed-loading-indicator';
            indicator.className = 'delayed-loading-overlay';
            indicator.innerHTML = `
                <div class="delayed-loading-content">
                    <div class="loading-spinner-small"></div>
                    <span>Refreshing...</span>
                </div>
            `;
            
            // Add to the main status section
            const statusSection = document.querySelector('.status-section');
            if (statusSection) {
                statusSection.appendChild(indicator);
            }
        }
        indicator.style.display = 'flex';
    }

    hideDelayedLoadingIndicator() {
        const indicator = document.getElementById('delayed-loading-indicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
    }

    showErrorState(message) {
        const container = document.querySelector('.status-section');
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = `Error loading status: ${message}`;
        container.appendChild(errorDiv);
        
        // Remove error message after 5 seconds
        setTimeout(() => errorDiv.remove(), 5000);
    }

    updateTimestamps() {
        const lastCheck = document.getElementById('last-check');
        
        // Use cache age approach if available (avoids clock sync issues)
        if (this.dataFetchTime && this.cacheAgeAtFetch !== null) {
            const now = new Date();
            const timeSinceFetch = Math.floor((now - this.dataFetchTime) / 1000);
            const totalAge = this.cacheAgeAtFetch + timeSinceFetch;
            
            console.debug('Cache age calculation - Age at fetch:', this.cacheAgeAtFetch, 'Time since fetch:', timeSinceFetch, 'Total age:', totalAge);
            
            this.formatTimeDisplay(lastCheck, totalAge);
        } else if (this.lastServerUpdateTime) {
            // Fallback to timestamp comparison
            const now = new Date();
            const diff = now - this.lastServerUpdateTime;
            const seconds = Math.floor(diff / 1000);
            
            if (seconds < -30) { // Allow small negative differences (up to 30 seconds) for minor clock drift
                lastCheck.textContent = 'Just updated';
                console.debug('Minor negative time difference (clock drift), showing as just updated');
            } else if (seconds < 0) {
                lastCheck.textContent = 'Just updated';
            } else {
                this.formatTimeDisplay(lastCheck, seconds);
            }
        } else {
            lastCheck.textContent = 'Never';
        }
    }

    formatTimeDisplay(element, seconds) {
        if (seconds < 60) {
            element.textContent = `${seconds} seconds ago`;
        } else if (seconds < 3600) { // Less than 1 hour
            const minutes = Math.floor(seconds / 60);
            element.textContent = `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
        } else if (seconds < 86400) { // Less than 1 day
            const hours = Math.floor(seconds / 3600);
            element.textContent = `${hours} hour${hours > 1 ? 's' : ''} ago`;
        } else {
            // More than a day - something is wrong
            element.textContent = 'Unknown';
            console.warn('Time difference too large, may indicate timestamp issue');
        }
    }

    startAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
        }
        
        this.refreshTimer = setInterval(() => {
            if (this.autoRefreshEnabled) {
                this.loadStatus();
            }
        }, this.refreshInterval);
    }

    stopAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }

    forceRefresh() {
        const refreshBtn = document.getElementById('refresh-text');
        const originalText = refreshBtn.textContent;
        
        refreshBtn.textContent = '🔄 Refreshing Cache...';
        
        // Just refresh the cached data, don't trigger new VATSIM API calls
        this.loadStatus().then(() => {
            refreshBtn.textContent = originalText;
            
            // Show success message briefly
            const container = document.querySelector('.status-section');
            const successDiv = document.createElement('div');
            successDiv.className = 'success-message';
            successDiv.textContent = 'Cached data refreshed successfully';
            container.appendChild(successDiv);
            
            setTimeout(() => successDiv.remove(), 3000);
        });
    }

    // Removed toggleAutoRefresh() - users no longer control monitoring frequency
    // The background monitoring service handles all VATSIM API calls

    async testStatusNotification() {
        const testBtn = document.getElementById('test-notification-text');
        const originalText = testBtn.textContent;
        
        testBtn.textContent = '📤 Sending...';
        
        try {
            const response = await fetch('/api/test-status-notification', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Show success message
                this.showMessage('success', 'Test notification sent successfully! Check your device.', {
                    status: result.status,
                    controllers: result.controllers,
                    using_user_config: result.using_user_config
                });
                
                console.log('Test status notification sent successfully');
            } else {
                // Show error message
                this.showMessage('error', result.message || 'Failed to send test notification');
            }
            
        } catch (error) {
            console.error('Error sending test notification:', error);
            this.showMessage('error', 'Network error: Unable to send test notification');
        } finally {
            testBtn.textContent = originalText;
        }
    }

    showMessage(type, message, details = null) {
        const container = document.querySelector('.status-section');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message-notification ${type}-message`;
        
        let messageContent = message;
        
        if (details && type === 'success') {
            messageContent += `<br><small>Status: ${details.status || 'Unknown'}`;
            if (details.controllers) {
                const totalControllers = (details.controllers.main || 0) +
                                       (details.controllers.supporting_above || 0) +
                                       (details.controllers.supporting_below || 0);
                messageContent += ` | ${totalControllers} controllers online`;
            }
            if (details.using_user_config) {
                messageContent += ` | Using custom config`;
            }
            messageContent += '</small>';
        }
        
        messageDiv.innerHTML = messageContent;
        container.appendChild(messageDiv);
        
        // Auto-remove message after 5 seconds
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 5000);
        
        // Add fade-in animation
        setTimeout(() => messageDiv.classList.add('message-fade-in'), 100);
    }

    getFacilityName(controllers) {
        // Extract facility name from first controller's callsign
        if (controllers && controllers.length > 0) {
            return controllers[0].callsign;
        }
        return null;
    }

    updateSectionHeaders(status) {
        // Update section headers to use configured facility names
        const facilityNames = status.facility_names || {};
        const mainFacilityName = facilityNames.main_facility || this.getFacilityName(status.mainControllers) || 'Main Facilities';
        
        // Find and update the main facility header by finding the element that contains the main controllers
        const controllerCards = document.querySelectorAll('.controller-card h3');
        controllerCards.forEach(header => {
            if (header.textContent.includes('Main Facilities')) {
                // Always use the configured facility name, regardless of online status
                if (facilityNames.main_facility) {
                    header.innerHTML = `🏗️ ${facilityNames.main_facility}`;
                } else if (status.mainControllers && status.mainControllers.length > 0) {
                    const facilityName = this.getFacilityName(status.mainControllers);
                    if (facilityName) {
                        header.innerHTML = `🏗️ ${facilityName}`;
                    }
                } else {
                    header.innerHTML = `🏗️ Main Facilities`;
                }
            }
        });
    }
}

// Cookie utility functions
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

function setCookie(name, value, days) {
    const date = new Date();
    date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
    const expires = `expires=${date.toUTCString()}`;
    document.cookie = `${name}=${value};${expires};path=/`;
}

// First Visit Modal Handler
class FirstVisitModal {
    constructor() {
        this.modal = document.getElementById('firstVisitModal');
        this.authMessage = document.getElementById('authMessage');
        this.modalActions = document.getElementById('modalActions');
        this.cookieName = 'oak_tower_first_visit_shown';
        this.userAuthenticated = false;
        this.outsideClickListenerAdded = false;
    }

    async checkAndShow() {
        // Check if we've already shown the modal
        const hasSeenModal = getCookie(this.cookieName);
        if (hasSeenModal === 'true') {
            return;
        }

        // Check authentication status from the API
        try {
            const response = await fetch('/api/cached-status');
            if (response.ok) {
                const data = await response.json();
                this.userAuthenticated = data.user_authenticated || false;
            }
        } catch (error) {
            console.error('Error checking auth status:', error);
        }

        // Show the modal
        this.show();
    }

    show() {
        // Update content based on authentication status
        if (this.userAuthenticated) {
            this.authMessage.innerHTML = `
                <p><strong>You're signed in!</strong> You can customize which facilities to monitor in your settings.</p>
            `;
            this.modalActions.innerHTML = `
                <a href="/auth/settings/oak_tower_watcher" class="btn btn-primary">⚙️ Customize Settings</a>
                <button class="btn btn-dismiss" id="dismissModalBtn">Dismiss</button>
            `;
        } else {
            this.authMessage.innerHTML = `
                <p><strong>Want to customize?</strong> Sign in or register to set your own facilities to monitor and receive notifications when controllers come online!</p>
            `;
            this.modalActions.innerHTML = `
                <a href="/auth/register" class="btn btn-primary">📝 Register</a>
                <a href="/auth/login" class="btn btn-secondary">🔑 Sign In</a>
                <button class="btn btn-dismiss" id="dismissModalBtn">Dismiss</button>
            `;
        }

        // Show the modal
        this.modal.classList.add('show');
        
        // Use setTimeout to ensure DOM is updated before adding event listeners
        setTimeout(() => {
            // Add event listener to dismiss button
            const dismissBtn = document.getElementById('dismissModalBtn');
            if (dismissBtn) {
                dismissBtn.addEventListener('click', () => this.dismiss());
            }
            
            // Add event listener to close button
            const closeBtn = document.getElementById('modalCloseBtn');
            if (closeBtn) {
                closeBtn.addEventListener('click', () => this.dismiss());
            }
        }, 0);
        
        // Add event listener to close modal when clicking outside (only once)
        if (!this.outsideClickListenerAdded) {
            this.modal.addEventListener('click', (e) => {
                if (e.target === this.modal) {
                    this.dismiss();
                }
            });
            this.outsideClickListenerAdded = true;
        }
    }

    dismiss() {
        // Hide the modal
        this.modal.classList.remove('show');
        
        // Set cookie to remember we've shown it
        setCookie(this.cookieName, 'true', 365); // Remember for 1 year
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.oakStatus = new OAKTowerStatus();
    
    // Initialize and check first visit modal
    window.firstVisitModal = new FirstVisitModal();
    window.firstVisitModal.checkAndShow();
});
