/**
 * Helper utilities for time formatting and display.
 */

/**
 * Format minutes into a human-readable duration string.
 */
export function formatDuration(minutes) {
  if (!minutes || minutes <= 0) return "0m";
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours === 0) return `${mins}m`;
  if (mins === 0) return `${hours}h`;
  return `${hours}h ${mins}m`;
}

/**
 * Format distance in km with appropriate precision.
 */
export function formatDistance(km) {
  if (!km || km <= 0) return "0 km";
  if (km < 1) return `${Math.round(km * 1000)} m`;
  return `${Math.round(km)} km`;
}

/**
 * Get a human-readable delay status message.
 */
export function getDelayText(minutes) {
  if (!minutes || minutes === 0) return "On Time";
  if (minutes < 0) return `${Math.abs(minutes)} min early`;
  if (minutes <= 5) return "Slight delay";
  if (minutes <= 15) return `${minutes} min late`;
  if (minutes <= 60) return `${minutes} min late`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hours}h ${mins}m late`;
}

/**
 * Get color for delay status.
 */
export function getDelayColor(minutes) {
  if (!minutes || minutes <= 0) return "#2e7d32";
  if (minutes <= 5) return "#f57f17";
  if (minutes <= 15) return "#e65100";
  return "#c62828";
}

/**
 * Get status badge configuration.
 */
export function getStatusBadge(status) {
  const badges = {
    on_time: { text: "On Time", color: "#2e7d32", bg: "#e8f5e9" },
    slightly_delayed: { text: "Slight Delay", color: "#f57f17", bg: "#fff8e1" },
    delayed: { text: "Delayed", color: "#e65100", bg: "#fff3e0" },
    not_departed: { text: "Not Departed", color: "#1565c0", bg: "#e3f2fd" },
    completed: { text: "Arrived", color: "#2e7d32", bg: "#e8f5e9" },
    already_passed: { text: "Passed", color: "#757575", bg: "#f5f5f5" },
  };
  return badges[status] || { text: status, color: "#757575", bg: "#f5f5f5" };
}

/**
 * Format a time string (HH:MM) for display.
 */
export function formatTime(timeStr) {
  if (!timeStr) return "--:--";
  return timeStr;
}

/**
 * Calculate progress percentage between two stations.
 */
export function calculateProgress(currentDistance, fromDistance, toDistance) {
  if (toDistance <= fromDistance) return 0;
  const progress = (currentDistance - fromDistance) / (toDistance - fromDistance);
  return Math.max(0, Math.min(1, progress));
}
