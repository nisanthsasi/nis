/**
 * TrainDetailScreen - Shows train details, live status, and actions.
 */

import React, { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  RefreshControl,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "../utils/colors";
import { api } from "../services/api";
import { StationTimeline } from "../components/StationTimeline";
import { getDelayColor, getDelayText } from "../utils/helpers";

export function TrainDetailScreen({ route, navigation }) {
  const { trainNumber, trainName } = route.params;
  const [trainRoute, setTrainRoute] = useState(null);
  const [liveStatus, setLiveStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState("live");

  const fetchData = useCallback(async () => {
    try {
      const [routeData, statusData] = await Promise.all([
        api.getTrainRoute(trainNumber),
        api.getLiveStatus(trainNumber),
      ]);
      setTrainRoute(routeData);
      setLiveStatus(statusData);
    } catch (error) {
      Alert.alert("Error", "Could not load train data.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [trainNumber]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  const handleETAPress = (station) => {
    navigation.navigate("ETA", {
      trainNumber,
      trainName: trainRoute?.train_name || trainName,
      stationCode: station.code,
      stationName: station.name,
    });
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={colors.primary} />
        <Text style={styles.loadingText}>Loading train info...</Text>
      </View>
    );
  }

  const stations = activeTab === "live"
    ? liveStatus?.stations || []
    : trainRoute?.stations || [];

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Train header card */}
      <View style={styles.headerCard}>
        <View style={styles.headerTop}>
          <View>
            <Text style={styles.trainNumber}>{trainNumber}</Text>
            <Text style={styles.trainName}>
              {trainRoute?.train_name || trainName}
            </Text>
          </View>
          <TouchableOpacity onPress={onRefresh}>
            <Ionicons name="refresh" size={24} color={colors.textLight} />
          </TouchableOpacity>
        </View>

        {/* Route summary */}
        {trainRoute && trainRoute.stations.length > 0 && (
          <View style={styles.routeSummary}>
            <View style={styles.endStation}>
              <Text style={styles.endCode}>
                {trainRoute.stations[0].code}
              </Text>
              <Text style={styles.endName}>
                {trainRoute.stations[0].name}
              </Text>
              <Text style={styles.endTime}>
                {trainRoute.stations[0].departure || "--:--"}
              </Text>
            </View>
            <View style={styles.routeLine}>
              <View style={styles.routeDash} />
              <Ionicons
                name="train"
                size={20}
                color={colors.accentLight}
              />
              <View style={styles.routeDash} />
            </View>
            <View style={[styles.endStation, { alignItems: "flex-end" }]}>
              <Text style={styles.endCode}>
                {trainRoute.stations[trainRoute.stations.length - 1].code}
              </Text>
              <Text style={styles.endName}>
                {trainRoute.stations[trainRoute.stations.length - 1].name}
              </Text>
              <Text style={styles.endTime}>
                {trainRoute.stations[trainRoute.stations.length - 1].arrival ||
                  "--:--"}
              </Text>
            </View>
          </View>
        )}

        {/* Live status banner */}
        {liveStatus && (
          <View style={styles.statusBanner}>
            <Ionicons
              name="radio-outline"
              size={16}
              color={colors.textLight}
            />
            <Text style={styles.statusText}>
              {liveStatus.status_message}
            </Text>
            {liveStatus.delay_minutes > 0 && (
              <View
                style={[
                  styles.delayBadge,
                  {
                    backgroundColor: getDelayColor(
                      liveStatus.delay_minutes
                    ),
                  },
                ]}
              >
                <Text style={styles.delayBadgeText}>
                  {getDelayText(liveStatus.delay_minutes)}
                </Text>
              </View>
            )}
          </View>
        )}
      </View>

      {/* Tab switcher */}
      <View style={styles.tabs}>
        <TouchableOpacity
          style={[styles.tab, activeTab === "live" && styles.tabActive]}
          onPress={() => setActiveTab("live")}
        >
          <Ionicons
            name="radio"
            size={16}
            color={
              activeTab === "live" ? colors.primary : colors.textMuted
            }
          />
          <Text
            style={[
              styles.tabText,
              activeTab === "live" && styles.tabTextActive,
            ]}
          >
            Live Status
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tab, activeTab === "schedule" && styles.tabActive]}
          onPress={() => setActiveTab("schedule")}
        >
          <Ionicons
            name="calendar-outline"
            size={16}
            color={
              activeTab === "schedule" ? colors.primary : colors.textMuted
            }
          />
          <Text
            style={[
              styles.tabText,
              activeTab === "schedule" && styles.tabTextActive,
            ]}
          >
            Schedule
          </Text>
        </TouchableOpacity>
      </View>

      {/* Info text */}
      <Text style={styles.tapHint}>
        Tap any station to see ETA and journey details
      </Text>

      {/* Station list with ETA tap */}
      <View style={styles.stationsContainer}>
        {stations.map((station, index) => (
          <TouchableOpacity
            key={`${station.code}-${index}`}
            onPress={() => handleETAPress(station)}
            activeOpacity={0.7}
          >
            <View pointerEvents="none">
              <StationTimeline
                stations={[station]}
                currentStationCode={liveStatus?.current_station}
              />
            </View>
          </TouchableOpacity>
        ))}
      </View>

      {/* Last updated */}
      {liveStatus?.last_updated && (
        <Text style={styles.lastUpdated}>
          Last updated: {liveStatus.last_updated}
        </Text>
      )}

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
  headerCard: {
    backgroundColor: colors.primary,
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 20,
  },
  headerTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  trainNumber: {
    fontSize: 14,
    fontWeight: "600",
    color: "rgba(255,255,255,0.7)",
  },
  trainName: {
    fontSize: 22,
    fontWeight: "800",
    color: colors.textLight,
    marginTop: 2,
  },
  routeSummary: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 20,
    backgroundColor: "rgba(255,255,255,0.1)",
    borderRadius: 12,
    padding: 14,
  },
  endStation: {
    flex: 1,
  },
  endCode: {
    fontSize: 18,
    fontWeight: "800",
    color: colors.textLight,
  },
  endName: {
    fontSize: 11,
    color: "rgba(255,255,255,0.7)",
    marginTop: 2,
  },
  endTime: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.accentLight,
    marginTop: 4,
  },
  routeLine: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 8,
  },
  routeDash: {
    width: 20,
    height: 2,
    backgroundColor: "rgba(255,255,255,0.3)",
  },
  statusBanner: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 12,
    gap: 8,
    flexWrap: "wrap",
  },
  statusText: {
    fontSize: 13,
    color: "rgba(255,255,255,0.9)",
    flex: 1,
  },
  delayBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
  },
  delayBadgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.textLight,
  },
  tabs: {
    flexDirection: "row",
    marginHorizontal: 16,
    marginTop: 16,
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 4,
    elevation: 1,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
  },
  tab: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 10,
    borderRadius: 8,
    gap: 6,
  },
  tabActive: {
    backgroundColor: "#e8eaf6",
  },
  tabText: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.textMuted,
  },
  tabTextActive: {
    color: colors.primary,
  },
  tapHint: {
    fontSize: 12,
    color: colors.textMuted,
    textAlign: "center",
    marginTop: 12,
    marginBottom: 4,
  },
  stationsContainer: {
    marginHorizontal: 16,
    marginTop: 8,
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 12,
    elevation: 1,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
  },
  lastUpdated: {
    fontSize: 11,
    color: colors.textMuted,
    textAlign: "center",
    marginTop: 12,
  },
});
