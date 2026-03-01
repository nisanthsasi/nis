/**
 * API service for communicating with the Train Tracker backend.
 *
 * Configure BASE_URL to point to the Flask backend server.
 * Defaults to localhost:5000 for development.
 */

const BASE_URL = "http://localhost:5000/api";

async function fetchJSON(url) {
  const response = await fetch(url);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error || `Request failed: ${response.status}`);
  }
  return response.json();
}

export const api = {
  /**
   * Search trains by number or name.
   */
  searchTrains: (query) =>
    fetchJSON(`${BASE_URL}/trains/search?q=${encodeURIComponent(query)}`),

  /**
   * Get the full route/schedule for a train.
   */
  getTrainRoute: (trainNumber) =>
    fetchJSON(`${BASE_URL}/trains/${trainNumber}/route`),

  /**
   * Get live running status of a train.
   */
  getLiveStatus: (trainNumber, date) => {
    let url = `${BASE_URL}/trains/${trainNumber}/live`;
    if (date) url += `?date=${date}`;
    return fetchJSON(url);
  },

  /**
   * Calculate ETA to a destination station.
   */
  getETA: (trainNumber, stationCode, date) => {
    let url = `${BASE_URL}/trains/${trainNumber}/eta?station=${stationCode}`;
    if (date) url += `&date=${date}`;
    return fetchJSON(url);
  },

  /**
   * Get journey summary between two stations.
   */
  getJourneySummary: (trainNumber, fromStation, toStation) =>
    fetchJSON(
      `${BASE_URL}/trains/${trainNumber}/journey?from=${fromStation}&to=${toStation}`
    ),

  /**
   * Search stations by code or name.
   */
  searchStations: (query) =>
    fetchJSON(
      `${BASE_URL}/stations/search?q=${encodeURIComponent(query)}`
    ),

  /**
   * Find trains between two stations.
   */
  getTrainsBetween: (fromStation, toStation) =>
    fetchJSON(
      `${BASE_URL}/trains/between?from=${fromStation}&to=${toStation}`
    ),
};
