import { useState } from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { router } from "expo-router";
import useAuthStore from "../../../stores/auth";

export default function SettingsScreen() {
  const logout = useAuthStore((s) => s.logout);
  const [loggingOut, setLoggingOut] = useState(false);

  async function handleLogout() {
    if (loggingOut) return;
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      router.replace("/login");
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Account</Text>
        <TouchableOpacity
          onPress={handleLogout}
          style={[styles.logoutBtn, loggingOut && styles.logoutBtnDisabled]}
          disabled={loggingOut}
        >
          <Text style={styles.logoutText}>{loggingOut ? "Logging out..." : "Log out"}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#fff",
    padding: 16,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: "600",
    color: "#999",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 12,
  },
  logoutBtn: {
    padding: 14,
    backgroundColor: "#f5f5f5",
    borderRadius: 8,
  },
  logoutBtnDisabled: {
    opacity: 0.5,
  },
  logoutText: {
    color: "#c00",
    fontSize: 16,
  },
});
