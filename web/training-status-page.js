// Training Session Status Page JavaScript
class TrainingStatusPage {
    constructor() {
        this.statusData = null;
        this.isAuthenticated = false;
        this.refreshInterval = null;
        
        // Initialize the page
        this.init();
    }
    
    init() {
        // Check if user visited before
        this.checkFirstVisit();
        
        // Load initial status
        this.loadTrainingStatus();
        
        // Set up auto-refresh every 60 seconds
        this.refreshInterval = setInterval(() => {
            this.loadTrainingStatus();
        }, 60000);
        
        // Set up page visibility listener for immediate updates when returning from settings
        this.setupPageVisibilityListener();
        
        // Set up event listeners
        this.setupEventListeners();
    }
    
    checkFirstVisit() {
        const hasVisited = localStorage.getItem('training_status_visited');
        if (!hasVisited) {
            this.showFirstVisitModal();
            localStorage.setItem('training_status_visited', 'true');
        }
    }
    
    setupEventListeners() {
        // Modal close button
        const modalCloseBtn = document.getElementById('modalCloseBtn');
        if (modalCloseBtn) {
            modalCloseBtn.addEventListener('click', () => this.hideFirstVisitModal());
        }
        
        // Test notification button
        const testNotificationBtn = document.getElementById('test-notification-btn');
        if (testNotificationBtn) {
            testNotificationBtn.addEventListener('click', () => this.testNotification());
        }
        
        
        // Close modal when clicking outside
        const modal = document.getElementById('firstVisitModal');
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.hideFirstVisitModal();
                }
            });
        }
    }
    
    setupPageVisibilityListener() {
        // Refresh data when page becomes visible (e.g., returning from settings page)
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                console.log('Page became visible, refreshing training status...');
                this.loadTrainingStatus();
            }
        });
        
        // Also refresh when window gains focus (for cases where visibilitychange doesn't fire)
        window.addEventListener('focus', () => {
            console.log('Window gained focus, refreshing training status...');
            this.loadTrainingStatus();
        });
        
        // Listen for storage events (in case settings are changed in another tab)
        window.addEventListener('storage', (e) => {
            if (e.key && e.key.includes('training')) {
                console.log('Training-related storage change detected, refreshing...');
                this.loadTrainingStatus();
            }
        });
    }
    
    async loadTrainingStatus() {
        try {
            const response = await fetch('/api/training/status');
            const data = await response.json();
            
            if (response.ok) {
                this.statusData = data;
                this.isAuthenticated = data.user_info?.authenticated || false;
                this.updateUI(data);
            } else {
                console.error('Error loading training status:', data);
                this.showError('Failed to load training status');
            }
        } catch (error) {
            console.error('Network error:', error);
            this.showError('Network error loading training status');
        }
    }
    
    updateUI(data) {
        this.updateMainStatus(data);
        this.updateCurrentSessions(data.user_sessions || []);
        this.updateMonitoredRatings(data.user_info?.monitored_ratings || []);
        this.updateServiceStats(data);
        this.updateLastCheck(data.timestamp);
    }
    
    updateMainStatus(data) {
        const indicator = document.getElementById('main-status-indicator');
        const title = document.getElementById('status-title');
        const description = document.getElementById('status-description');
        
        if (!indicator || !title || !description) return;
        
        const userInfo = data.user_info || {};
        const serviceStatus = data.service_status?.training_monitoring || {};
        
        if (!this.isAuthenticated) {
            indicator.className = 'status-indicator-large status-warning';
            title.textContent = 'Authentication Required';
            description.textContent = 'Please log in to configure training session monitoring';
        } else if (!userInfo.settings_configured) {
            indicator.className = 'status-indicator-large status-warning';
            title.textContent = 'Configuration Required';
            description.textContent = 'Please configure your training session settings';
        } else if (!userInfo.session_key_configured) {
            indicator.className = 'status-indicator-large status-warning';
            title.textContent = 'Session Key Required';
            description.textContent = 'Please configure your OAK ARTCC PHP session key';
        } else if (!userInfo.notifications_enabled) {
            indicator.className = 'status-indicator-large status-warning';
            title.textContent = 'Notifications Disabled';
            description.textContent = 'Training session notifications are disabled';
        } else if (serviceStatus.success) {
            indicator.className = 'status-indicator-large status-online';
            title.textContent = 'Monitoring Active';
            description.textContent = `Monitoring ${userInfo.monitored_ratings?.length || 0} rating patterns`;
        } else {
            indicator.className = 'status-indicator-large status-offline';
            title.textContent = 'Service Error';
            description.textContent = serviceStatus.error || 'Training monitoring service error';
        }
    }
    
    updateCurrentSessions(sessions) {
        const container = document.getElementById('current-sessions');
        if (!container) return;
        
        if (sessions.length === 0) {
            container.innerHTML = '<div class="no-data">No training sessions found matching your monitored ratings</div>';
            return;
        }
        
        const sessionElements = sessions.map(session => {
            const sessionDate = new Date(session.session_date + 'T00:00:00');
            const isToday = this.isToday(sessionDate);
            const isTomorrow = this.isTomorrow(sessionDate);
            
            let dateLabel = session.session_date;
            if (isToday) dateLabel += ' (Today)';
            else if (isTomorrow) dateLabel += ' (Tomorrow)';
            
            return `
                <div class="controller-item session-item">
                    <div class="session-info">
                        <div class="session-header">
                            <span class="session-rating rating-badge">${session.rating_pattern}</span>
                            <span class="session-date">${dateLabel}</span>
                        </div>
                        <div class="session-details">
                            <div class="session-student">
                                <strong>${session.student_name}</strong>
                                ${session.student_rating ? `<span class="student-rating">(${session.student_rating})</span>` : ''}
                            </div>
                            <div class="session-instructor">Instructor: ${session.instructor_name}</div>
                            <div class="session-module">${session.module_name}</div>
                            <div class="session-time">🕐 ${session.session_time}</div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        
        container.innerHTML = sessionElements;
    }
    
    updateMonitoredRatings(ratings) {
        const container = document.getElementById('monitored-ratings');
        if (!container) return;
        
        if (ratings.length === 0) {
            container.innerHTML = '<div class="no-data">No ratings configured for monitoring</div>';
            return;
        }
        
        const ratingElements = ratings.map(rating => 
            `<div class="controller-item rating-item">
                <span class="rating-badge">${rating}</span>
            </div>`
        ).join('');
        
        container.innerHTML = ratingElements;
    }
    
    async loadNotificationHistory() {
        if (!this.isAuthenticated) return;
        
        try {
            const response = await fetch('/api/training/notification-history');
            const data = await response.json();
            
            if (response.ok) {
                this.updateRecentNotifications(data.notifications || []);
            }
        } catch (error) {
            console.error('Error loading notification history:', error);
        }
    }
    
    updateRecentNotifications(notifications) {
        const container = document.getElementById('recent-notifications');
        if (!container) return;
        
        if (notifications.length === 0) {
            container.innerHTML = '<div class="no-data">No recent notifications</div>';
            return;
        }
        
        // Show last 5 notifications
        const recentNotifications = notifications.slice(0, 5);
        
        const notificationElements = recentNotifications.map(notification => {
            const sentDate = new Date(notification.notification_sent_at);
            const timeAgo = this.timeAgo(sentDate);
            
            return `
                <div class="controller-item notification-item">
                    <div class="notification-info">
                        <div class="notification-header">
                            <span class="notification-rating rating-badge">${notification.matching_rating}</span>
                            <span class="notification-time">${timeAgo}</span>
                        </div>
                        <div class="notification-details">
                            <div class="notification-student">${notification.student_name}</div>
                            <div class="notification-module">${notification.module_name}</div>
                            <div class="notification-date">${notification.session_date} ${notification.session_time}</div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        
        container.innerHTML = notificationElements;
    }
    
    updateServiceStats(data) {
        const serviceStatus = data.service_status?.training_monitoring || {};
        const serviceInfo = data.service_status?.service_info || {};
        
        // Monitoring status
        const monitoringStatus = document.getElementById('monitoring-status');
        if (monitoringStatus) {
            const isRunning = serviceInfo.running;
            monitoringStatus.textContent = isRunning ? 'Active' : 'Stopped';
            monitoringStatus.className = `stat-value ${isRunning ? 'status-online' : 'status-offline'}`;
        }
        
        // Check interval
        const checkInterval = document.getElementById('check-interval');
        if (checkInterval) {
            const hours = serviceInfo.check_interval_hours || 1;
            checkInterval.textContent = hours === 1 ? '1 hour' : `${hours} hours`;
        }
        
        // Session key status
        const sessionKeyStatus = document.getElementById('session-key-status');
        if (sessionKeyStatus && this.isAuthenticated) {
            const userInfo = data.user_info || {};
            if (!userInfo.session_key_configured) {
                sessionKeyStatus.textContent = 'Not configured';
                sessionKeyStatus.className = 'stat-value status-warning';
            } else {
                sessionKeyStatus.textContent = 'Configured';
                sessionKeyStatus.className = 'stat-value status-online';
            }
        }
    }
    
    updateLastCheck(timestamp) {
        const lastCheck = document.getElementById('last-check');
        if (lastCheck && timestamp) {
            const checkTime = new Date(timestamp);
            lastCheck.textContent = this.formatTime(checkTime);
        }
    }
    
    async testNotification() {
        if (!this.isAuthenticated) {
            this.showError('Please log in to test notifications');
            return;
        }
        
        const btn = document.getElementById('test-notification-btn');
        const btnText = document.getElementById('test-notification-text');
        
        if (!btn || !btnText) return;
        
        // Update button to show loading
        btn.disabled = true;
        btnText.textContent = '⏳ Testing...';
        
        try {
            const response = await fetch('/api/test-pushover', { method: 'POST' });
            const data = await response.json();
            
            if (response.ok && data.success) {
                this.showSuccess('Test notification sent successfully!');
            } else {
                this.showError(data.message || 'Failed to send test notification');
            }
        } catch (error) {
            console.error('Error sending test notification:', error);
            this.showError('Network error sending test notification');
        } finally {
            // Reset button
            btn.disabled = false;
            btnText.textContent = '🔔 Test Notification';
        }
    }
    
    
    showFirstVisitModal() {
        const modal = document.getElementById('firstVisitModal');
        const authMessage = document.getElementById('authMessage');
        const modalActions = document.getElementById('modalActions');
        
        if (!modal || !authMessage || !modalActions) return;
        
        // Update message based on authentication status
        if (this.isAuthenticated) {
            authMessage.innerHTML = 'You are logged in and ready to configure training session monitoring.';
            modalActions.innerHTML = `
                <a href="/auth/training-session-settings" class="btn btn-primary">Configure Settings</a>
                <button class="btn btn-secondary" id="modalStartBtn">Start Monitoring</button>
            `;
        } else {
            authMessage.innerHTML = 'Please log in to configure personalized training session monitoring and receive notifications.';
            modalActions.innerHTML = `
                <a href="/auth/login" class="btn btn-primary">Login</a>
                <a href="/auth/register" class="btn btn-secondary">Register</a>
            `;
        }
        
        modal.style.display = 'flex';
        
        // Add event listener for start monitoring button
        const startBtn = document.getElementById('modalStartBtn');
        if (startBtn) {
            startBtn.addEventListener('click', () => this.hideFirstVisitModal());
        }
    }
    
    hideFirstVisitModal() {
        const modal = document.getElementById('firstVisitModal');
        if (modal) {
            modal.style.display = 'none';
        }
        
        // Load notification history now that modal is closed
        this.loadNotificationHistory();
    }
    
    showError(message) {
        console.error('Training Status Error:', message);
        // You could implement a toast notification system here
        alert(message); // Simple fallback
    }
    
    showSuccess(message) {
        console.log('Training Status Success:', message);
        // You could implement a toast notification system here
        alert(message); // Simple fallback
    }
    
    // Utility functions
    isToday(date) {
        const today = new Date();
        return date.toDateString() === today.toDateString();
    }
    
    isTomorrow(date) {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        return date.toDateString() === tomorrow.toDateString();
    }
    
    timeAgo(date) {
        const now = new Date();
        const diff = now - date;
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);
        
        if (days > 0) return `${days}d ago`;
        if (hours > 0) return `${hours}h ago`;
        if (minutes > 0) return `${minutes}m ago`;
        return 'Just now';
    }
    
    formatTime(date) {
        return date.toLocaleString();
    }
    
    cleanup() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
    }
}

// Initialize the page when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const trainingStatusPage = new TrainingStatusPage();
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        trainingStatusPage.cleanup();
    });
});