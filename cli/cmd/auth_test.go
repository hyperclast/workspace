package cmd

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"

	"github.com/hyperclast/workspace/cli/internal/config"
)

func resetAuthFlags() {
	outputFmt = "text"
	quiet = false
	verbose = false
}

func TestAuthStatus_NotAuthenticated(t *testing.T) {
	resetAuthFlags()
	cfg = &config.Config{Token: ""}

	// Capture stdout
	oldStdout := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	err := authStatusCmd.RunE(authStatusCmd, []string{})

	_ = w.Close()
	os.Stdout = oldStdout

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	output, _ := io.ReadAll(r)
	if !strings.Contains(string(output), "Not authenticated") {
		t.Errorf("output = %q, expected to contain 'Not authenticated'", string(output))
	}
}

func TestAuthStatus_NotAuthenticated_JSON(t *testing.T) {
	resetAuthFlags()
	cfg = &config.Config{Token: ""}
	outputFmt = "json"

	// Capture stdout
	oldStdout := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	err := authStatusCmd.RunE(authStatusCmd, []string{})

	_ = w.Close()
	os.Stdout = oldStdout

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	output, _ := io.ReadAll(r)
	var result map[string]any
	if err := json.Unmarshal(output, &result); err != nil {
		t.Fatalf("output is not valid JSON: %v\nraw: %s", err, string(output))
	}
	if result["authenticated"] != false {
		t.Errorf("authenticated = %v, want false", result["authenticated"])
	}
}

func TestAuthStatus_Authenticated(t *testing.T) {
	resetAuthFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/users/me/" {
			t.Errorf("path = %q, want /users/me/", r.URL.Path)
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"external_id": "usr_123", "email": "test@example.com"}`))
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL: server.URL,
		Token:  "valid-token",
	}

	// Capture stdout
	oldStdout := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	err := authStatusCmd.RunE(authStatusCmd, []string{})

	_ = w.Close()
	os.Stdout = oldStdout

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	output, _ := io.ReadAll(r)
	if !strings.Contains(string(output), "test@example.com") {
		t.Errorf("output = %q, expected to contain email", string(output))
	}
}

func TestAuthStatus_Authenticated_JSON(t *testing.T) {
	resetAuthFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"external_id": "usr_123", "email": "test@example.com"}`))
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL: server.URL,
		Token:  "valid-token",
	}
	outputFmt = "json"

	// Capture stdout
	oldStdout := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	err := authStatusCmd.RunE(authStatusCmd, []string{})

	_ = w.Close()
	os.Stdout = oldStdout

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	output, _ := io.ReadAll(r)
	var result map[string]any
	if err := json.Unmarshal(output, &result); err != nil {
		t.Fatalf("output is not valid JSON: %v\nraw: %s", err, string(output))
	}
	if result["authenticated"] != true {
		t.Errorf("authenticated = %v, want true", result["authenticated"])
	}
	if result["email"] != "test@example.com" {
		t.Errorf("email = %v, want test@example.com", result["email"])
	}
}

func TestAuthStatus_TokenInvalid(t *testing.T) {
	resetAuthFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL: server.URL,
		Token:  "expired-token",
	}

	err := authStatusCmd.RunE(authStatusCmd, []string{})
	if err == nil {
		t.Fatal("expected error for expired token")
	}
	if !strings.Contains(err.Error(), "failed to verify token") {
		t.Errorf("error = %q, expected to contain 'failed to verify token'", err)
	}
}

func TestAuthStatus_TokenInvalid_JSON(t *testing.T) {
	resetAuthFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL: server.URL,
		Token:  "expired-token",
	}
	outputFmt = "json"

	// Capture stdout
	oldStdout := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	err := authStatusCmd.RunE(authStatusCmd, []string{})

	_ = w.Close()
	os.Stdout = oldStdout

	// In JSON mode, auth status returns nil even on error
	if err != nil {
		t.Fatalf("JSON mode should return nil error, got: %v", err)
	}

	output, _ := io.ReadAll(r)
	var result map[string]any
	if err := json.Unmarshal(output, &result); err != nil {
		t.Fatalf("output is not valid JSON: %v\nraw: %s", err, string(output))
	}
	if result["authenticated"] != false {
		t.Errorf("authenticated = %v, want false", result["authenticated"])
	}
	if _, hasError := result["error"]; !hasError {
		t.Error("expected 'error' field in JSON output")
	}
}

func TestAuthLogout_WhenNotAuthenticated(t *testing.T) {
	resetAuthFlags()
	cfg = &config.Config{Token: ""}

	// Capture stdout
	oldStdout := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	err := authLogoutCmd.RunE(authLogoutCmd, []string{})

	_ = w.Close()
	os.Stdout = oldStdout

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	output, _ := io.ReadAll(r)
	if !strings.Contains(string(output), "Not currently authenticated") {
		t.Errorf("output = %q, expected 'Not currently authenticated'", string(output))
	}
}
