/**
 * ETACard - Displays ETA information with a prominent countdown.
 */

import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "../utils/colors";
import {
  formatDuration,
  formatDistance,
  getStatusBadge,
  getDelayColor,
} from "../utils/helpers";

export function ETACard({ eta }) {
  if (!eta) return null;

  const badge = getStatusBadge(eta.status);

  return (
    <View style={styles.card}>
      {/* Status badge */}
      <View style={[styles.badge, { backgroundColor: badge.bg }]}>
        <Text style={[styles.badgeText, { color: badge.color }]}>
          {badge.text}
        </Text>
      </View>

      {/* Main ETA display */}
      <View style={styles.etaMain}>
        <Text style={styles.etaLabel}>Expected Arrival</Text>
        <Text style={styles.etaTime}>{eta.expected_arrival || "--:--"}</Text>
        {eta.scheduled_arrival && eta.expected_arrival !== eta.scheduled_arrival && (
          <Text style={styles.scheduledTime}>
            Scheduled: {eta.scheduled_arrival}
          </Text>
        )}
      </View>

      {/* Time remaining */}
      {eta.time_remaining_minutes > 0 && (
        <View style={styles.countdown}>
          <Ionicons name="time-outline" size={20} color={colors.accent} />
          <Text style={styles.countdownText}>
            {formatDuration(eta.time_remaining_minutes)} remaining
          </Text>
        </View>
      )}

      {/* Stats row */}
      <View style={styles.statsRow}>
        <View style={styles.stat}>
          <Ionicons name="navigate-outline" size={18} color={colors.primary} />
          <Text style={styles.statValue}>
            {formatDistance(eta.remaining_distance_km)}
          </Text>
          <Text style={styles.statLabel}>Distance</Text>
        </View>

        <View style={styles.statDivider} />

        <View style={styles.stat}>
          <Ionicons name="git-commit-outline" size={18} color={colors.primary} />
          <Text style={styles.statValue}>{eta.remaining_stops}</Text>
          <Text style={styles.statLabel}>Stops</Text>
        </View>

        <View style={styles.statDivider} />

        <View style={styles.stat}>
          <Ionicons
            name="alert-circle-outline"
            size={18}
            color={getDelayColor(eta.delay_minutes)}
          />
          <Text
            style={[
              styles.statValue,
              { color: getDelayColor(eta.delay_minutes) },
            ]}
          >
            {eta.delay_minutes > 0 ? `+${eta.delay_minutes}m` : "0m"}
          </Text>
          <Text style={styles.statLabel}>Delay</Text>
        </View>
      </View>

      {/* Current position */}
      {eta.current_station_name && (
        <View style={styles.currentPos}>
          <Ionicons name="location" size={16} color={colors.accent} />
          <Text style={styles.currentPosText}>
            Currently at: {eta.current_station_name}
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 20,
    marginHorizontal: 16,
    marginVertical: 8,
    elevation: 3,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.12,
    shadowRadius: 6,
  },
  badge: {
    alignSelf: "flex-start",
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
    marginBottom: 12,
  },
  badgeText: {
    fontSize: 12,
    fontWeight: "700",
  },
  etaMain: {
    alignItems: "center",
    marginBottom: 16,
  },
  etaLabel: {
    fontSize: 13,
    color: colors.textSecondary,
    marginBottom: 4,
  },
  etaTime: {
    fontSize: 42,
    fontWeight: "800",
    color: colors.primary,
    letterSpacing: 2,
  },
  scheduledTime: {
    fontSize: 13,
    color: colors.textMuted,
    marginTop: 4,
    textDecorationLine: "line-through",
  },
  countdown: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#fff8e1",
    borderRadius: 8,
    padding: 10,
    marginBottom: 16,
    gap: 8,
  },
  countdownText: {
    fontSize: 16,
    fontWeight: "700",
    color: colors.accent,
  },
  statsRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-around",
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  stat: {
    alignItems: "center",
    flex: 1,
  },
  statValue: {
    fontSize: 16,
    fontWeight: "700",
    color: colors.textPrimary,
    marginTop: 4,
  },
  statLabel: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 2,
  },
  statDivider: {
    width: 1,
    height: 36,
    backgroundColor: colors.divider,
  },
  currentPos: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
    gap: 6,
  },
  currentPosText: {
    fontSize: 13,
    color: colors.textSecondary,
    fontWeight: "500",
  },
});
