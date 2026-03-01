/**
 * StationSearchScreen - Search for stations and find trains between them.
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
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "../utils/colors";
import { api } from "../services/api";

export function StationSearchScreen({ navigation }) {
  const [fromQuery, setFromQuery] = useState("");
  const [toQuery, setToQuery] = useState("");
  const [fromStation, setFromStation] = useState(null);
  const [toStation, setToStation] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [activeField, setActiveField] = useState(null);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const searchStations = async (query, field) => {
    if (query.length < 2) {
      setSuggestions([]);
      return;
    }
    setActiveField(field);
    try {
      const data = await api.searchStations(query);
      setSuggestions(data.stations || []);
    } catch {
      setSuggestions([]);
    }
  };

  const selectStation = (station, field) => {
    if (field === "from") {
      setFromStation(station);
      setFromQuery(`${station.name} (${station.code})`);
    } else {
      setToStation(station);
      setToQuery(`${station.name} (${station.code})`);
    }
    setSuggestions([]);
    setActiveField(null);
  };

  const handleSearch = async () => {
    if (!fromStation || !toStation) {
      Alert.alert("Select Stations", "Please select both From and To stations.");
      return;
    }

    setLoading(true);
    setSearched(true);
    try {
      const data = await api.getTrainsBetween(fromStation.code, toStation.code);
      setResults(data.trains || []);
    } catch (error) {
      Alert.alert("Error", "Could not find trains between these stations.");
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const swapStations = () => {
    const tmpStation = fromStation;
    const tmpQuery = fromQuery;
    setFromStation(toStation);
    setFromQuery(toQuery);
    setToStation(tmpStation);
    setToQuery(tmpQuery);
  };

  return (
    <ScrollView
      style={styles.container}
      keyboardShouldPersistTaps="handled"
    >
      {/* Search form */}
      <View style={styles.formCard}>
        <Text style={styles.formTitle}>Find Trains Between Stations</Text>

        {/* From field */}
        <View style={styles.fieldContainer}>
          <View style={styles.fieldIcon}>
            <Ionicons
              name="radio-button-on"
              size={16}
              color={colors.success}
            />
          </View>
          <View style={styles.fieldInput}>
            <Text style={styles.fieldLabel}>From</Text>
            <TextInput
              style={styles.input}
              placeholder="Source station name or code"
              placeholderTextColor={colors.textMuted}
              value={fromQuery}
              onChangeText={(text) => {
                setFromQuery(text);
                setFromStation(null);
                searchStations(text, "from");
              }}
              onFocus={() => setActiveField("from")}
            />
          </View>
        </View>

        {/* Swap button */}
        <TouchableOpacity style={styles.swapButton} onPress={swapStations}>
          <Ionicons name="swap-vertical" size={20} color={colors.primary} />
        </TouchableOpacity>

        {/* To field */}
        <View style={styles.fieldContainer}>
          <View style={styles.fieldIcon}>
            <Ionicons name="location" size={16} color={colors.error} />
          </View>
          <View style={styles.fieldInput}>
            <Text style={styles.fieldLabel}>To</Text>
            <TextInput
              style={styles.input}
              placeholder="Destination station name or code"
              placeholderTextColor={colors.textMuted}
              value={toQuery}
              onChangeText={(text) => {
                setToQuery(text);
                setToStation(null);
                searchStations(text, "to");
              }}
              onFocus={() => setActiveField("to")}
            />
          </View>
        </View>

        {/* Station suggestions */}
        {suggestions.length > 0 && (
          <View style={styles.suggestions}>
            {suggestions.map((station) => (
              <TouchableOpacity
                key={station.code}
                style={styles.suggestionItem}
                onPress={() => selectStation(station, activeField)}
              >
                <Ionicons
                  name="train-outline"
                  size={16}
                  color={colors.textSecondary}
                />
                <View style={styles.suggestionText}>
                  <Text style={styles.suggestionName}>{station.name}</Text>
                  <Text style={styles.suggestionCode}>{station.code}</Text>
                </View>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* Search button */}
        <TouchableOpacity
          style={[
            styles.searchButton,
            (!fromStation || !toStation) && styles.searchButtonDisabled,
          ]}
          onPress={handleSearch}
          disabled={!fromStation || !toStation}
        >
          <Ionicons name="search" size={18} color={colors.textLight} />
          <Text style={styles.searchButtonText}>Find Trains</Text>
        </TouchableOpacity>
      </View>

      {/* Results */}
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
          <Text style={styles.emptyText}>No direct trains found</Text>
          <Text style={styles.emptySubtext}>
            Try different stations or check for connecting trains
          </Text>
        </View>
      )}

      {!loading && results.length > 0 && (
        <View style={styles.resultsSection}>
          <Text style={styles.resultsTitle}>
            {results.length} train{results.length !== 1 ? "s" : ""} found
          </Text>
          {results.map((train, index) => (
            <TouchableOpacity
              key={index}
              style={styles.resultCard}
              onPress={() =>
                navigation.navigate("TrainDetail", {
                  trainNumber: train.train_number,
                  trainName: train.train_name,
                })
              }
            >
              <View style={styles.resultHeader}>
                <Text style={styles.resultNumber}>{train.train_number}</Text>
                <Text style={styles.resultName}>{train.train_name}</Text>
              </View>

              <View style={styles.resultRoute}>
                <View style={styles.resultTimeBlock}>
                  <Text style={styles.resultTime}>
                    {train.departure || "--:--"}
                  </Text>
                  <Text style={styles.resultStationLabel}>Departure</Text>
                </View>

                <View style={styles.resultDuration}>
                  <Text style={styles.durationLine}>─────</Text>
                  <Text style={styles.durationText}>
                    {Math.round(train.duration_km)} km
                  </Text>
                  <Text style={styles.stopsText}>
                    {train.stops} stop{train.stops !== 1 ? "s" : ""}
                  </Text>
                </View>

                <View
                  style={[styles.resultTimeBlock, { alignItems: "flex-end" }]}
                >
                  <Text style={styles.resultTime}>
                    {train.arrival || "--:--"}
                  </Text>
                  <Text style={styles.resultStationLabel}>Arrival</Text>
                </View>
              </View>

              {train.run_days && (
                <View style={styles.runDays}>
                  {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(
                    (day) => (
                      <Text
                        key={day}
                        style={[
                          styles.dayLabel,
                          train.run_days.includes(day) && styles.dayLabelActive,
                        ]}
                      >
                        {day.charAt(0)}
                      </Text>
                    )
                  )}
                </View>
              )}
            </TouchableOpacity>
          ))}
        </View>
      )}

      <View style={{ height: 32 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  formCard: {
    backgroundColor: colors.surface,
    margin: 16,
    borderRadius: 16,
    padding: 20,
    elevation: 2,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 6,
  },
  formTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: colors.textPrimary,
    marginBottom: 20,
  },
  fieldContainer: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 8,
  },
  fieldIcon: {
    width: 32,
    alignItems: "center",
  },
  fieldInput: {
    flex: 1,
  },
  fieldLabel: {
    fontSize: 12,
    color: colors.textMuted,
    fontWeight: "600",
    marginBottom: 4,
  },
  input: {
    fontSize: 15,
    color: colors.textPrimary,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingVertical: 8,
  },
  swapButton: {
    alignSelf: "center",
    backgroundColor: colors.background,
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    marginVertical: 4,
  },
  suggestions: {
    backgroundColor: colors.background,
    borderRadius: 8,
    marginTop: 8,
    maxHeight: 200,
  },
  suggestionItem: {
    flexDirection: "row",
    alignItems: "center",
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
    gap: 10,
  },
  suggestionText: {
    flex: 1,
  },
  suggestionName: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  suggestionCode: {
    fontSize: 12,
    color: colors.textMuted,
  },
  searchButton: {
    flexDirection: "row",
    backgroundColor: colors.primary,
    borderRadius: 12,
    padding: 14,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 20,
    gap: 8,
  },
  searchButtonDisabled: {
    backgroundColor: colors.textMuted,
  },
  searchButtonText: {
    color: colors.textLight,
    fontSize: 16,
    fontWeight: "700",
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
    textAlign: "center",
    paddingHorizontal: 32,
  },
  resultsSection: {
    paddingHorizontal: 16,
  },
  resultsTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: colors.textPrimary,
    marginBottom: 12,
  },
  resultCard: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 16,
    marginBottom: 10,
    elevation: 1,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
  },
  resultHeader: {
    marginBottom: 12,
  },
  resultNumber: {
    fontSize: 13,
    fontWeight: "700",
    color: colors.primary,
  },
  resultName: {
    fontSize: 16,
    fontWeight: "600",
    color: colors.textPrimary,
    marginTop: 2,
  },
  resultRoute: {
    flexDirection: "row",
    alignItems: "center",
  },
  resultTimeBlock: {
    flex: 1,
  },
  resultTime: {
    fontSize: 20,
    fontWeight: "800",
    color: colors.textPrimary,
  },
  resultStationLabel: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 2,
  },
  resultDuration: {
    alignItems: "center",
    paddingHorizontal: 8,
  },
  durationLine: {
    color: colors.textMuted,
    fontSize: 12,
  },
  durationText: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.textSecondary,
  },
  stopsText: {
    fontSize: 10,
    color: colors.textMuted,
  },
  runDays: {
    flexDirection: "row",
    marginTop: 12,
    gap: 8,
  },
  dayLabel: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.textMuted,
  },
  dayLabelActive: {
    color: colors.primary,
  },
});
