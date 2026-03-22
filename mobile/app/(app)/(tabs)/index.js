import { useEffect, useCallback, useMemo } from "react";
import {
  View,
  Text,
  SectionList,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  TouchableOpacity,
} from "react-native";
import { router } from "expo-router";
import useProjectStore from "../../../stores/projects";

export default function ProjectListScreen() {
  const projects = useProjectStore((s) => s.projects);
  const loading = useProjectStore((s) => s.loading);
  const error = useProjectStore((s) => s.error);
  const fetchProjects = useProjectStore((s) => s.fetchProjects);

  useEffect(() => {
    fetchProjects();
  }, []);

  const onRefresh = useCallback(() => {
    fetchProjects();
  }, [fetchProjects]);

  const sections = useMemo(() => {
    if (projects.length === 0) return [];
    const grouped = new Map();
    for (const project of projects) {
      const orgKey = project.org?.external_id || "_personal";
      const orgName = project.org?.name || "Personal";
      if (!grouped.has(orgKey)) {
        grouped.set(orgKey, { title: orgName, data: [] });
      }
      grouped.get(orgKey).data.push(project);
    }
    return Array.from(grouped.values());
  }, [projects]);

  const showSectionHeaders = sections.length > 1;

  if (loading && projects.length === 0) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <SectionList
        sections={sections}
        keyExtractor={(item) => item.external_id}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={onRefresh} />}
        renderSectionHeader={({ section }) =>
          showSectionHeaders ? (
            <View style={styles.sectionHeader}>
              <Text style={styles.sectionHeaderText}>{section.title}</Text>
            </View>
          ) : null
        }
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.projectRow}
            onPress={() => router.push(`/project/${item.external_id}`)}
            accessibilityRole="button"
          >
            <Text style={styles.projectName}>{item.name}</Text>
            {item.description ? (
              <Text style={styles.projectDesc} numberOfLines={2}>
                {item.description}
              </Text>
            ) : null}
            <Text style={styles.projectMeta}>{item.pages?.length ?? 0} pages</Text>
          </TouchableOpacity>
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
  sectionHeader: {
    backgroundColor: "#f5f5f5",
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  sectionHeaderText: {
    fontSize: 13,
    fontWeight: "600",
    color: "#999",
    textTransform: "uppercase",
    letterSpacing: 0.5,
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
