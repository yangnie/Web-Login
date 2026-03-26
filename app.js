const API_BASE_URL = window.location.protocol + '//' + window.location.hostname + ':8000'; // Explicitly target API server on port 8000

async function makeRequest(url, method = 'GET', body = null, tokenRequired = true) {
    const apiAuthToken = localStorage.getItem('apiAuthToken'); // Get token from local storage
    const headers = {
        'Content-Type': 'application/json',
    };

    if (tokenRequired) {
        if (!apiAuthToken) {
            alert('Please enter your API Authentication Token in the Auth page and save it!');
            return null;
        }
        headers['Authorization'] = `Bearer ${apiAuthToken}`;
    }

    const config = {
        method: method,
        headers: headers,
    };

    if (body) {
        config.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(url, config);
        const data = await response.json();
        return { status: response.status, data: data };
    } catch (error) {
        console.error('Network or parsing error:', error);
        return { status: 500, data: { error: 'Network or JSON parsing error: ' + error.message } };
    }
}

function displayResponse(elementId, response) {
    const responseDiv = document.getElementById(elementId);
    if (response) {
        responseDiv.innerHTML = `<p><strong>Status:</strong> ${response.status}</p><pre>${JSON.stringify(response.data, null, 2)}</pre>`;
        if (response.status >= 400) {
            responseDiv.classList.add('error');
        } else {
            responseDiv.classList.remove('error');
        }
    } else {
        responseDiv.innerHTML = '<p class="error">No response received.</p>';
        responseDiv.classList.add('error');
    }
}
