/**
 * StationTimeline - Displays the train route as a vertical timeline.
 *
 * Accessibility:
 * - Each station row has a descriptive accessibilityLabel
 * - Status is conveyed via text labels, not color alone
 * - All text meets WCAG 2.2 AA contrast requirements
 */

import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../utils/colors";
import { formatTime, getDelayColor, getDelayText } from "../utils/helpers";

function getStationStatusText(station, isCurrent, isPassed, isFirst, isLast) {
  if (isCurrent) return "Current station";
  if (isPassed) return "Passed";
  if (isFirst) return "Origin";
  if (isLast) return "Destination";
  return "Upcoming";
}

export function StationTimeline({ stations, currentStationCode }) {
  if (!stations || stations.length === 0) return null;

  return (
    <View style={styles.container} accessibilityRole="list">
      {stations.map((station, index) => {
        const isFirst = index === 0;
        const isLast = index === stations.length - 1;
        const isCurrent = station.code === currentStationCode;
        const isPassed = station.has_departed || station.has_arrived;

        let dotColor = colors.stationUpcoming;
        if (isCurrent) dotColor = colors.stationCurrent;
        else if (isPassed) dotColor = colors.stationPassed;

        let lineColor = colors.trackLine;
        if (isPassed || isCurrent) lineColor = colors.trackLinePassed;

        const statusText = getStationStatusText(station, isCurrent, isPassed, isFirst, isLast);
        const delayLabel = station.delay_minutes > 0 && (isPassed || isCurrent)
          ? `, ${getDelayText(station.delay_minutes)}`
          : "";
        const a11yLabel = `${station.name}, ${station.code}, ${statusText}${delayLabel}. Arrival ${formatTime(station.arrival)}, Departure ${formatTime(station.departure)}, ${Math.round(station.distance_km)} kilometers`;

        return (
          <View
            key={`${station.code}-${index}`}
            style={styles.stationRow}
            accessible={true}
            accessibilityRole="text"
            accessibilityLabel={a11yLabel}
          >
            {/* Timeline column */}
            <View style={styles.timelineCol} importantForAccessibility="no">
              {!isFirst && (
                <View
                  style={[
                    styles.lineTop,
                    { backgroundColor: lineColor },
                  ]}
                />
              )}
              <View
                style={[
                  styles.dot,
                  { backgroundColor: dotColor },
                  isCurrent && styles.dotCurrent,
                ]}
              />
              {!isLast && (
                <View
                  style={[
                    styles.lineBottom,
                    {
                      backgroundColor:
                        isPassed && !isCurrent
                          ? colors.trackLinePassed
                          : colors.trackLine,
                    },
                  ]}
                />
              )}
            </View>

            {/* Station info column */}
            <View
              style={[styles.infoCol, isCurrent && styles.infoColCurrent]}
            >
              <View style={styles.stationHeader}>
                <Text
                  style={[
                    styles.stationName,
                    isCurrent && styles.stationNameCurrent,
                  ]}
                >
                  {station.name}
                </Text>
                <Text style={styles.stationCode}>{station.code}</Text>
              </View>

              {/* Text-based status label (not color-only) */}
              <Text style={[styles.statusLabel, isCurrent && styles.statusLabelCurrent]}>
                {statusText}
              </Text>

              <View style={styles.timeRow}>
                {/* Arrival */}
                <View style={styles.timeBlock}>
                  <Text style={styles.timeLabel}>
                    {isFirst ? "" : "Arr"}
                  </Text>
                  <Text style={styles.timeValue}>
                    {isFirst ? "" : formatTime(station.arrival)}
                  </Text>
                  {station.actual_arrival &&
                    station.actual_arrival !== station.arrival && (
                      <Text
                        style={[
                          styles.actualTime,
                          {
                            color: getDelayColor(station.delay_minutes),
                          },
                        ]}
                        accessibilityLabel={`Actual arrival ${station.actual_arrival}`}
                      >
                        {formatTime(station.actual_arrival)}
                      </Text>
                    )}
                </View>

                {/* Departure */}
                <View style={styles.timeBlock}>
                  <Text style={styles.timeLabel}>
                    {isLast ? "" : "Dep"}
                  </Text>
                  <Text style={styles.timeValue}>
                    {isLast ? "" : formatTime(station.departure)}
                  </Text>
                  {station.actual_departure &&
                    station.actual_departure !== station.departure && (
                      <Text
                        style={[
                          styles.actualTime,
                          {
                            color: getDelayColor(station.delay_minutes),
                          },
                        ]}
                        accessibilityLabel={`Actual departure ${station.actual_departure}`}
                      >
                        {formatTime(station.actual_departure)}
                      </Text>
                    )}
                </View>

                {/* Distance */}
                <View style={styles.timeBlock}>
                  <Text style={styles.timeLabel}>Dist</Text>
                  <Text style={styles.distText}>
                    {Math.round(station.distance_km)} km
                  </Text>
                </View>
              </View>

              {/* Delay indicator */}
              {station.delay_minutes > 0 && (isPassed || isCurrent) && (
                <Text
                  style={[
                    styles.delayText,
                    { color: getDelayColor(station.delay_minutes) },
                  ]}
                  accessibilityLabel={`Delay: ${getDelayText(station.delay_minutes)}`}
                >
                  {getDelayText(station.delay_minutes)}
                </Text>
              )}

              {/* Halt time */}
              {station.halt_minutes > 0 && !isFirst && !isLast && (
                <Text style={styles.haltText}>
                  Halt: {station.halt_minutes} min
                </Text>
              )}
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingVertical: 8,
  },
  stationRow: {
    flexDirection: "row",
    minHeight: 80,
  },
  timelineCol: {
    width: 40,
    alignItems: "center",
  },
  lineTop: {
    width: 3,
    flex: 1,
  },
  lineBottom: {
    width: 3,
    flex: 1,
  },
  dot: {
    width: 14,
    height: 14,
    borderRadius: 7,
  },
  dotCurrent: {
    width: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: 3,
    borderColor: colors.accentLight,
  },
  infoCol: {
    flex: 1,
    paddingLeft: 12,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },
  infoColCurrent: {
    backgroundColor: "#fff8e1",
    borderRadius: 8,
    padding: 12,
    marginRight: 8,
    borderBottomWidth: 0,
  },
  stationHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 2,
  },
  stationName: {
    fontSize: 15,
    fontWeight: "600",
    color: colors.textPrimary,
    flex: 1,
  },
  stationNameCurrent: {
    color: colors.accent,
    fontWeight: "700",
  },
  stationCode: {
    fontSize: 12,
    color: colors.textMuted,
    fontWeight: "600",
    backgroundColor: colors.divider,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  statusLabel: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.textMuted,
    marginBottom: 4,
  },
  statusLabelCurrent: {
    color: colors.accent,
  },
  timeRow: {
    flexDirection: "row",
    marginTop: 4,
  },
  timeBlock: {
    flex: 1,
  },
  timeLabel: {
    fontSize: 10,
    color: colors.textMuted,
    textTransform: "uppercase",
    fontWeight: "700",
  },
  timeValue: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  actualTime: {
    fontSize: 12,
    fontWeight: "600",
  },
  distText: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  delayText: {
    fontSize: 12,
    fontWeight: "700",
    marginTop: 4,
  },
  haltText: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 2,
  },
});
