// Funkcija za otvaranje i zatvaranje četa
function toggleChat() {
    const chatWidget = document.getElementById('chat-widget');
    chatWidget.classList.toggle('hidden');
}

// Funkcija za slanje poruke
async function sendMessage() {
    const inputField = document.getElementById('user-input');
    const messageText = inputField.value.trim();
    if (messageText === "") return;

    appendMessage('user', messageText);
    inputField.value = "";

    const botMessageId = appendMessage('bot', 'Razmišljam...');

    // PRAVI POZIV KA BACKENDU
    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: messageText })
        });
        
        const data = await response.json();
        updateMessage(botMessageId, data.response);
    } catch (error) {
        updateMessage(botMessageId, "Greška: Server nije dostupan.");
    }
}

// Pomoćna funkcija za dodavanje poruka u HTML
function appendMessage(sender, text) {
    const chatBox = document.getElementById('chat-box');
    const messageDiv = document.createElement('div');
    const messageId = Date.now(); // Jedinstveni ID za poruku

    messageDiv.classList.add('message', sender === 'user' ? 'user-msg' : 'bot-msg');
    messageDiv.id = messageId;
    messageDiv.innerText = text;

    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight; // Automatski skroluj na dno

    return messageId;
}

// Pomoćna funkcija za promenu teksta (npr. iz "Razmišljam..." u pravi odgovor)
function updateMessage(id, newText) {
    const messageDiv = document.getElementById(id);
    if (messageDiv) {
        messageDiv.innerText = newText;
    }
}

// Funkcija koja učitava istoriju
async function loadChatHistory() {
    try {
        const response = await fetch('/history');
        const messages = await response.json();
        
        // Prođi kroz svaku poruku i prikaži je
        messages.forEach(msg => {
            appendMessage(msg.sender, msg.content);
        });
    } catch (error) {
        console.error("Greška pri učitavanju istorije:", error);
    }
}

// Dozvoli slanje poruke na taster "Enter"
document.getElementById('user-input').addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

// OVO JE NOVO: Pozovi funkciju čim se učita prozor
window.onload = () => {
    loadChatHistory();
};