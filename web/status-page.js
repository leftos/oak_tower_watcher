// Status page JavaScript functionality

class OAKTowerStatus {
    constructor() {
        this.autoRefreshEnabled = true;
        this.refreshInterval = 30000; // 30 seconds
        this.refreshTimer = null;
        this.lastUpdateTime = null;
        
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

        // Toggle auto-refresh button
        const toggleAutoRefreshBtn = document.getElementById('toggle-auto-refresh-btn');
        if (toggleAutoRefreshBtn) {
            toggleAutoRefreshBtn.addEventListener('click', () => this.toggleAutoRefresh());
        }

        // Test notification button
        const testNotificationBtn = document.getElementById('test-notification-btn');
        if (testNotificationBtn) {
            testNotificationBtn.addEventListener('click', () => this.testStatusNotification());
        }
    }

    async loadStatus() {
        try {
            // Show loading state
            this.showLoadingState();
            
            // For now, we'll simulate the API call with mock data
            // In a real implementation, this would call the actual API
            const status = await this.fetchStatus();
            
            this.updateUI(status);
            this.lastUpdateTime = new Date();
            
        } catch (error) {
            console.error('Error loading status:', error);
            this.showErrorState(error.message);
        }
    }

    async fetchStatus() {
        try {
            const response = await fetch('/api/status');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Transform API response to match our UI expectations
            return {
                status: data.status,
                mainControllers: data.main_controllers || [],
                supportingAbove: data.supporting_above || [],
                supportingBelow: data.supporting_below || [],
                config: data.config || {}
            };
            
        } catch (error) {
            console.error('API fetch error:', error);
            throw error;
        }
    }

    updateUI(status) {
        this.updateMainStatus(status);
        this.updateControllers(status);
        this.updateServiceStats(status);
        this.updateUserConfigStatus(status);
    }

    updateMainStatus(status) {
        const indicator = document.getElementById('main-status-indicator');
        const title = document.getElementById('status-title');
        const description = document.getElementById('status-description');

        // Clear existing classes
        indicator.className = 'status-indicator-large';

        switch (status.status) {
            case 'main_facility_and_supporting_above_online':
                indicator.classList.add('status-online');
                indicator.textContent = '🟣';
                title.textContent = 'Full Coverage Online';
                description.textContent = 'Main facility and supporting facilities are active';
                break;
            case 'main_facility_online':
                indicator.classList.add('status-online');
                indicator.textContent = '🟢';
                title.textContent = 'Main Facility Online';
                description.textContent = 'Main facility controller is active';
                break;
            case 'supporting_above_online':
                indicator.classList.add('status-partial');
                indicator.textContent = '🟡';
                title.textContent = 'Supporting Facility Online';
                description.textContent = 'Main facility offline, but supporting facility active';
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
        this.updateControllerSection('main-controllers', status.mainControllers, 'No main facility controllers online');
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
                <div class="controller-name">${controller.name || controller.cid}</div>
                <div class="controller-details">
                    <div>CID: ${controller.cid || 'Unknown'}</div>
                    <div>Online: ${this.formatDuration(controller.logon_time)}</div>
                </div>
            </div>
        `).join('');
    }

    updateServiceStats(status) {
        document.getElementById('monitoring-status').textContent = 'Active';
        
        if (status.config && status.config.check_interval) {
            document.getElementById('check-interval').textContent = `${status.config.check_interval} seconds`;
        } else {
            document.getElementById('check-interval').textContent = '30 seconds';
        }
    }

    updateUserConfigStatus(status) {
        // Check if there's an existing user config indicator
        let configIndicator = document.getElementById('user-config-indicator');
        
        if (status.using_user_config) {
            // Create or update the indicator if user config is being used
            if (!configIndicator) {
                configIndicator = document.createElement('div');
                configIndicator.id = 'user-config-indicator';
                configIndicator.className = 'user-config-badge';
                
                // Insert after the service stats
                const serviceStatsCard = document.querySelector('.info-card');
                if (serviceStatsCard && serviceStatsCard.parentNode) {
                    const newCard = document.createElement('div');
                    newCard.className = 'info-card user-config-card';
                    newCard.appendChild(configIndicator);
                    serviceStatsCard.parentNode.insertBefore(newCard, serviceStatsCard.nextSibling);
                }
            }
            
            configIndicator.innerHTML = `
                <h3>🎯 Personal Configuration Active</h3>
                <div class="user-config-info">
                    <p><strong>You're using your custom facility patterns!</strong></p>
                    <div class="pattern-summary">
                        <div class="pattern-group">
                            <strong>Main Facility:</strong>
                            <span class="pattern-count">${status.facility_patterns?.main_facility?.length || 0} patterns</span>
                        </div>
                        <div class="pattern-group">
                            <strong>Supporting Above:</strong>
                            <span class="pattern-count">${status.facility_patterns?.supporting_above?.length || 0} patterns</span>
                        </div>
                        <div class="pattern-group">
                            <strong>Supporting Below:</strong>
                            <span class="pattern-count">${status.facility_patterns?.supporting_below?.length || 0} patterns</span>
                        </div>
                    </div>
                    <div class="config-actions">
                        <a href="/auth/settings/oak_tower_watcher" class="btn btn-secondary">⚙️ Edit Configuration</a>
                    </div>
                </div>
            `;
        } else {
            // Remove the indicator if using default config
            if (configIndicator) {
                const parentCard = configIndicator.closest('.user-config-card');
                if (parentCard) {
                    parentCard.remove();
                }
            }
        }
    }

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
        if (this.lastUpdateTime) {
            const lastCheck = document.getElementById('last-check');
            const now = new Date();
            const diff = now - this.lastUpdateTime;
            const seconds = Math.floor(diff / 1000);
            
            if (seconds < 60) {
                lastCheck.textContent = `${seconds} seconds ago`;
            } else {
                const minutes = Math.floor(seconds / 60);
                lastCheck.textContent = `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
            }
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
        
        refreshBtn.textContent = '🔄 Refreshing...';
        
        this.loadStatus().then(() => {
            refreshBtn.textContent = originalText;
            
            // Show success message briefly
            const container = document.querySelector('.status-section');
            const successDiv = document.createElement('div');
            successDiv.className = 'success-message';
            successDiv.textContent = 'Status refreshed successfully';
            container.appendChild(successDiv);
            
            setTimeout(() => successDiv.remove(), 3000);
        });
    }

    toggleAutoRefresh() {
        const btn = document.getElementById('auto-refresh-text');
        
        if (this.autoRefreshEnabled) {
            this.autoRefreshEnabled = false;
            this.stopAutoRefresh();
            btn.textContent = '▶️ Resume Auto-refresh';
        } else {
            this.autoRefreshEnabled = true;
            this.startAutoRefresh();
            btn.textContent = '⏸️ Pause Auto-refresh';
        }
    }

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
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.oakStatus = new OAKTowerStatus();
});
