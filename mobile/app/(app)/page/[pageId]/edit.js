import { useState, useCallback, useEffect } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { useLocalSearchParams, router, Stack, useNavigation } from "expo-router";
import usePageStore from "../../../../stores/pages";
import useProjectStore from "../../../../stores/projects";

export default function PageEditScreen() {
  const { pageId } = useLocalSearchParams();
  const currentPage = usePageStore((s) => s.currentPage);
  const loading = usePageStore((s) => s.loading);
  const saving = usePageStore((s) => s.saving);
  const error = usePageStore((s) => s.error);
  const updatePage = usePageStore((s) => s.updatePage);
  const fetchPage = usePageStore((s) => s.fetchPage);
  const fetchProjects = useProjectStore((s) => s.fetchProjects);
  const navigation = useNavigation();

  useEffect(() => {
    if (!currentPage || currentPage.external_id !== pageId) {
      fetchPage(pageId);
    }
  }, [pageId]);

  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [originalTitle, setOriginalTitle] = useState("");
  const [originalContent, setOriginalContent] = useState("");

  useEffect(() => {
    if (currentPage) {
      const t = currentPage.title || "";
      const c = currentPage.details?.content || "";
      setTitle(t);
      setContent(c);
      setOriginalTitle(t);
      setOriginalContent(c);
    }
  }, [currentPage?.external_id]);

  const isDirty = title !== originalTitle || content !== originalContent;

  const onSave = useCallback(async () => {
    try {
      await updatePage(pageId, { title, details: { content } });
      // Mark form as clean so the beforeRemove listener won't show
      // the "Discard changes?" prompt when router.back() fires.
      setOriginalTitle(title);
      setOriginalContent(content);
      // Refresh project store so the project detail and home screens show
      // updated page titles/counts. The store catches errors internally and
      // never throws, so a refresh failure won't block navigation — the user
      // just sees slightly stale project data until they pull to refresh.
      await fetchProjects();
      router.back();
    } catch {
      // Error is set in the page store and displayed via the error state below
    }
  }, [pageId, title, content, updatePage, fetchProjects]);

  useEffect(() => {
    const unsubscribe = navigation.addListener("beforeRemove", (e) => {
      if (!isDirty) return;
      e.preventDefault();
      Alert.alert("Discard changes?", "You have unsaved changes.", [
        { text: "Cancel", style: "cancel" },
        {
          text: "Discard",
          style: "destructive",
          onPress: () => navigation.dispatch(e.data.action),
        },
      ]);
    });
    return unsubscribe;
  }, [navigation, isDirty]);

  const headerRight = useCallback(
    () => (
      <TouchableOpacity onPress={onSave} disabled={saving} testID="save-button">
        {saving ? <ActivityIndicator size="small" /> : <Text style={styles.saveButton}>Save</Text>}
      </TouchableOpacity>
    ),
    [onSave, saving]
  );

  if (error && !currentPage) {
    return (
      <View style={styles.centered}>
        <Text style={styles.error}>Page not found</Text>
      </View>
    );
  }

  if (loading || !currentPage || currentPage.external_id !== pageId) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  return (
    <>
      <Stack.Screen options={{ title: "Edit", headerRight }} />
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={100}
      >
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <TextInput
          style={styles.titleInput}
          value={title}
          onChangeText={setTitle}
          placeholder="Title"
          testID="title-input"
        />
        <TextInput
          style={styles.contentInput}
          value={content}
          onChangeText={setContent}
          placeholder="Start writing..."
          multiline
          textAlignVertical="top"
          testID="content-input"
        />
      </KeyboardAvoidingView>
    </>
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
  titleInput: {
    fontSize: 20,
    fontWeight: "600",
    borderBottomWidth: 1,
    borderBottomColor: "#eee",
    paddingVertical: 12,
    marginBottom: 12,
  },
  contentInput: {
    flex: 1,
    fontSize: 16,
    lineHeight: 24,
  },
  error: {
    color: "#c00",
    fontSize: 14,
    marginBottom: 8,
  },
  saveButton: {
    color: "#007AFF",
    fontSize: 16,
    fontWeight: "600",
  },
});
