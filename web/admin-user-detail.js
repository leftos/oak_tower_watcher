function toggleBanForm() {
    const form = document.getElementById('ban-form');
    form.classList.toggle('hidden');
}


function syntaxHighlight(json) {
    json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
        var cls = 'json-number';
        if (/^"/.test(match)) {
            if (/:$/.test(match)) {
                cls = 'json-key';
            } else {
                cls = 'json-string';
            }
        } else if (/true|false/.test(match)) {
            cls = 'json-boolean';
        } else if (/null/.test(match)) {
            cls = 'json-null';
        }
        return '<span class="' + cls + '">' + match + '</span>';
    });
}

// Initialize event listeners when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Handle button actions with data-action
    document.addEventListener('click', function(e) {
        const action = e.target.getAttribute('data-action');
        
        if (action === 'toggle-ban-form') {
            e.preventDefault();
            toggleBanForm();
            return;
        } else if (action === 'unban') {
            if (!confirm('Are you sure you want to unban this user?')) {
                e.preventDefault();
                return false;
            }
            return;
        } else if (action === 'ban') {
            if (!confirm('Are you sure you want to ban this user? This will prevent them from logging in.')) {
                e.preventDefault();
                return false;
            }
            return;
        }
    });
    
    // Syntax highlight JSON
    const jsonContainers = document.querySelectorAll('.json-container');
    jsonContainers.forEach(container => {
        const text = container.textContent;
        try {
            const parsed = JSON.parse(text);
            const highlighted = syntaxHighlight(JSON.stringify(parsed, null, 2));
            container.innerHTML = highlighted;
        } catch (e) {
            // If JSON parsing fails, leave as is
        }
    });
});