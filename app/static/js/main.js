// Chat functionality
function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    
    if (!message) return;
    
    addMessageToChat('user', message);
    input.value = '';
    
    // Show loading
    addMessageToChat('ai', 'Thinking...');
    
    fetch('/api/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: message })
    })
    .then(response => response.json())
    .then(data => {
        // Remove loading message
        const chatMessages = document.getElementById('chat-messages');
        chatMessages.removeChild(chatMessages.lastChild);
        
        if (data.status === 'success') {
            addMessageToChat('ai', data.response);
        } else {
            addMessageToChat('ai', 'Error: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        addMessageToChat('ai', 'Sorry, there was an error processing your request.');
    });
}

function addMessageToChat(sender, message) {
    const chatMessages = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${sender}-message`;
    messageDiv.textContent = message;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function handleKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

function testGeminiAPI() {
    const input = document.getElementById('chat-input');
    input.value = 'Hello! Can you introduce yourself?';
    sendMessage();
}

function showProfile() {
    alert('Profile information is displayed in the sidebar!');
}