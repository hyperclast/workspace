import { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  TouchableOpacity,
} from "react-native";
import { router } from "expo-router";
import { fetchMentions } from "../../../lib/api";
import { formatRelativeTime } from "../../../lib/formatters";

export default function MentionsScreen() {
  const [mentions, setMentions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const loadMentions = useCallback(async () => {
    try {
      setError(null);
      const data = await fetchMentions();
      setMentions(data.mentions || []);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setError(null);
        const data = await fetchMentions();
        if (!cancelled) setMentions(data.mentions || []);
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadMentions();
    setRefreshing(false);
  }, [loadMentions]);

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.centered}>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={mentions}
        keyExtractor={(item) => item.page_external_id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.mentionRow}
            onPress={() => router.push(`/page/${item.page_external_id}`)}
            accessibilityRole="button"
          >
            <View style={styles.mentionContent}>
              <Text style={styles.pageTitle} numberOfLines={1}>
                {item.page_title}
              </Text>
              <Text style={styles.projectName} numberOfLines={1}>
                {item.project_name}
              </Text>
            </View>
            <Text style={styles.time}>{formatRelativeTime(item.modified)}</Text>
          </TouchableOpacity>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No mentions yet</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#fff",
  },
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#fff",
  },
  mentionRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#eee",
  },
  mentionContent: {
    flex: 1,
    marginRight: 12,
  },
  pageTitle: {
    fontSize: 16,
    fontWeight: "500",
  },
  projectName: {
    fontSize: 13,
    color: "#666",
    marginTop: 2,
  },
  time: {
    fontSize: 12,
    color: "#999",
  },
  empty: {
    textAlign: "center",
    color: "#999",
    marginTop: 32,
    fontSize: 16,
  },
  error: {
    color: "#c00",
    fontSize: 16,
    textAlign: "center",
    padding: 16,
  },
});
