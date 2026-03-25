import { useEffect, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
} from "react-native";
import { useLocalSearchParams, router, Stack } from "expo-router";
import Markdown from "react-native-markdown-display";
import usePageStore from "../../../../stores/pages";

const INTERNAL_LINK_RE = /^\/pages\/([^/]+)\/?$/;

export default function PageViewScreen() {
  const { pageId } = useLocalSearchParams();
  const currentPage = usePageStore((s) => s.currentPage);
  const loading = usePageStore((s) => s.loading);
  const error = usePageStore((s) => s.error);
  const fetchPage = usePageStore((s) => s.fetchPage);
  const clearPage = usePageStore((s) => s.clearPage);

  useEffect(() => {
    fetchPage(pageId);
    return () => clearPage();
  }, [pageId]);

  const onLinkPress = useCallback((url) => {
    const match = url.match(INTERNAL_LINK_RE);
    if (match) {
      router.push(`/page/${match[1]}`);
      return false;
    }
    return true;
  }, []);

  const headerRight = useCallback(() => {
    if (!currentPage?.is_owner) return null;
    return (
      <TouchableOpacity onPress={() => router.push(`/page/${pageId}/edit`)} testID="edit-button">
        <Text style={styles.editButton}>Edit</Text>
      </TouchableOpacity>
    );
  }, [currentPage?.is_owner, pageId]);

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
        <Text style={styles.error}>Page not found</Text>
      </View>
    );
  }

  if (!currentPage) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  const content = currentPage.details?.content || "";

  return (
    <>
      <Stack.Screen
        options={{
          title: currentPage.title || "Untitled",
          headerRight,
        }}
      />
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <Markdown onLinkPress={onLinkPress}>{content}</Markdown>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#fff",
  },
  content: {
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
    fontSize: 16,
    textAlign: "center",
    padding: 16,
  },
  editButton: {
    color: "#007AFF",
    fontSize: 16,
    fontWeight: "600",
  },
});
