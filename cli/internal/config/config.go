package config

import (
	"fmt"
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

type Defaults struct {
	OrgID     string `yaml:"org_id,omitempty"`
	ProjectID string `yaml:"project_id,omitempty"`
}

type Config struct {
	APIURL   string   `yaml:"api_url"`
	Token    string   `yaml:"token,omitempty"`
	Defaults Defaults `yaml:"defaults,omitempty"`

	path string
}

const defaultAPIURL = "https://hyperclast.com/api"

func DefaultPath() string {
	homeDir, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	return filepath.Join(homeDir, ".config", "hyperclast", "config.yaml")
}

func Load(path string) (*Config, error) {
	if path == "" {
		path = DefaultPath()
	}

	cfg := &Config{
		APIURL: defaultAPIURL,
		path:   path,
	}

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return cfg, nil
		}
		return nil, fmt.Errorf("failed to read config file: %w", err)
	}

	if err := yaml.Unmarshal(data, cfg); err != nil {
		return nil, fmt.Errorf("failed to parse config file: %w", err)
	}

	cfg.path = path
	return cfg, nil
}

func (c *Config) Save() error {
	if c.path == "" {
		c.path = DefaultPath()
	}

	dir := filepath.Dir(c.path)
	if err := os.MkdirAll(dir, 0700); err != nil {
		return fmt.Errorf("failed to create config directory: %w", err)
	}

	data, err := yaml.Marshal(c)
	if err != nil {
		return fmt.Errorf("failed to serialize config: %w", err)
	}

	if err := os.WriteFile(c.path, data, 0600); err != nil {
		return fmt.Errorf("failed to write config file: %w", err)
	}

	return nil
}

func (c *Config) IsAuthenticated() bool {
	return c.Token != ""
}

func (c *Config) SetToken(token string) {
	c.Token = token
}

func (c *Config) ClearToken() {
	c.Token = ""
}

func (c *Config) SetDefaultOrg(orgID string) {
	c.Defaults.OrgID = orgID
}

func (c *Config) SetDefaultProject(projectID string) {
	c.Defaults.ProjectID = projectID
}

func (c *Config) GetDefaultOrg() string {
	return c.Defaults.OrgID
}

func (c *Config) GetDefaultProject() string {
	return c.Defaults.ProjectID
}

func (c *Config) Path() string {
	return c.path
}
