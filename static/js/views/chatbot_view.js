// chatbot_view.js
// Responsável por renderizar o chat de segurança e manipular eventos de usuário

import ChatbotModel from "../models/chatbot_model.js";

const ChatbotView = (() => {
    let messagesContainer;
    let inputField;
    let sendButton;

    function init() {
        messagesContainer = document.getElementById("chatbot-messages");
        inputField = document.getElementById("chatbot-input");
        sendButton = document.getElementById("chatbot-send-btn");
        bindEvents();
    }

    /**
     * Renderiza lista de mensagens no container.
     * @param {Array<Object>} messages - Lista de mensagens com campos:
     *   {string} sender - 'user' ou 'bot'
     *   {string} text    - Conteúdo da mensagem
     *   {string} timestamp (ISO date string)
     */
    function render(messages) {
        if (!messagesContainer) init();
        messagesContainer.innerHTML = messages.map(msg => `
            <div class="message ${msg.sender}">
                <div class="message-text">${msg.text}</div>
                <div class="message-time">${new Date(msg.timestamp).toLocaleTimeString()}</div>
            </div>
        `).join('');
        // Scroll até a última mensagem
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    /**
     * Limpa o campo de input após enviar.
     */
    function clearInput() {
        if (!inputField) init();
        inputField.value = "";
        inputField.focus();
    }

    /**
     * Associa listeners ao botão e enter no input.
     */
    function bindEvents() {
        if (!inputField || !sendButton) return;
        sendButton.addEventListener("click", sendMessage);
        inputField.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    function sendMessage() {
        const text = inputField.value.trim();
        if (!text) return;
        // Dispara evento para o controller tratar o envio
        document.dispatchEvent(
            new CustomEvent("chatbot:message:send", { detail: { text } })
        );
        clearInput();
    }

    return {
        render,
        clearInput
    };
})();

export default ChatbotView;