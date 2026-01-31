const chatBox = document.getElementById('chat-box');
const messageInput = document.getElementById('message-input');
const chatWidget = document.getElementById('chat-widget');

// --- NOVO: UPRAVLJANJE SESIJOM ---
function getSessionId() {
    // Proveravamo da li korisnik već ima ID u memoriji browsera
    let sessionId = localStorage.getItem('chat_session_id');
    if (!sessionId) {
        // Ako nema, generišemo novi nasumični ID (npr. 'sess-17482...')
        sessionId = 'sess-' + Date.now() + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('chat_session_id', sessionId);
    }
    return sessionId;
}

// 1. FUNKCIJA ZA OTVARANJE/ZATVARANJE CHATA
function toggleChat() {
    chatWidget.classList.toggle('show-chat');
    if (chatWidget.classList.contains('show-chat')) {
        messageInput.focus();
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}

// 2. UČITAVANJE ISTORIJE (Sada šaljemo session_id)
async function loadChatHistory() {
    const sessionId = getSessionId();
    try {
        // Šaljemo ID kao deo linka (query parameter)
        const response = await fetch(`/history?session_id=${sessionId}`);
        const messages = await response.json();
        chatBox.innerHTML = '';
        messages.forEach(msg => {
            appendMessage(msg.sender, msg.content, false);
        });
    } catch (error) {
        console.error("Greška pri učitavanju istorije:", error);
    }
}

// 3. SLANJE PORUKE (Sada šaljemo session_id)
async function sendMessage() {
    const message = messageInput.value.trim();
    if (message === "") return;

    appendMessage('user', message);
    messageInput.value = '';
    const loadingId = appendMessage('bot', 'Razmišljam...', true); 
    
    const sessionId = getSessionId(); // Uzimamo ID

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            // Šaljemo poruku I session_id
            body: JSON.stringify({ 
                message: message, 
                session_id: sessionId 
            })
        });
        const data = await response.json();
        updateMessage(loadingId, data.response);
    } catch (error) {
        updateMessage(loadingId, "Izvini, došlo je do greške.");
    }
}

// 4. RENDEROVANJE (Ostaje isto)
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

messageInput.addEventListener('keypress', function (e) {
    if (e.key === 'Enter') { sendMessage(); }
});

window.onload = loadChatHistory;