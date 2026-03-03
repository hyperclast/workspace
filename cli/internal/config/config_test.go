package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadDefaultsWhenFileNotExists(t *testing.T) {
	t.Setenv("HYPERCLAST_TOKEN", "")
	cfg, err := Load("/tmp/nonexistent-hyperclast-test/config.yaml")
	if err != nil {
		t.Fatalf("Load() returned error: %v", err)
	}
	if cfg.APIURL != defaultAPIURL {
		t.Errorf("APIURL = %q, want %q", cfg.APIURL, defaultAPIURL)
	}
	if cfg.Token != "" {
		t.Errorf("Token = %q, want empty", cfg.Token)
	}
}

func TestLoadFromFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "config.yaml")
	err := os.WriteFile(path, []byte("api_url: https://custom.example.com/api\ntoken: file-token\n"), 0600)
	if err != nil {
		t.Fatal(err)
	}

	cfg, err := Load(path)
	if err != nil {
		t.Fatalf("Load() returned error: %v", err)
	}
	if cfg.APIURL != "https://custom.example.com/api" {
		t.Errorf("APIURL = %q, want %q", cfg.APIURL, "https://custom.example.com/api")
	}
	if cfg.Token != "file-token" {
		t.Errorf("Token = %q, want %q", cfg.Token, "file-token")
	}
}

func TestHyperclastConfigEnvVar(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "custom-config.yaml")
	err := os.WriteFile(path, []byte("token: env-path-token\n"), 0600)
	if err != nil {
		t.Fatal(err)
	}

	t.Setenv("HYPERCLAST_CONFIG", path)

	cfg, err := Load("")
	if err != nil {
		t.Fatalf("Load() returned error: %v", err)
	}
	if cfg.Token != "env-path-token" {
		t.Errorf("Token = %q, want %q", cfg.Token, "env-path-token")
	}
	if cfg.path != path {
		t.Errorf("path = %q, want %q", cfg.path, path)
	}
}

func TestHyperclastConfigEnvVarOverriddenByFlag(t *testing.T) {
	dir := t.TempDir()

	envPath := filepath.Join(dir, "env-config.yaml")
	os.WriteFile(envPath, []byte("token: env-token\n"), 0600)

	flagPath := filepath.Join(dir, "flag-config.yaml")
	os.WriteFile(flagPath, []byte("token: flag-token\n"), 0600)

	t.Setenv("HYPERCLAST_CONFIG", envPath)

	cfg, err := Load(flagPath)
	if err != nil {
		t.Fatalf("Load() returned error: %v", err)
	}
	if cfg.Token != "flag-token" {
		t.Errorf("Token = %q, want %q (--config flag should take precedence)", cfg.Token, "flag-token")
	}
}

func TestHyperclastTokenEnvVar(t *testing.T) {
	t.Setenv("HYPERCLAST_TOKEN", "env-token-123")

	cfg, err := Load("/tmp/nonexistent-hyperclast-test/config.yaml")
	if err != nil {
		t.Fatalf("Load() returned error: %v", err)
	}
	if cfg.Token != "env-token-123" {
		t.Errorf("Token = %q, want %q", cfg.Token, "env-token-123")
	}
}

func TestHyperclastTokenEnvVarOverridesFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "config.yaml")
	os.WriteFile(path, []byte("token: file-token\n"), 0600)

	t.Setenv("HYPERCLAST_TOKEN", "env-override-token")

	cfg, err := Load(path)
	if err != nil {
		t.Fatalf("Load() returned error: %v", err)
	}
	if cfg.Token != "env-override-token" {
		t.Errorf("Token = %q, want %q (HYPERCLAST_TOKEN should override file token)", cfg.Token, "env-override-token")
	}
}

func TestHyperclastTokenEnvVarEmptyDoesNotOverride(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "config.yaml")
	os.WriteFile(path, []byte("token: file-token\n"), 0600)

	t.Setenv("HYPERCLAST_TOKEN", "")

	cfg, err := Load(path)
	if err != nil {
		t.Fatalf("Load() returned error: %v", err)
	}
	if cfg.Token != "file-token" {
		t.Errorf("Token = %q, want %q (empty env var should not override)", cfg.Token, "file-token")
	}
}
