import { useEffect, useState } from "react";
import { View, Text, FlatList, StyleSheet, ActivityIndicator, RefreshControl } from "react-native";
import { fetchProjects } from "../../../lib/api";

export default function ProjectListScreen() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  async function loadProjects() {
    try {
      const data = await fetchProjects();
      setProjects(Array.isArray(data) ? data : []);
      setError("");
    } catch (e) {
      setError(e.message || "Failed to load projects");
      if (e.message === "Unauthorized") return;
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadProjects();
  }, []);

  function onRefresh() {
    setRefreshing(true);
    loadProjects();
  }

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <FlatList
        data={projects}
        keyExtractor={(item) => item.external_id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        renderItem={({ item }) => (
          <View style={styles.projectRow}>
            <Text style={styles.projectName}>{item.name}</Text>
            {item.description ? (
              <Text style={styles.projectDesc} numberOfLines={2}>
                {item.description}
              </Text>
            ) : null}
            <Text style={styles.projectMeta}>
              {item.org?.name || "Personal"} · {item.pages?.length ?? 0} pages
            </Text>
          </View>
        )}
        ListEmptyComponent={!error ? <Text style={styles.empty}>No projects yet</Text> : null}
      />
    </View>
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
  projectRow: {
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#eee",
  },
  projectName: {
    fontSize: 17,
    fontWeight: "600",
    marginBottom: 4,
  },
  projectDesc: {
    fontSize: 14,
    color: "#666",
    marginBottom: 4,
  },
  projectMeta: {
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
    marginBottom: 8,
    fontSize: 14,
  },
});
