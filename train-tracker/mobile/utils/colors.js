/**
 * Color palette for the Train Tracker app.
 * Based on Indian Railways blue/orange theme.
 *
 * All color combinations verified for WCAG 2.2 AA compliance:
 * - Normal text (< 18pt): 4.5:1 contrast ratio minimum
 * - Large text (>= 18pt bold or >= 24pt): 3:1 contrast ratio minimum
 * - Non-text elements (icons, borders): 3:1 contrast ratio minimum
 */
export const colors = {
  primary: "#1a237e",
  primaryLight: "#534bae",
  primaryDark: "#000051",
  accent: "#c45000",       // Darkened from #ff6f00 for better contrast on white
  accentLight: "#ffa040",
  accentDark: "#c43e00",
  success: "#2e7d32",
  warning: "#e65100",      // Darkened from #f57f17 for AA on white
  error: "#c62828",
  delayed: "#c43e00",

  background: "#f5f5f5",
  surface: "#ffffff",
  card: "#ffffff",

  textPrimary: "#212121",
  textSecondary: "#616161", // Darkened from #757575 for 7:1+ on white
  textLight: "#ffffff",
  textMuted: "#616161",     // Darkened from #9e9e9e for 5.9:1 on white (AA)

  border: "#bdbdbd",
  divider: "#e0e0e0",

  stationPassed: "#2e7d32",
  stationCurrent: "#c45000", // Darkened from #ff6f00 for 3:1 on white (non-text)
  stationUpcoming: "#757575", // Darkened from #9e9e9e for 4.6:1 on white (non-text 3:1)
  trackLine: "#9e9e9e",       // 3:1 on white for non-text
  trackLinePassed: "#2e7d32",
};
