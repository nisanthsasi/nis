/**
 * ETAScreen - Shows detailed ETA to a destination station.
 *
 * Displays:
 * - Expected arrival time with delay
 * - Countdown timer
 * - Remaining distance and stops
 * - All intermediate stations to reach destination
 */

import React, { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  Alert,
  RefreshControl,
  TouchableOpacity,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "../utils/colors";
import { api } from "../services/api";
import { ETACard } from "../components/ETACard";
import { StationTimeline } from "../components/StationTimeline";
import { formatDuration, formatDistance } from "../utils/helpers";

export function ETAScreen({ route, navigation }) {
  const { trainNumber, trainName, stationCode, stationName } = route.params;
  const [eta, setEta] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchETA = useCallback(async () => {
    try {
      const data = await api.getETA(trainNumber, stationCode);
      setEta(data);
    } catch (error) {
      Alert.alert("Error", "Could not calculate ETA.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [trainNumber, stationCode]);

  useEffect(() => {
    fetchETA();
    // Auto-refresh every 2 minutes
    const interval = setInterval(fetchETA, 120000);
    return () => clearInterval(interval);
  }, [fetchETA]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchETA();
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={colors.primary} />
        <Text style={styles.loadingText}>Calculating ETA...</Text>
      </View>
    );
  }

  if (!eta) {
    return (
      <View style={styles.errorContainer}>
        <Ionicons name="alert-circle" size={48} color={colors.error} />
        <Text style={styles.errorText}>Could not calculate ETA</Text>
        <Text style={styles.errorSubtext}>
          This station may not be on the train's route
        </Text>
        <TouchableOpacity style={styles.retryButton} onPress={fetchETA}>
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTrain}>
          {trainNumber} - {eta.train_name}
        </Text>
        <View style={styles.headerRoute}>
          <Text style={styles.headerTo}>ETA to</Text>
          <Text style={styles.headerStation} accessibilityRole="header">{eta.destination_name}</Text>
          <Text style={styles.headerCode}>{eta.destination_station}</Text>
        </View>
      </View>

      {/* ETA Card */}
      <ETACard eta={eta} />

      {/* Journey progress */}
      {eta.remaining_stations && eta.remaining_stations.length > 0 && (
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons
              name="git-branch-outline"
              size={20}
              color={colors.primary}
            />
            <Text style={styles.sectionTitle}>
              Stations to {stationName || eta.destination_name}
            </Text>
          </View>

          <View style={styles.stationsList}>
            {/* Current station marker */}
            {eta.current_station_name && (
              <View style={styles.currentMarker}>
                <Ionicons
                  name="location"
                  size={16}
                  color={colors.accent}
                />
                <Text style={styles.currentMarkerText}>
                  Current: {eta.current_station_name}
                </Text>
              </View>
            )}

            <StationTimeline
              stations={eta.remaining_stations}
              currentStationCode={eta.current_station}
            />
          </View>
        </View>
      )}

      {/* Summary stats */}
      <View style={styles.summaryCard}>
        <Text style={styles.summaryTitle}>Journey Summary</Text>

        <View style={styles.summaryRow}>
          <View style={styles.summaryItem}>
            <Ionicons name="time-outline" size={20} color={colors.primary} />
            <Text style={styles.summaryLabel}>Time Left</Text>
            <Text style={styles.summaryValue}>
              {formatDuration(eta.time_remaining_minutes)}
            </Text>
          </View>
          <View style={styles.summaryItem}>
            <Ionicons
              name="navigate-outline"
              size={20}
              color={colors.primary}
            />
            <Text style={styles.summaryLabel}>Distance Left</Text>
            <Text style={styles.summaryValue}>
              {formatDistance(eta.remaining_distance_km)}
            </Text>
          </View>
        </View>

        <View style={styles.summaryRow}>
          <View style={styles.summaryItem}>
            <Ionicons
              name="git-commit-outline"
              size={20}
              color={colors.primary}
            />
            <Text style={styles.summaryLabel}>Stops Remaining</Text>
            <Text style={styles.summaryValue}>{eta.remaining_stops}</Text>
          </View>
          <View style={styles.summaryItem}>
            <Ionicons
              name="speedometer-outline"
              size={20}
              color={colors.primary}
            />
            <Text style={styles.summaryLabel}>Delay</Text>
            <Text style={styles.summaryValue}>
              {eta.delay_minutes > 0 ? `${eta.delay_minutes} min` : "None"}
            </Text>
          </View>
        </View>
      </View>

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: colors.background,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: colors.textSecondary,
  },
  errorContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: colors.background,
    paddingHorizontal: 32,
  },
  errorText: {
    fontSize: 18,
    fontWeight: "700",
    color: colors.textPrimary,
    marginTop: 16,
  },
  errorSubtext: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 8,
    textAlign: "center",
  },
  retryButton: {
    marginTop: 24,
    backgroundColor: colors.primary,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  retryText: {
    color: colors.textLight,
    fontWeight: "700",
  },
  header: {
    backgroundColor: colors.primary,
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 20,
  },
  headerTrain: {
    fontSize: 13,
    color: "rgba(255,255,255,0.85)",
    fontWeight: "600",
  },
  headerRoute: {
    marginTop: 8,
  },
  headerTo: {
    fontSize: 13,
    color: "rgba(255,255,255,0.85)",
  },
  headerStation: {
    fontSize: 24,
    fontWeight: "800",
    color: colors.textLight,
    marginTop: 2,
  },
  headerCode: {
    fontSize: 14,
    color: colors.accentLight,
    fontWeight: "600",
    marginTop: 2,
  },
  section: {
    marginHorizontal: 16,
    marginTop: 16,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  stationsList: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 12,
    elevation: 1,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
  },
  currentMarker: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fff8e1",
    borderRadius: 8,
    padding: 8,
    marginBottom: 8,
    gap: 6,
  },
  currentMarkerText: {
    fontSize: 13,
    fontWeight: "600",
    color: colors.accent,
  },
  summaryCard: {
    marginHorizontal: 16,
    marginTop: 16,
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 16,
    elevation: 1,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
  },
  summaryTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: colors.textPrimary,
    marginBottom: 16,
  },
  summaryRow: {
    flexDirection: "row",
    marginBottom: 16,
    gap: 12,
  },
  summaryItem: {
    flex: 1,
    alignItems: "center",
    backgroundColor: colors.background,
    borderRadius: 10,
    padding: 12,
  },
  summaryLabel: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 6,
  },
  summaryValue: {
    fontSize: 18,
    fontWeight: "800",
    color: colors.textPrimary,
    marginTop: 2,
  },
});
