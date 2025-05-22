// static/js/models/reports_model.js
// Model for CRUD operations on reports

const API_BASE = '/api/reports';

class ReportsModel {
  /**
   * Fetch a paginated list of reports.
   * @param {Object} params - Query params { page, pageSize, filter }.
   * @returns {Promise<Object>} JSON with list and pagination info.
   */
  static async fetchReports(params = {}) {
    const query = new URLSearchParams(params);
    try {
      const response = await fetch(`${API_BASE}?${query.toString()}`, {
        method: 'GET',
        credentials: 'include',
      });
      if (!response.ok) {
        throw new Error(`Failed to fetch reports: ${response.status} ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      console.error('ReportsModel.fetchReports error:', error);
      throw error;
    }
  }

  /**
   * Fetch a single report by ID.
   * @param {string|number} reportId
   * @returns {Promise<Object>} Report data JSON.
   */
  static async fetchReport(reportId) {
    try {
      const response = await fetch(`${API_BASE}/${reportId}`, {
        method: 'GET',
        credentials: 'include',
      });
      if (!response.ok) {
        throw new Error(`Failed to fetch report ${reportId}: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('ReportsModel.fetchReport error:', error);
      throw error;
    }
  }

  /**
   * Create a new report.
   * @param {Object} data - Report payload (title, content, settings).
   * @returns {Promise<Object>} Created report JSON.
   */
  static async createReport(data) {
    try {
      const response = await fetch(API_BASE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(data),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `Failed to create report: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('ReportsModel.createReport error:', error);
      throw error;
    }
  }

  /**
   * Update an existing report by ID.
   * @param {string|number} reportId
   * @param {Object} data - Fields to update.
   * @returns {Promise<Object>} Updated report JSON.
   */
  static async updateReport(reportId, data) {
    try {
      const response = await fetch(`${API_BASE}/${reportId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(data),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `Failed to update report ${reportId}: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('ReportsModel.updateReport error:', error);
      throw error;
    }
  }

  /**
   * Delete a report by ID.
   * @param {string|number} reportId
   * @returns {Promise<void>}
   */
  static async deleteReport(reportId) {
    try {
      const response = await fetch(`${API_BASE}/${reportId}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (!response.ok) {
        throw new Error(`Failed to delete report ${reportId}: ${response.status}`);
      }
    } catch (error) {
      console.error('ReportsModel.deleteReport error:', error);
      throw error;
    }
  }
}

export default ReportsModel;
