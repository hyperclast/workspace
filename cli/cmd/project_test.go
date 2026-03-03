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

// sampleProjectJSON returns a valid JSON response matching the api.Project struct.
func sampleProjectJSON() string {
	return `{
		"external_id": "proj_abc123",
		"name": "Build Logs",
		"description": "CI/CD pipeline output",
		"version": "",
		"modified": "2025-01-15T10:00:00Z",
		"created": "2025-01-15T10:00:00Z",
		"creator": {"external_id": "usr_001", "email": "test@example.com"},
		"org": {"external_id": "org_xyz", "name": "Test Org", "domain": "", "is_pro": false}
	}`
}

// resetProjectFlags resets package-level flag variables to their zero values.
func resetProjectFlags() {
	projectNewOrgID = ""
	projectNewDesc = ""
	projectNewSetUse = false
	outputFmt = "text"
	quiet = false
}

func TestProjectNew_NotAuthenticated(t *testing.T) {
	resetProjectFlags()
	cfg = &config.Config{Token: ""}

	err := projectNewCmd.RunE(projectNewCmd, []string{"My Project"})
	if err == nil {
		t.Fatal("expected error for unauthenticated user")
	}
	if err.Error() != "not authenticated. Run 'hyperclast auth login' first" {
		t.Errorf("unexpected error: %s", err)
	}
}

func TestProjectNew_EmptyName(t *testing.T) {
	resetProjectFlags()
	cfg = &config.Config{Token: "test-token"}

	err := projectNewCmd.RunE(projectNewCmd, []string{""})
	if err == nil {
		t.Fatal("expected error for empty name")
	}
	if err.Error() != "project name cannot be empty" {
		t.Errorf("unexpected error: %s", err)
	}
}

func TestProjectNew_WhitespaceOnlyName(t *testing.T) {
	resetProjectFlags()
	cfg = &config.Config{Token: "test-token"}

	err := projectNewCmd.RunE(projectNewCmd, []string{"   "})
	if err == nil {
		t.Fatal("expected error for whitespace-only name")
	}
	if err.Error() != "project name cannot be empty" {
		t.Errorf("unexpected error: %s", err)
	}
}

func TestProjectNew_NameTooLong(t *testing.T) {
	resetProjectFlags()
	cfg = &config.Config{Token: "test-token"}

	longName := strings.Repeat("a", 256)
	err := projectNewCmd.RunE(projectNewCmd, []string{longName})
	if err == nil {
		t.Fatal("expected error for name exceeding 255 characters")
	}
	if err.Error() != "project name too long (max 255 characters)" {
		t.Errorf("unexpected error: %s", err)
	}
}

func TestProjectNew_NameExactly255Chars(t *testing.T) {
	resetProjectFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusCreated)
		w.Write([]byte(sampleProjectJSON()))
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL:   server.URL,
		Token:    "test-token",
		Defaults: config.Defaults{OrgID: "org_xyz"},
	}

	name255 := strings.Repeat("a", 255)
	err := projectNewCmd.RunE(projectNewCmd, []string{name255})
	if err != nil {
		t.Fatalf("255-char name should be accepted, got error: %s", err)
	}
}

func TestProjectNew_NoOrgSpecified(t *testing.T) {
	resetProjectFlags()
	cfg = &config.Config{
		Token: "test-token",
		// No default org set, no --org flag
	}

	// Reset SilenceErrors so we can verify it gets set
	projectNewCmd.SilenceErrors = false

	err := projectNewCmd.RunE(projectNewCmd, []string{"My Project"})
	if err == nil {
		t.Fatal("expected error when no org specified")
	}
	if err.Error() != "no organization specified" {
		t.Errorf("unexpected error: %s", err)
	}
	if !projectNewCmd.SilenceErrors {
		t.Error("expected SilenceErrors to be set to prevent double error output")
	}
}

