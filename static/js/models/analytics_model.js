// static/js/models/analytics_model.js
// Model for fetching analytics data from the API.

const API_BASE = '/api/analytics';

class AnalyticsModel {
  /**
   * Fetch overview statistics for dashboard (counts, summaries).
   * @returns {Promise<Object>} Overview data JSON.
   */
  static async fetchOverview() {
    try {
      const response = await fetch(`${API_BASE}/overview`, {
        method: 'GET',
        credentials: 'include',
      });
      if (!response.ok) {
        throw new Error(`Failed to fetch analytics overview: ${response.status} ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      console.error('AnalyticsModel.fetchOverview error:', error);
      throw error;
    }
  }

  /**
   * Fetch time-series data for a specific metric over a date range.
   * @param {string} metricId - Identifier for the metric (e.g., 'users', 'revenue').
   * @param {Object} params - Query params: { startDate: 'YYYY-MM-DD', endDate: 'YYYY-MM-DD' }.
   * @returns {Promise<Object>} Time-series data JSON.
   */
  static async fetchTimeSeries(metricId, params = {}) {
    const { startDate, endDate } = params;
    const query = new URLSearchParams();
    if (startDate) query.append('start', startDate);
    if (endDate) query.append('end', endDate);

    try {
      const response = await fetch(`${API_BASE}/timeseries/${metricId}?${query.toString()}`, {
        method: 'GET',
        credentials: 'include',
      });
      if (!response.ok) {
        throw new Error(`Failed to fetch time-series for ${metricId}: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('AnalyticsModel.fetchTimeSeries error:', error);
      throw error;
    }
  }

  /**
   * Fetch detailed record list for a given analytics category.
   * @param {string} category - e.g., 'top_users', 'error_logs'.
   * @param {Object} params - Query params for pagination/filtering.
   * @returns {Promise<Object>} List data JSON.
   */
  static async fetchDetails(category, params = {}) {
    const query = new URLSearchParams(params);
    try {
      const response = await fetch(`${API_BASE}/details/${category}?${query.toString()}`, {
        method: 'GET',
        credentials: 'include',
      });
      if (!response.ok) {
        throw new Error(`Failed to fetch analytics details ${category}: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('AnalyticsModel.fetchDetails error:', error);
      throw error;
    }
  }

  /**
   * Submit a custom analytics query.
   * @param {Object} payload - Query payload (e.g., filters, aggregations).
   * @returns {Promise<Object>} Query result JSON.
   */
  static async runCustomQuery(payload) {
    try {
      const response = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.message || `Custom query failed: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('AnalyticsModel.runCustomQuery error:', error);
      throw error;
    }
  }
}

export default AnalyticsModel;
