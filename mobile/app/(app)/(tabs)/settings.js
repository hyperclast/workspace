import { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  ScrollView,
  Alert,
} from "react-native";
import { router } from "expo-router";
import Constants from "expo-constants";
import useAuthStore from "../../../stores/auth";
import { fetchMe, fetchStorage, fetchDevices, revokeDevice } from "../../../lib/api";
import { formatRelativeTime, formatBytes } from "../../../lib/formatters";

export default function SettingsScreen() {
  const logout = useAuthStore((s) => s.logout);
  const [loggingOut, setLoggingOut] = useState(false);
  const [user, setUser] = useState(null);
  const [storage, setStorage] = useState(null);
  const [devices, setDevices] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const results = await Promise.allSettled([fetchMe(), fetchStorage(), fetchDevices()]);
      if (!cancelled) {
        const [userResult, storageResult, devicesResult] = results;
        if (userResult.status === "fulfilled") setUser(userResult.value);
        if (storageResult.status === "fulfilled") setStorage(storageResult.value);
        if (devicesResult.status === "fulfilled") setDevices(devicesResult.value);
        if (results.some((r) => r.status === "rejected")) {
          setError("Some data couldn't be loaded");
        }
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleRevoke = useCallback((device) => {
    Alert.alert("Remove device?", `"${device.name}" will be signed out.`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Remove",
        style: "destructive",
        onPress: async () => {
          try {
            await revokeDevice(device.client_id);
            setDevices((prev) => prev.filter((d) => d.client_id !== device.client_id));
          } catch {
            // Silently fail — device may already be revoked
          }
        },
      },
    ]);
  }, []);

  async function handleLogout() {
    if (loggingOut) return;
    setLoggingOut(true);
    try {
      await logout();
    } catch {
      // Server-side revocation failed but local cleanup succeeded (store's finally block)
    } finally {
      router.replace("/login");
    }
  }

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  const appVersion = Constants.expoConfig?.version || "0.0.0";

  return (
    <ScrollView style={styles.container}>
      {error && <Text style={styles.error}>{error}</Text>}
      {user && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Account</Text>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Username</Text>
            <Text style={styles.infoValue}>{user.username}</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Email</Text>
            <Text style={styles.infoValue}>{user.email}</Text>
          </View>
        </View>
      )}

      {storage && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Storage</Text>
          <Text style={styles.storageText}>
            {storage.file_count} files, {formatBytes(storage.total_bytes)} used
          </Text>
        </View>
      )}

      {devices && devices.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Devices</Text>
          {devices.map((device) => (
            <View key={device.client_id} style={styles.deviceRow}>
              <View style={styles.deviceInfo}>
                <View style={styles.deviceNameRow}>
                  <Text style={styles.deviceName}>{device.name}</Text>
                  {device.is_current && <Text style={styles.currentBadge}>Current</Text>}
                </View>
                <Text style={styles.deviceMeta}>
                  {device.os} · {formatRelativeTime(device.last_active)}
                </Text>
              </View>
              {!device.is_current && (
                <TouchableOpacity onPress={() => handleRevoke(device)}>
                  <Text style={styles.revokeText}>Remove</Text>
                </TouchableOpacity>
              )}
            </View>
          ))}
        </View>
      )}

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>App</Text>
        <Text style={styles.versionText}>Version {appVersion}</Text>
        <TouchableOpacity
          onPress={handleLogout}
          style={[styles.logoutBtn, loggingOut && styles.logoutBtnDisabled]}
          disabled={loggingOut}
        >
          <Text style={styles.logoutText}>{loggingOut ? "Signing out..." : "Sign out"}</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#fff",
    padding: 16,
  },
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#fff",
  },
  error: {
    color: "#c00",
    marginBottom: 8,
    fontSize: 14,
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
  infoRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    padding: 14,
    backgroundColor: "#f5f5f5",
    borderRadius: 8,
    marginBottom: 4,
  },
  infoLabel: {
    fontSize: 16,
    color: "#666",
  },
  infoValue: {
    fontSize: 16,
  },
  storageText: {
    fontSize: 16,
    padding: 14,
    backgroundColor: "#f5f5f5",
    borderRadius: 8,
  },
  deviceRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 14,
    backgroundColor: "#f5f5f5",
    borderRadius: 8,
    marginBottom: 4,
  },
  deviceInfo: {
    flex: 1,
    marginRight: 12,
  },
  deviceNameRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  deviceName: {
    fontSize: 16,
    fontWeight: "500",
  },
  currentBadge: {
    fontSize: 11,
    fontWeight: "600",
    color: "#007AFF",
    backgroundColor: "#E8F0FE",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    marginLeft: 8,
    overflow: "hidden",
  },
  deviceMeta: {
    fontSize: 13,
    color: "#666",
    marginTop: 2,
  },
  revokeText: {
    fontSize: 14,
    color: "#c00",
  },
  versionText: {
    fontSize: 14,
    color: "#999",
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
