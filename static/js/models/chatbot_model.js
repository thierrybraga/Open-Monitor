// static/js/views/chatbot_view.js
// View for rendering and handling chatbot interactions.

import ChatbotModel from "../models/chatbot_model.js";

class ChatbotView {
  /**
   * Initialize the chatbot view: bind events and load history.
   */
  static init() {
    // DOM elements
    this.chatContainer = document.getElementById('chat-container');
    this.inputField = document.getElementById('chat-input');
    this.sendButton = document.getElementById('chat-send');

    // Event listeners
    this.sendButton.addEventListener('click', () => this.handleSend());
    this.inputField.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        this.handleSend();
      }
    });

    // Load existing conversation
    this.loadHistory();
  }

  /**
   * Load conversation history from the server and render messages.
   */
  static async loadHistory() {
    try {
      const history = await ChatbotModel.fetchHistory();
      history.forEach(msg => this.renderMessage(msg));
      this.scrollToBottom();
    } catch (error) {
      console.error('Error loading chatbot history:', error);
      this.renderSystemMessage('Erro ao carregar histórico do chatbot.');
    }
  }

  /**
   * Handle sending a new message.
   */
  static async handleSend() {
    const text = this.inputField.value.trim();
    if (!text) return;

    // Render user message
    const userMsg = { sender: 'user', text };
    this.renderMessage(userMsg);
    this.inputField.value = '';
    this.scrollToBottom();

    try {
      // Send to API
      const response = await ChatbotModel.sendMessage(text);
      const botMsg = { sender: 'bot', text: response.reply };
      this.renderMessage(botMsg);
      this.scrollToBottom();
    } catch (error) {
      console.error('Error sending chatbot message:', error);
      this.renderSystemMessage('Erro ao enviar mensagem. Tente novamente.');
      this.scrollToBottom();
    }
  }

  /**
   * Render a single message in the chat container.
   * @param {{sender: string, text: string}} msg
   */
  static renderMessage(msg) {
    const msgEl = document.createElement('div');
    msgEl.classList.add('chat-message', `chat-${msg.sender}`);
    msgEl.textContent = msg.text;
    this.chatContainer.appendChild(msgEl);
  }

  /**
   * Render a system message (errors, notifications).
   * @param {string} text
   */
  static renderSystemMessage(text) {
    const sysEl = document.createElement('div');
    sysEl.classList.add('chat-message', 'chat-system');
    sysEl.textContent = text;
    this.chatContainer.appendChild(sysEl);
  }

  /**
   * Scroll the chat container to the bottom.
   */
  static scrollToBottom() {
    this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
  }
}

// Initialize when DOM is ready
if (document.readyState !== 'loading') {
  ChatbotView.init();
} else {
  document.addEventListener('DOMContentLoaded', () => ChatbotView.init());
}

export default ChatbotView;
