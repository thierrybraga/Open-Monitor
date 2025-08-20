// static/js/models/chatbot_model.js
// Model for handling chatbot data operations and API communication.

class ChatbotModel {
  /**
   * Fetch conversation history from the server.
   * @returns {Promise<Array>} Array of message objects
   */
  static async fetchHistory() {
    try {
      const response = await fetch('/api/chatbot/history', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data.success ? data.messages : [];
    } catch (error) {
      console.error('Error fetching chatbot history:', error);
      throw error;
    }
  }

  /**
   * Send a message to the chatbot API.
   * @param {string} message - The user message
   * @param {string|null} sessionId - Current session ID
   * @returns {Promise<Object>} API response object
   */
  static async sendMessage(message, sessionId = null) {
    try {
      const response = await fetch('/api/chatbot/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: message,
          session_id: sessionId
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      if (!data.success) {
        throw new Error(data.error || 'Unknown error occurred');
      }

      return {
        reply: data.response,
        sessionId: data.session_id,
        relevantCves: data.relevant_cves || []
      };
    } catch (error) {
      console.error('Error sending message to chatbot:', error);
      throw error;
    }
  }

  /**
   * Clear the current chat session.
   * @param {string} sessionId - Session ID to clear
   * @returns {Promise<boolean>} Success status
   */
  static async clearSession(sessionId) {
    try {
      const response = await fetch('/api/chatbot/clear', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data.success;
    } catch (error) {
      console.error('Error clearing chatbot session:', error);
      throw error;
    }
  }
}

export default ChatbotModel;
