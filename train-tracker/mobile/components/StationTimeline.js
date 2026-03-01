/**
 * StationTimeline - Displays the train route as a vertical timeline.
 *
 * Shows each station with:
 * - Connection line (green for passed, grey for upcoming)
 * - Station dot (green/orange/grey based on status)
 * - Station name, code, and scheduled/actual times
 * - Delay info and distance
 */

import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../utils/colors";
import { formatTime, getDelayColor, getDelayText } from "../utils/helpers";

export function StationTimeline({ stations, currentStationCode }) {
  if (!stations || stations.length === 0) return null;

  return (
    <View style={styles.container}>
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

        return (
          <View key={`${station.code}-${index}`} style={styles.stationRow}>
            {/* Timeline column */}
            <View style={styles.timelineCol}>
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
    minHeight: 72,
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
    marginBottom: 4,
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
    fontWeight: "500",
    backgroundColor: colors.divider,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
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
  },
  timeValue: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  actualTime: {
    fontSize: 12,
    fontWeight: "500",
  },
  distText: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  delayText: {
    fontSize: 12,
    fontWeight: "600",
    marginTop: 4,
  },
  haltText: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 2,
  },
});
