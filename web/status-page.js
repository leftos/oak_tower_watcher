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
                description.textContent = 'Tower and supporting facilities are active';
                break;
            case 'main_facility_online':
                indicator.classList.add('status-online');
                indicator.textContent = '🟢';
                title.textContent = 'Tower Online';
                description.textContent = 'Tower controller is active';
                break;
            case 'supporting_above_online':
                indicator.classList.add('status-partial');
                indicator.textContent = '🟡';
                title.textContent = 'Supporting Facility Online';
                description.textContent = 'Tower offline, but supporting facility active';
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
        this.updateControllerSection('main-controllers', status.mainControllers, 'No tower controllers online');
        this.updateControllerSection('supporting-above-controllers', status.supportingAbove, 'No supporting controllers online');
        this.updateControllerSection('supporting-below-controllers', status.supportingBelow, 'No ground/delivery controllers online');
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
                <div class="controller-name">${controller.name || 'Unknown Controller'}</div>
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
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.oakStatus = new OAKTowerStatus();
});
