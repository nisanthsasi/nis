/**
 * HomeScreen - Main landing screen with train search and quick actions.
 */

import React, { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "../utils/colors";
import { api } from "../services/api";
import { TrainCard } from "../components/TrainCard";

const POPULAR_TRAINS = [
  { number: "12301", name: "Howrah Rajdhani", route: "NDLS → HWH" },
  { number: "12951", name: "Mumbai Rajdhani", route: "MMCT → NDLS" },
  { number: "12622", name: "Tamil Nadu Express", route: "NDLS → MAS" },
  { number: "12627", name: "Karnataka Express", route: "NDLS → SBC" },
  { number: "12002", name: "Bhopal Shatabdi", route: "NDLS → BPL" },
  { number: "12431", name: "TVC Rajdhani", route: "NDLS → TVC" },
];

export function HomeScreen({ navigation }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    const trimmed = query.trim();
    if (!trimmed) return;

    setLoading(true);
    setSearched(true);
    try {
      const data = await api.searchTrains(trimmed);
      setResults(data.trains || []);
    } catch (error) {
      Alert.alert("Error", "Could not search trains. Check your connection.");
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleTrainPress = (train) => {
    navigation.navigate("TrainDetail", {
      trainNumber: train.train_number,
      trainName: train.train_name,
    });
  };

  const handlePopularPress = (train) => {
    navigation.navigate("TrainDetail", {
      trainNumber: train.number,
      trainName: train.name,
    });
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView style={styles.scroll} keyboardShouldPersistTaps="handled">
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.headerTitle} accessibilityRole="header">
            Train Tracker
          </Text>
          <Text style={styles.headerSubtitle}>
            Indian Railways Live Tracking
          </Text>
        </View>

        {/* Search bar */}
        <View style={styles.searchSection}>
          <View style={styles.searchBar}>
            <Ionicons name="search" size={20} color={colors.textMuted} />
            <TextInput
              style={styles.searchInput}
              placeholder="Enter train number or name..."
              placeholderTextColor={colors.textMuted}
              value={query}
              onChangeText={setQuery}
              onSubmitEditing={handleSearch}
              returnKeyType="search"
              autoCorrect={false}
              accessibilityLabel="Search trains"
              accessibilityHint="Enter a train number or name, then tap Search"
            />
            {query.length > 0 && (
              <TouchableOpacity
                onPress={() => {
                  setQuery("");
                  setResults([]);
                  setSearched(false);
                }}
                accessibilityRole="button"
                accessibilityLabel="Clear search"
                hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
              >
                <Ionicons
                  name="close-circle"
                  size={20}
                  color={colors.textMuted}
                />
              </TouchableOpacity>
            )}
          </View>
          <TouchableOpacity
            style={styles.searchButton}
            onPress={handleSearch}
            accessibilityRole="button"
            accessibilityLabel="Search trains"
          >
            <Text style={styles.searchButtonText}>Search</Text>
          </TouchableOpacity>
        </View>

        {/* Quick actions */}
        <View style={styles.quickActions}>
          <TouchableOpacity
            style={styles.actionCard}
            onPress={() => navigation.navigate("StationSearch")}
            accessibilityRole="button"
            accessibilityLabel="Find trains between stations"
          >
            <Ionicons name="swap-horizontal" size={28} color={colors.primary} importantForAccessibility="no" />
            <Text style={styles.actionText}>Trains Between{"\n"}Stations</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.actionCard}
            onPress={() => navigation.navigate("StationSearch")}
            accessibilityRole="button"
            accessibilityLabel="Search stations"
          >
            <Ionicons name="location-outline" size={28} color={colors.accent} importantForAccessibility="no" />
            <Text style={styles.actionText}>Search{"\n"}Stations</Text>
          </TouchableOpacity>
        </View>

        {/* Search results */}
        {loading && (
          <ActivityIndicator
            size="large"
            color={colors.primary}
            style={styles.loader}
          />
        )}

        {!loading && searched && results.length === 0 && (
          <View style={styles.emptyState}>
            <Ionicons name="train-outline" size={48} color={colors.textMuted} />
            <Text style={styles.emptyText}>No trains found</Text>
            <Text style={styles.emptySubtext}>
              Try a different train number or name
            </Text>
          </View>
        )}

        {!loading &&
          results.map((train, index) => (
            <TrainCard key={index} train={train} onPress={handleTrainPress} />
          ))}

        {/* Popular trains */}
        {!searched && (
          <View style={styles.popularSection}>
            <Text style={styles.sectionTitle} accessibilityRole="header">Popular Trains</Text>
            {POPULAR_TRAINS.map((train) => (
              <TouchableOpacity
                key={train.number}
                style={styles.popularCard}
                onPress={() => handlePopularPress(train)}
                accessibilityRole="button"
                accessibilityLabel={`Train ${train.number}, ${train.name}, ${train.route}`}
                accessibilityHint="Double tap to view details"
              >
                <View style={styles.popularLeft}>
                  <Ionicons
                    name="train"
                    size={20}
                    color={colors.primaryLight}
                  />
                  <View style={styles.popularInfo}>
                    <Text style={styles.popularNumber}>{train.number}</Text>
                    <Text style={styles.popularName}>{train.name}</Text>
                  </View>
                </View>
                <View style={styles.popularRight}>
                  <Text style={styles.popularRoute}>{train.route}</Text>
                  <Ionicons
                    name="chevron-forward"
                    size={16}
                    color={colors.textMuted}
                  />
                </View>
              </TouchableOpacity>
            ))}
          </View>
        )}

        <View style={{ height: 32 }} />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scroll: {
    flex: 1,
  },
  header: {
    backgroundColor: colors.primary,
    paddingHorizontal: 20,
    paddingTop: 60,
    paddingBottom: 24,
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: "800",
    color: colors.textLight,
  },
  headerSubtitle: {
    fontSize: 14,
    color: "rgba(255,255,255,0.85)",
    marginTop: 4,
  },
  searchSection: {
    flexDirection: "row",
    paddingHorizontal: 16,
    marginTop: -20,
    gap: 8,
  },
  searchBar: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 12,
    paddingHorizontal: 14,
    height: 48,
    elevation: 4,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    gap: 10,
  },
  searchInput: {
    flex: 1,
    fontSize: 15,
    color: colors.textPrimary,
  },
  searchButton: {
    backgroundColor: colors.accent,
    borderRadius: 12,
    paddingHorizontal: 20,
    height: 48,
    justifyContent: "center",
    elevation: 4,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
  },
  searchButtonText: {
    color: colors.textLight,
    fontWeight: "700",
    fontSize: 15,
  },
  quickActions: {
    flexDirection: "row",
    paddingHorizontal: 16,
    marginTop: 20,
    gap: 12,
  },
  actionCard: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    elevation: 2,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 4,
  },
  actionText: {
    fontSize: 13,
    color: colors.textPrimary,
    fontWeight: "600",
    textAlign: "center",
    marginTop: 8,
    lineHeight: 18,
  },
  loader: {
    marginTop: 40,
  },
  emptyState: {
    alignItems: "center",
    paddingVertical: 48,
  },
  emptyText: {
    fontSize: 16,
    fontWeight: "600",
    color: colors.textSecondary,
    marginTop: 12,
  },
  emptySubtext: {
    fontSize: 13,
    color: colors.textMuted,
    marginTop: 4,
  },
  popularSection: {
    marginTop: 24,
    paddingHorizontal: 16,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: colors.textPrimary,
    marginBottom: 12,
  },
  popularCard: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 14,
    marginBottom: 8,
    elevation: 1,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
  },
  popularLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  popularInfo: {},
  popularNumber: {
    fontSize: 13,
    fontWeight: "700",
    color: colors.primary,
  },
  popularName: {
    fontSize: 14,
    color: colors.textPrimary,
    fontWeight: "500",
  },
  popularRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  popularRoute: {
    fontSize: 12,
    color: colors.textSecondary,
  },
});
