// @ts-nocheck

let chatMessages = [];
let session_id = null;
let weatherUpdateInterval = null;

// Weather update interval (5 minutes)
const WEATHER_UPDATE_INTERVAL = 5 * 60 * 1000;

// Debug flag
const DEBUG = true;

function debugLog(message, data = null) {
    if (DEBUG && console) {
        if (data) {
            console.log(`[Debug] ${message}`, data);
        } else {
            console.log(`[Debug] ${message}`);
        }
    }
}

// Close suggestions when clicking outside
document.addEventListener('click', function(event) {
    const suggestionsDiv = document.getElementById('country-suggestions');
    if (!event.target.closest('#country-input') && !event.target.closest('#country-suggestions')) {
        suggestionsDiv.classList.add('hidden');
    }
});

// Country input handler with instant suggestions
document.getElementById('country-input').addEventListener('keyup', async function(event) {
    const input = this.value.trim();

    if (input.length >= 2) { // Minimum 2 characters for suggestions
        this.classList.add('input-loading');

        try {
            const response = await fetch('/verify_country', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ country: input })
            });
            const data = await response.json();
            handleCountryVerification(data.verification);
        } catch (error) {
            debugLog('Error in country verification:', error);
        } finally {
            this.classList.remove('input-loading');
        }
    } else {
        document.getElementById('country-suggestions').classList.add('hidden');
        this.classList.remove('input-loading');
    }
});

async function updateWeatherAndInfo(country) {
    try {
        debugLog('Updating weather and country info for:', country);
        
        document.getElementById('weather-content').classList.add('hidden');
        document.getElementById('weather-loading').classList.remove('hidden');
        document.getElementById('country-content').classList.add('hidden');
        document.getElementById('country-loading').classList.remove('hidden');

        const response = await fetch('/get_country_info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ country })
        });

        const data = await response.json();
        debugLog('Received country info:', data);

        if (data.status === 'success') {
            // Update weather
            if (data.weather) {
                document.getElementById('weather-temp').textContent = `${data.weather.temperature}°C`;
                document.getElementById('weather-desc').textContent = data.weather.condition;
                document.getElementById('weather-location').textContent = data.weather.city;
                document.getElementById('weather-time').textContent = `Local time: ${data.weather.local_time}`;
                document.getElementById('weather-icon').src = 
                    `https://openweathermap.org/img/wn/${data.weather.icon}@2x.png`;
                
                document.getElementById('weather-loading').classList.add('hidden');
                document.getElementById('weather-content').classList.remove('hidden');
            }

            // Update country info
            if (data.country_info) {
                document.getElementById('country-details').innerHTML = data.country_info
                    .split('\n')
                    .map(line => `<div class="info-item">${line}</div>`)
                    .join('');
                
                document.getElementById('country-loading').classList.add('hidden');
                document.getElementById('country-content').classList.remove('hidden');
            }
        }
    } catch (error) {
        debugLog('Error updating weather and country info:', error);
        document.getElementById('weather-loading').textContent = 'Error loading weather data';
        document.getElementById('country-loading').textContent = 'Error loading country information';
    }
}

function handleCountryVerification(verification) {
    const suggestionsDiv = document.getElementById('country-suggestions');
    const suggestionsList = suggestionsDiv.querySelector('ul');
    suggestionsList.innerHTML = ''; // Clear previous suggestions

    if (verification.startsWith('Did you mean:')) {
        const suggestions = verification.substring(14).split(',');
        suggestions.forEach(suggestion => {
            const trimmedSuggestion = suggestion.trim().replace('?', '');
            const li = document.createElement('li');
            li.className = 'suggestion-item flex items-center gap-2';
            li.innerHTML = trimmedSuggestion;
            li.onclick = function() { selectCountry(trimmedSuggestion); };
            suggestionsList.appendChild(li);
        });
        suggestionsDiv.classList.remove('hidden');
    } else if (!verification.includes('Invalid')) {
        document.getElementById('country-input').value = verification;
        suggestionsDiv.classList.add('hidden');
    } else {
        suggestionsDiv.classList.add('hidden');
    }
}

