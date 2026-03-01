/**
 * Train Tracker India - Main Application Entry Point
 *
 * A mobile application for tracking Indian Railways trains in real-time.
 * Features:
 * - Search trains by number or name
 * - Live train running status
 * - ETA calculation to destination station
 * - Route with all intermediate stops
 * - Find trains between two stations
 */

import React from "react";
import { StatusBar } from "expo-status-bar";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { Ionicons } from "@expo/vector-icons";

import { HomeScreen } from "./screens/HomeScreen";
import { TrainDetailScreen } from "./screens/TrainDetailScreen";
import { ETAScreen } from "./screens/ETAScreen";
import { StationSearchScreen } from "./screens/StationSearchScreen";
import { colors } from "./utils/colors";

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

function HomeTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textMuted,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.divider,
          height: 60,
          paddingBottom: 8,
          paddingTop: 4,
        },
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: "600",
        },
        headerShown: false,
      }}
    >
      <Tab.Screen
        name="HomeTab"
        component={HomeScreen}
        options={{
          tabBarLabel: "Track Train",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="train" size={size} color={color} />
          ),
          tabBarAccessibilityLabel: "Track Train tab",
        }}
      />
      <Tab.Screen
        name="StationSearch"
        component={StationSearchScreen}
        options={{
          tabBarLabel: "Stations",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="swap-horizontal" size={size} color={color} />
          ),
          tabBarAccessibilityLabel: "Search stations tab",
        }}
      />
    </Tab.Navigator>
  );
}

export default function App() {
  return (
    <NavigationContainer>
      <StatusBar style="light" />
      <Stack.Navigator
        screenOptions={{
          headerStyle: {
            backgroundColor: colors.primary,
          },
          headerTintColor: colors.textLight,
          headerTitleStyle: {
            fontWeight: "700",
          },
          headerBackTitleVisible: false,
        }}
      >
        <Stack.Screen
          name="Home"
          component={HomeTabs}
          options={{ headerShown: false }}
        />
        <Stack.Screen
          name="TrainDetail"
          component={TrainDetailScreen}
          options={({ route }) => ({
            title: route.params.trainName || "Train Details",
            headerAccessibilityLabel: `${route.params.trainName || "Train"} details`,
          })}
        />
        <Stack.Screen
          name="ETA"
          component={ETAScreen}
          options={({ route }) => ({
            title: `ETA to ${route.params.stationName || route.params.stationCode}`,
            headerAccessibilityLabel: `Estimated arrival to ${route.params.stationName || route.params.stationCode}`,
          })}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
