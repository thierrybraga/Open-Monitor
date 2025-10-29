// static/js/models/account_model.js
// Model for fetching and updating user account data.

const API_BASE = '/api/account';

class AccountModel {
  /**
   * Fetch the current user's account information.
   * @returns {Promise<Object>} Account data JSON.
   */
  static async fetchAccount() {
    try {
      const response = await fetch(API_BASE, {
        method: 'GET',
        credentials: 'include', // Include cookies for auth
      });
      if (!response.ok) {
        throw new Error(`Failed to fetch account data: ${response.status} ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      console.error('AccountModel.fetchAccount error:', error);
      throw error;
    }
  }

  /**
   * Update the user's account information.
   * @param {Object} data - Fields to update (e.g., { name, email }).
   * @returns {Promise<Object>} Updated account data JSON.
   */
  static async updateAccount(data) {
    try {
      const response = await fetch(API_BASE, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(data),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `Failed to update account: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('AccountModel.updateAccount error:', error);
      throw error;
    }
  }

  /**
   * Change the user's password.
   * @param {string} currentPassword
   * @param {string} newPassword
   * @param {string} confirmPassword
   * @returns {Promise<Object>} Response JSON.
   */
  static async changePassword({ currentPassword, newPassword, confirmPassword }) {
    try {
      const response = await fetch(`${API_BASE}/password`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ currentPassword, newPassword, confirmPassword }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `Failed to change password: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('AccountModel.changePassword error:', error);
      throw error;
    }
  }
}

export default AccountModel;