function selectCountry(country) {
    document.getElementById('country-input').value = country;
    document.getElementById('country-suggestions').classList.add('hidden');
}

// Chat handlers
document.getElementById('start-chat').addEventListener('click', async function() {
    const country = document.getElementById('country-input').value.trim();
    const gender = document.getElementById('gender-select').value;

    if (!country) {
        alert('Please enter a country');
        return;
    }

    try {
        document.getElementById('start-chat').classList.add('loading');
        debugLog('Starting chat with:', { country, gender, session_id });

        const response = await fetch('/start_chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ country, gender, session_id })
        });

        const data = await response.json();
        debugLog('Server response:', data);

        if (data.status === 'error') {
            throw new Error(data.error);
        }

        document.getElementById('avatar').src = data.avatar_url;
        document.getElementById('setup-container').classList.add('hidden');
        document.getElementById('chat-container').classList.remove('hidden');

        if (!session_id) {
            session_id = data.session_id;
            localStorage.setItem('session_id', session_id);
        }

        if (data.message) {
            debugLog('Adding initial message:', data.message);
            setTimeout(() => {
                addMessage('assistant', data.message, true);
                const messages = document.getElementById('messages');
                messages.scrollTop = messages.scrollHeight;
            }, 100);
        }

        chatMessages = data.messages;

        // Start weather updates
        await updateWeatherAndInfo(country);
        weatherUpdateInterval = setInterval(() => updateWeatherAndInfo(country), WEATHER_UPDATE_INTERVAL);

    } catch (error) {
        debugLog('Error:', error);
        alert('Error starting chat: ' + error.message);
    } finally {
        document.getElementById('start-chat').classList.remove('loading');
    }
});

document.getElementById('back-button').addEventListener('click', function() {
    document.getElementById('chat-container').classList.add('hidden');
    document.getElementById('setup-container').classList.remove('hidden');
    document.getElementById('messages').innerHTML = '';
    chatMessages = [];
    
    // Clear weather update interval
    if (weatherUpdateInterval) {
        clearInterval(weatherUpdateInterval);
    }
});

document.getElementById('send-message').addEventListener('click', sendMessage);
document.getElementById('user-input').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') sendMessage();
});

async function sendMessage() {
    const input = document.getElementById('user-input');
    const message = input.value.trim();

    if (message) {
        input.value = '';
        addMessage('user', message);

        try {
            document.getElementById('send-message').classList.add('loading');
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_input: message,
                    session_id: session_id
                })
            });

            const data = await response.json();
            if (data.status === 'error') {
                throw new Error(data.error);
            }

            addMessage('assistant', data.reply);
            chatMessages = data.messages;

        } catch (error) {
            addMessage('system', 'Error: Could not send message');
        } finally {
            document.getElementById('send-message').classList.remove('loading');
        }
    }
}

function addMessage(role, content, isInitial = false) {
    const messages = document.getElementById('messages');
    const messageDiv = document.createElement('div');
    
    if (role === 'assistant' && isInitial) {
        messageDiv.className = `p-3 rounded-lg bg-gray-100 mr-12 initial-message`;
    } else {
        messageDiv.className = `p-3 rounded-lg ${role === 'user' ? 'bg-blue-100 ml-12' : 'bg-gray-100 mr-12'}`;
    }
    
    messageDiv.textContent = content;
    messages.appendChild(messageDiv);
    messages.scrollTop = messages.scrollHeight;
}

// On page load
window.onload = () => {
    session_id = localStorage.getItem('session_id');
    debugLog('Session ID from storage:', session_id);
};

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (weatherUpdateInterval) {
        clearInterval(weatherUpdateInterval);
    }
});