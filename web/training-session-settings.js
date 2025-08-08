// Training session settings page JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Auto-scroll to alerts
    const alerts = document.querySelectorAll('.alert');
    if (alerts.length > 0) {
        alerts[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    
    // Handle session key test form submission
    const testForm = document.getElementById('test-session-form');
    if (testForm) {
        testForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const submitBtn = document.getElementById('test-submit-btn');
            const testResult = document.getElementById('test-result');
            const sessionKeyInput = document.getElementById('test-php-session-key');
            
            // Disable button and show loading state
            submitBtn.disabled = true;
            submitBtn.textContent = 'Testing...';
            testResult.style.display = 'none';
            
            try {
                const response = await fetch('/api/training/test-session-key', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        php_session_key: sessionKeyInput.value
                    })
                });
                
                const data = await response.json();
                
                if (response.ok && data.success) {
                    // Show result near the button
                    testResult.innerHTML = `
                        <div class="alert alert-${data.valid ? 'success' : 'danger'}">
                            ${data.valid ? '✅ Session key is valid and working!' : '❌ Session key test failed'}
                            <br><small>${data.message}</small>
                        </div>
                    `;
                } else {
                    testResult.innerHTML = `
                        <div class="alert alert-danger">
                            ❌ Test failed: ${data.message || data.error || 'Unknown error'}
                        </div>
                    `;
                }
            } catch (error) {
                console.error('Test error:', error);
                testResult.innerHTML = `
                    <div class="alert alert-danger">
                        ❌ Network error occurred while testing session key
                    </div>
                `;
            } finally {
                // Re-enable button and show result
                submitBtn.disabled = false;
                submitBtn.textContent = 'Test Session Key';
                testResult.style.display = 'block';
            }
        });
    }
});