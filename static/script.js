const chatBox = document.getElementById('chat-box');
const messageInput = document.getElementById('message-input');
const chatWidget = document.getElementById('chat-widget');

// 1. FUNKCIJA ZA OTVARANJE/ZATVARANJE CHATA
function toggleChat() {
    // Dodajemo ili sklanjamo klasu "show-chat"
    chatWidget.classList.toggle('show-chat');
    
    // Ako se otvorio, fokusiraj input polje i skroluj na dno
    if (chatWidget.classList.contains('show-chat')) {
        messageInput.focus();
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}

// 2. UČITAVANJE ISTORIJE
async function loadChatHistory() {
    try {
        const response = await fetch('/history');
        const messages = await response.json();
        chatBox.innerHTML = '';
        messages.forEach(msg => {
            appendMessage(msg.sender, msg.content, false);
        });
    } catch (error) {
        console.error("Greška pri učitavanju istorije:", error);
    }
}

// 3. SLANJE PORUKE
async function sendMessage() {
    const message = messageInput.value.trim();
    if (message === "") return;

    appendMessage('user', message);
    messageInput.value = '';

    const loadingId = appendMessage('bot', 'Razmišljam...', true); 

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        });
        const data = await response.json();
        updateMessage(loadingId, data.response);
    } catch (error) {
        updateMessage(loadingId, "Izvini, došlo je do greške.");
    }
}

// 4. RENDEROVANJE (Isto kao pre)
function appendMessage(sender, text, isLoading = false) {
    const messageDiv = document.createElement('div');
    const uniqueId = 'msg-' + Date.now() + Math.random().toString(36).substr(2, 9);
    
    messageDiv.id = uniqueId;
    const senderClass = sender.toLowerCase() === 'user' ? 'user-msg' : 'bot-msg';
    messageDiv.classList.add('message', senderClass);

    if (senderClass === 'bot-msg' && !isLoading) {
        messageDiv.innerHTML = marked.parse(text);
    } else {
        messageDiv.innerText = text;
    }

    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
    return uniqueId;
}

function updateMessage(id, newText) {
    const messageDiv = document.getElementById(id);
    if (messageDiv) {
        messageDiv.innerHTML = marked.parse(newText);
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}

// Enter za slanje
messageInput.addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

// Učitaj istoriju odmah
window.onload = loadChatHistory;