func TestProjectNew_ExplicitOrgOverridesDefault(t *testing.T) {
	resetProjectFlags()

	var receivedOrgID string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		var req api.CreateProjectRequest
		json.Unmarshal(body, &req)
		receivedOrgID = req.OrgID
		w.WriteHeader(http.StatusCreated)
		w.Write([]byte(sampleProjectJSON()))
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL: server.URL,
		Token:  "test-token",
		Defaults: config.Defaults{
			OrgID: "org_default",
		},
	}
	projectNewOrgID = "org_explicit"

	err := projectNewCmd.RunE(projectNewCmd, []string{"Build Logs"})
	if err != nil {
		t.Fatalf("unexpected error: %s", err)
	}
	if receivedOrgID != "org_explicit" {
		t.Errorf("expected org_explicit, got %s", receivedOrgID)
	}
}

func TestProjectNew_FallsBackToDefaultOrg(t *testing.T) {
	resetProjectFlags()

	var receivedOrgID string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		var req api.CreateProjectRequest
		json.Unmarshal(body, &req)
		receivedOrgID = req.OrgID
		w.WriteHeader(http.StatusCreated)
		w.Write([]byte(sampleProjectJSON()))
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL: server.URL,
		Token:  "test-token",
		Defaults: config.Defaults{
			OrgID: "org_default",
		},
	}

	err := projectNewCmd.RunE(projectNewCmd, []string{"Build Logs"})
	if err != nil {
		t.Fatalf("unexpected error: %s", err)
	}
	if receivedOrgID != "org_default" {
		t.Errorf("expected org_default, got %s", receivedOrgID)
	}
}

func TestProjectNew_SendsDescriptionWhenProvided(t *testing.T) {
	resetProjectFlags()

	var receivedDesc string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		var req api.CreateProjectRequest
		json.Unmarshal(body, &req)
		receivedDesc = req.Description
		w.WriteHeader(http.StatusCreated)
		w.Write([]byte(sampleProjectJSON()))
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL:   server.URL,
		Token:    "test-token",
		Defaults: config.Defaults{OrgID: "org_xyz"},
	}
	projectNewDesc = "CI/CD pipeline output"

	err := projectNewCmd.RunE(projectNewCmd, []string{"Build Logs"})
	if err != nil {
		t.Fatalf("unexpected error: %s", err)
	}
	if receivedDesc != "CI/CD pipeline output" {
		t.Errorf("expected description 'CI/CD pipeline output', got %q", receivedDesc)
	}
}

func TestProjectNew_OmitsDescriptionWhenEmpty(t *testing.T) {
	resetProjectFlags()

	var rawBody map[string]interface{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		json.Unmarshal(body, &rawBody)
		w.WriteHeader(http.StatusCreated)
		w.Write([]byte(sampleProjectJSON()))
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL:   server.URL,
		Token:    "test-token",
		Defaults: config.Defaults{OrgID: "org_xyz"},
	}
	// projectNewDesc is "" (default from resetProjectFlags)

	err := projectNewCmd.RunE(projectNewCmd, []string{"Build Logs"})
	if err != nil {
		t.Fatalf("unexpected error: %s", err)
	}
	if _, exists := rawBody["description"]; exists {
		t.Error("expected description to be omitted from JSON when empty")
	}
}

func TestProjectNew_UseFlagSavesDefaultProject(t *testing.T) {
	resetProjectFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusCreated)
		w.Write([]byte(sampleProjectJSON()))
	}))
	defer server.Close()

	tmpDir := t.TempDir()
	cfgPath := filepath.Join(tmpDir, "config.yaml")

	cfg = &config.Config{
		APIURL:   server.URL,
		Token:    "test-token",
		Defaults: config.Defaults{OrgID: "org_xyz"},
	}
	// Set private path field via Load so Save() writes to temp dir
	loadedCfg, err := config.Load(cfgPath)
	if err != nil {
		t.Fatalf("failed to load config: %s", err)
	}
	loadedCfg.APIURL = server.URL
	loadedCfg.Token = "test-token"
	loadedCfg.SetDefaultOrg("org_xyz")
	cfg = loadedCfg

	projectNewSetUse = true

	err = projectNewCmd.RunE(projectNewCmd, []string{"Build Logs"})
	if err != nil {
		t.Fatalf("unexpected error: %s", err)
	}

	if cfg.GetDefaultProject() != "proj_abc123" {
		t.Errorf("expected default project to be 'proj_abc123', got %q", cfg.GetDefaultProject())
	}

	// Verify it was persisted to disk
	reloaded, err := config.Load(cfgPath)
	if err != nil {
		t.Fatalf("failed to reload config: %s", err)
	}
	if reloaded.GetDefaultProject() != "proj_abc123" {
		t.Errorf("expected persisted default project 'proj_abc123', got %q", reloaded.GetDefaultProject())
	}
}

