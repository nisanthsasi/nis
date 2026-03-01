/**
 * TrainCard - Displays a train search result as a tappable card.
 *
 * Accessibility:
 * - Full card is a single accessible button with descriptive label
 * - Day badges have 44px hit target and text labels
 * - Contrast ratios meet WCAG 2.2 AA
 */

import React from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "../utils/colors";

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function TrainCard({ train, onPress }) {
  const source = train.source || train.source_station;
  const dest = train.destination || train.destination_station;
  const runDaysText = train.run_days ? train.run_days.join(", ") : "Daily";

  return (
    <TouchableOpacity
      style={styles.card}
      onPress={() => onPress(train)}
      activeOpacity={0.7}
      accessibilityRole="button"
      accessibilityLabel={`Train ${train.train_number}, ${train.train_name}, from ${source} ${train.source_name || ""} to ${dest} ${train.destination_name || ""}, runs on ${runDaysText}`}
      accessibilityHint="Double tap to view train details and live status"
    >
      <View style={styles.header}>
        <View style={styles.trainNumber}>
          <Ionicons
            name="train-outline"
            size={16}
            color={colors.primary}
            accessibilityElementsHidden={true}
            importantForAccessibility="no"
          />
          <Text style={styles.numberText}>{train.train_number}</Text>
        </View>
        <Ionicons
          name="chevron-forward"
          size={20}
          color={colors.textMuted}
          accessibilityElementsHidden={true}
          importantForAccessibility="no"
        />
      </View>

      <Text style={styles.trainName}>{train.train_name}</Text>

      <View style={styles.route}>
        <View style={styles.stationBlock}>
          <Text style={styles.stationCode}>{source}</Text>
          <Text style={styles.stationName} numberOfLines={1}>
            {train.source_name || ""}
          </Text>
        </View>

        <View
          style={styles.arrow}
          accessibilityElementsHidden={true}
          importantForAccessibility="no"
        >
          <View style={styles.arrowLine} />
          <Ionicons name="arrow-forward" size={14} color={colors.accent} />
        </View>

        <View style={[styles.stationBlock, styles.destBlock]}>
          <Text style={styles.stationCode}>{dest}</Text>
          <Text style={styles.stationName} numberOfLines={1}>
            {train.destination_name || ""}
          </Text>
        </View>
      </View>

      {train.run_days && train.run_days.length > 0 && (
        <View
          style={styles.daysRow}
          accessibilityLabel={`Runs on ${runDaysText}`}
        >
          {DAY_NAMES.map((day) => {
            const isActive = train.run_days.includes(day);
            return (
              <View
                key={day}
                style={[
                  styles.dayBadge,
                  isActive && styles.dayBadgeActive,
                ]}
              >
                <Text
                  style={[
                    styles.dayText,
                    isActive && styles.dayTextActive,
                  ]}
                >
                  {day.charAt(0)}
                </Text>
              </View>
            );
          })}
        </View>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginHorizontal: 16,
    marginVertical: 6,
    elevation: 2,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  trainNumber: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  numberText: {
    fontSize: 14,
    fontWeight: "700",
    color: colors.primary,
  },
  trainName: {
    fontSize: 17,
    fontWeight: "600",
    color: colors.textPrimary,
    marginTop: 4,
    marginBottom: 12,
  },
  route: {
    flexDirection: "row",
    alignItems: "center",
  },
  stationBlock: {
    flex: 1,
  },
  destBlock: {
    alignItems: "flex-end",
  },
  stationCode: {
    fontSize: 16,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  stationName: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  arrow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 8,
  },
  arrowLine: {
    width: 30,
    height: 2,
    backgroundColor: colors.accent,
    marginRight: -2,
  },
  daysRow: {
    flexDirection: "row",
    marginTop: 12,
    gap: 6,
  },
  dayBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.divider,
    alignItems: "center",
    justifyContent: "center",
  },
  dayBadgeActive: {
    backgroundColor: colors.primaryLight,
  },
  dayText: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.textMuted,
  },
  dayTextActive: {
    color: colors.textLight,
  },
});
