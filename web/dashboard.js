// Dashboard JavaScript functionality
document.addEventListener('DOMContentLoaded', function() {
    const testBtn = document.getElementById('test-pushover-btn');
    
    if (testBtn) {
        testBtn.addEventListener('click', async function() {
            // Disable button and show loading state
            const originalText = testBtn.textContent;
            testBtn.disabled = true;
            testBtn.textContent = 'Sending...';
            testBtn.classList.remove('btn-success');
            testBtn.classList.add('btn-secondary');
            
            try {
                const response = await fetch('/api/test-pushover', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'same-origin'  // Include session cookies
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Success - show green and success message
                    testBtn.textContent = '✓ Sent!';
                    testBtn.classList.remove('btn-secondary');
                    testBtn.classList.add('btn-success');
                    
                    // Show success message
                    showNotification(result.message, 'success');
                    
                    // Reset button after 3 seconds
                    setTimeout(() => {
                        testBtn.textContent = originalText;
                        testBtn.disabled = false;
                    }, 3000);
                } else {
                    // Error - show red and error message
                    testBtn.textContent = '✗ Failed';
                    testBtn.classList.remove('btn-secondary');
                    testBtn.classList.add('btn-danger');
                    
                    // Show error message
                    showNotification(result.message || result.error, 'error');
                    
                    // Reset button after 3 seconds
                    setTimeout(() => {
                        testBtn.textContent = originalText;
                        testBtn.classList.remove('btn-danger');
                        testBtn.classList.add('btn-success');
                        testBtn.disabled = false;
                    }, 3000);
                }
            } catch (error) {
                console.error('Error testing pushover:', error);
                
                // Network error - show red and error message
                testBtn.textContent = '✗ Error';
                testBtn.classList.remove('btn-secondary');
                testBtn.classList.add('btn-danger');
                
                showNotification('Network error occurred while testing notification', 'error');
                
                // Reset button after 3 seconds
                setTimeout(() => {
                    testBtn.textContent = originalText;
                    testBtn.classList.remove('btn-danger');
                    testBtn.classList.add('btn-success');
                    testBtn.disabled = false;
                }, 3000);
            }
        });
    }
});

function showNotification(message, type) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 5px;
        color: white;
        font-weight: 500;
        z-index: 1000;
        max-width: 400px;
        word-wrap: break-word;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    `;
    
    // Set background color based on type
    if (type === 'success') {
        notification.style.backgroundColor = '#22c55e';
    } else if (type === 'error') {
        notification.style.backgroundColor = '#ef4444';
    } else {
        notification.style.backgroundColor = '#3b82f6';
    }
    
    notification.textContent = message;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Animate in
    notification.style.transform = 'translateX(100%)';
    notification.style.transition = 'transform 0.3s ease-in-out';
    setTimeout(() => {
        notification.style.transform = 'translateX(0)';
    }, 10);
    
    // Remove after 5 seconds
    setTimeout(() => {
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 5000);
}