func TestProjectNew_WithoutUseFlagDoesNotSetDefault(t *testing.T) {
	resetProjectFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusCreated)
		w.Write([]byte(sampleProjectJSON()))
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL:   server.URL,
		Token:    "test-token",
		Defaults: config.Defaults{OrgID: "org_xyz"},
	}

	err := projectNewCmd.RunE(projectNewCmd, []string{"Build Logs"})
	if err != nil {
		t.Fatalf("unexpected error: %s", err)
	}

	if cfg.GetDefaultProject() != "" {
		t.Errorf("expected no default project, got %q", cfg.GetDefaultProject())
	}
}

func TestProjectNew_JSONOutput(t *testing.T) {
	resetProjectFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusCreated)
		w.Write([]byte(sampleProjectJSON()))
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL:   server.URL,
		Token:    "test-token",
		Defaults: config.Defaults{OrgID: "org_xyz"},
	}
	outputFmt = "json"

	// Capture stdout
	oldStdout := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	err := projectNewCmd.RunE(projectNewCmd, []string{"Build Logs"})

	w.Close()
	os.Stdout = oldStdout

	if err != nil {
		t.Fatalf("unexpected error: %s", err)
	}

	output, _ := io.ReadAll(r)

	var project api.Project
	if err := json.Unmarshal(output, &project); err != nil {
		t.Fatalf("output is not valid JSON: %s\nraw output: %s", err, string(output))
	}
	if project.ExternalID != "proj_abc123" {
		t.Errorf("expected external_id 'proj_abc123', got %q", project.ExternalID)
	}
	if project.Name != "Build Logs" {
		t.Errorf("expected name 'Build Logs', got %q", project.Name)
	}
}

func TestProjectNew_APIErrorPropagation(t *testing.T) {
	resetProjectFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusForbidden)
		w.Write([]byte(`{"detail": "You do not have permission to create projects in this organization"}`))
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL:   server.URL,
		Token:    "test-token",
		Defaults: config.Defaults{OrgID: "org_xyz"},
	}

	err := projectNewCmd.RunE(projectNewCmd, []string{"Build Logs"})
	if err == nil {
		t.Fatal("expected error from API")
	}
	expected := "failed to create project: "
	if len(err.Error()) < len(expected) || err.Error()[:len(expected)] != expected {
		t.Errorf("expected error to start with %q, got %q", expected, err.Error())
	}
}

func TestProjectNew_SendsCorrectHTTPMethod(t *testing.T) {
	resetProjectFlags()

	var receivedMethod string
	var receivedPath string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedMethod = r.Method
		receivedPath = r.URL.Path
		w.WriteHeader(http.StatusCreated)
		w.Write([]byte(sampleProjectJSON()))
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL:   server.URL,
		Token:    "test-token",
		Defaults: config.Defaults{OrgID: "org_xyz"},
	}

	err := projectNewCmd.RunE(projectNewCmd, []string{"Build Logs"})
	if err != nil {
		t.Fatalf("unexpected error: %s", err)
	}
	if receivedMethod != "POST" {
		t.Errorf("expected POST, got %s", receivedMethod)
	}
	if receivedPath != "/projects/" {
		t.Errorf("expected /projects/, got %s", receivedPath)
	}
}

func TestProjectNew_SendsAuthHeader(t *testing.T) {
	resetProjectFlags()

	var receivedAuth string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedAuth = r.Header.Get("Authorization")
		w.WriteHeader(http.StatusCreated)
		w.Write([]byte(sampleProjectJSON()))
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL:   server.URL,
		Token:    "my-secret-token",
		Defaults: config.Defaults{OrgID: "org_xyz"},
	}

	err := projectNewCmd.RunE(projectNewCmd, []string{"Build Logs"})
	if err != nil {
		t.Fatalf("unexpected error: %s", err)
	}
	if receivedAuth != "Bearer my-secret-token" {
		t.Errorf("expected 'Bearer my-secret-token', got %q", receivedAuth)
	}
}
