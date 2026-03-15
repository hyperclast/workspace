import { View, Text, StyleSheet } from "react-native";

export default function MentionsScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.placeholder}>Mentions will appear here</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#fff",
  },
  placeholder: {
    color: "#999",
    fontSize: 16,
  },
});
