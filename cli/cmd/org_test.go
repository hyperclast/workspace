package cmd

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/hyperclast/workspace/cli/internal/api"
	"github.com/hyperclast/workspace/cli/internal/config"
)

func resetOrgFlags() {
	outputFmt = "text"
	quiet = false
}

func TestOrgList_NotAuthenticated(t *testing.T) {
	resetOrgFlags()
	cfg = &config.Config{Token: ""}

	err := orgListCmd.RunE(orgListCmd, []string{})
	if err == nil {
		t.Fatal("expected error for unauthenticated user")
	}
	if !strings.Contains(err.Error(), "not authenticated") {
		t.Errorf("unexpected error: %s", err)
	}
}

func TestOrgList_Success(t *testing.T) {
	resetOrgFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/orgs/" {
			t.Errorf("path = %q, want /orgs/", r.URL.Path)
		}
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode([]api.Org{
			{ExternalID: "org_1", Name: "Org One", Domain: "one.com"},
			{ExternalID: "org_2", Name: "Org Two", Domain: "two.com"},
		})
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL: server.URL,
		Token:  "test-token",
	}

	// Capture stdout
	oldStdout := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	err := orgListCmd.RunE(orgListCmd, []string{})

	_ = w.Close()
	os.Stdout = oldStdout

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	output, _ := io.ReadAll(r)
	outputStr := string(output)
	if !strings.Contains(outputStr, "Org One") {
		t.Errorf("output should contain 'Org One', got %q", outputStr)
	}
	if !strings.Contains(outputStr, "Org Two") {
		t.Errorf("output should contain 'Org Two', got %q", outputStr)
	}
}

func TestOrgList_Empty(t *testing.T) {
	resetOrgFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`[]`))
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL: server.URL,
		Token:  "test-token",
	}

	// Capture stdout
	oldStdout := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	err := orgListCmd.RunE(orgListCmd, []string{})

	_ = w.Close()
	os.Stdout = oldStdout

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	output, _ := io.ReadAll(r)
	if !strings.Contains(string(output), "No organizations found") {
		t.Errorf("output = %q, expected 'No organizations found'", string(output))
	}
}

func TestOrgList_JSONOutput(t *testing.T) {
	resetOrgFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode([]api.Org{
			{ExternalID: "org_1", Name: "Org One"},
		})
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL: server.URL,
		Token:  "test-token",
	}
	outputFmt = "json"

	// Capture stdout
	oldStdout := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	err := orgListCmd.RunE(orgListCmd, []string{})

	_ = w.Close()
	os.Stdout = oldStdout

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	output, _ := io.ReadAll(r)
	var orgs []api.Org
	if err := json.Unmarshal(output, &orgs); err != nil {
		t.Fatalf("output is not valid JSON: %v\nraw: %s", err, string(output))
	}
	if len(orgs) != 1 {
		t.Fatalf("expected 1 org, got %d", len(orgs))
	}
	if orgs[0].Name != "Org One" {
		t.Errorf("name = %q, want %q", orgs[0].Name, "Org One")
	}
}

func TestOrgList_ShowsDefaultMarker(t *testing.T) {
	resetOrgFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode([]api.Org{
			{ExternalID: "org_1", Name: "Org One"},
			{ExternalID: "org_default", Name: "Default Org"},
		})
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL:   server.URL,
		Token:    "test-token",
		Defaults: config.Defaults{OrgID: "org_default"},
	}

	// Capture stdout
	oldStdout := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	err := orgListCmd.RunE(orgListCmd, []string{})

	_ = w.Close()
	os.Stdout = oldStdout

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	output, _ := io.ReadAll(r)
	if !strings.Contains(string(output), "(default)") {
		t.Errorf("output should contain '(default)' marker, got %q", string(output))
	}
}

func TestOrgCurrent_NoDefault(t *testing.T) {
	resetOrgFlags()
	cfg = &config.Config{Token: "test-token"}

	// Capture stdout
	oldStdout := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	err := orgCurrentCmd.RunE(orgCurrentCmd, []string{})

	_ = w.Close()
	os.Stdout = oldStdout

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	output, _ := io.ReadAll(r)
	if !strings.Contains(string(output), "No default organization set") {
		t.Errorf("output = %q, expected 'No default organization set'", string(output))
	}
}

func TestOrgCurrent_JSON(t *testing.T) {
	resetOrgFlags()
	cfg = &config.Config{
		Token:    "test-token",
		Defaults: config.Defaults{OrgID: "org_abc"},
	}
	outputFmt = "json"

	// Capture stdout
	oldStdout := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	err := orgCurrentCmd.RunE(orgCurrentCmd, []string{})

	_ = w.Close()
	os.Stdout = oldStdout

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	output, _ := io.ReadAll(r)
	var result map[string]string
	if err := json.Unmarshal(output, &result); err != nil {
		t.Fatalf("output is not valid JSON: %v\nraw: %s", err, string(output))
	}
	if result["org_id"] != "org_abc" {
		t.Errorf("org_id = %q, want %q", result["org_id"], "org_abc")
	}
}

func TestOrgUse_Success(t *testing.T) {
	resetOrgFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode([]api.Org{
			{ExternalID: "org_abc", Name: "My Org"},
		})
	}))
	defer server.Close()

	tmpDir := t.TempDir()
	cfgPath := filepath.Join(tmpDir, "config.yaml")
	loadedCfg, _ := config.Load(cfgPath)
	loadedCfg.APIURL = server.URL
	loadedCfg.Token = "test-token"
	cfg = loadedCfg

	err := orgUseCmd.RunE(orgUseCmd, []string{"org_abc"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.GetDefaultOrg() != "org_abc" {
		t.Errorf("default org = %q, want %q", cfg.GetDefaultOrg(), "org_abc")
	}
}

func TestOrgUse_NotFound(t *testing.T) {
	resetOrgFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode([]api.Org{
			{ExternalID: "org_other", Name: "Other Org"},
		})
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL: server.URL,
		Token:  "test-token",
	}

	err := orgUseCmd.RunE(orgUseCmd, []string{"org_nonexistent"})
	if err == nil {
		t.Fatal("expected error for non-existent org")
	}
	if !strings.Contains(err.Error(), "not found") {
		t.Errorf("error = %q, expected to contain 'not found'", err)
	}
}
