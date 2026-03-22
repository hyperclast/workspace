import { useEffect, useCallback, useMemo } from "react";
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  TouchableOpacity,
} from "react-native";
import { useLocalSearchParams, router, Stack } from "expo-router";
import useProjectStore from "../../../stores/projects";
import usePageStore from "../../../stores/pages";
import { formatRelativeTime } from "../../../lib/formatters";

export default function ProjectDetailScreen() {
  const { projectId } = useLocalSearchParams();
  const projects = useProjectStore((s) => s.projects);
  const fetchProjects = useProjectStore((s) => s.fetchProjects);
  const projectsLoading = useProjectStore((s) => s.loading);
  const projectsError = useProjectStore((s) => s.error);
  const createPage = usePageStore((s) => s.createPage);
  const pageSaving = usePageStore((s) => s.saving);

  const project = useMemo(
    () => projects.find((p) => p.external_id === projectId),
    [projects, projectId]
  );

  const pages = useMemo(() => {
    if (!project?.pages) return [];
    return [...project.pages].sort((a, b) => new Date(b.updated) - new Date(a.updated));
  }, [project?.pages]);

  useEffect(() => {
    if (!project) {
      fetchProjects();
    }
  }, [project, fetchProjects]);

  const onRefresh = useCallback(() => {
    fetchProjects();
  }, [fetchProjects]);

  const onCreatePage = useCallback(async () => {
    try {
      const page = await createPage(projectId, "Untitled");
      // Refresh project store so the page list reflects the new page.
      // The store catches errors internally and never throws, so a refresh
      // failure won't block navigation — stale data resolves on pull-to-refresh.
      await fetchProjects();
      router.push(`/page/${page.external_id}/edit`);
    } catch {
      // Error is set in the page store; screen can read it if needed
    }
  }, [projectId, createPage, fetchProjects]);

  if (!project && projectsLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (!project) {
    return (
      <View style={styles.centered}>
        <Text style={styles.error}>
          {projectsError ? "Couldn't load project" : "Project not found"}
        </Text>
      </View>
    );
  }

  return (
    <>
      <Stack.Screen options={{ title: project.name }} />
      <View style={styles.container}>
        {project.description ? <Text style={styles.description}>{project.description}</Text> : null}
        <FlatList
          data={pages}
          keyExtractor={(item) => item.external_id}
          refreshControl={<RefreshControl refreshing={projectsLoading} onRefresh={onRefresh} />}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={styles.pageRow}
              onPress={() => router.push(`/page/${item.external_id}`)}
              accessibilityRole="button"
            >
              <Text style={styles.pageTitle} numberOfLines={1}>
                {item.title || "Untitled"}
              </Text>
              <Text style={styles.pageTime}>{formatRelativeTime(item.updated)}</Text>
            </TouchableOpacity>
          )}
          ListEmptyComponent={<Text style={styles.empty}>No pages yet</Text>}
        />
        <TouchableOpacity
          style={styles.fab}
          onPress={onCreatePage}
          disabled={pageSaving}
          accessibilityRole="button"
          accessibilityLabel="New page"
          testID="fab-new-page"
        >
          <Text style={styles.fabText}>+</Text>
        </TouchableOpacity>
      </View>
    </>
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
  description: {
    fontSize: 14,
    color: "#666",
    padding: 16,
    paddingBottom: 8,
  },
  pageRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#eee",
  },
  pageTitle: {
    fontSize: 16,
    flex: 1,
    marginRight: 12,
  },
  pageTime: {
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
  fab: {
    position: "absolute",
    right: 20,
    bottom: 20,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: "#007AFF",
    justifyContent: "center",
    alignItems: "center",
    elevation: 4,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
  },
  fabText: {
    color: "#fff",
    fontSize: 28,
    lineHeight: 30,
  },
});
