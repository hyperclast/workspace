package api

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

type Client struct {
	baseURL    string
	token      string
	httpClient *http.Client
}

func NewClient(baseURL, token string) *Client {
	return &Client{
		baseURL: baseURL,
		token:   token,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

func (c *Client) doRequest(method, path string, body interface{}) (*http.Response, error) {
	var reqBody io.Reader
	if body != nil {
		jsonBody, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal request body: %w", err)
		}
		reqBody = bytes.NewReader(jsonBody)
	}

	req, err := http.NewRequest(method, c.baseURL+path, reqBody)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+c.token)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	return c.httpClient.Do(req)
}

func (c *Client) Get(path string, result interface{}) error {
	resp, err := c.doRequest(http.MethodGet, path, nil)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusUnauthorized {
		return fmt.Errorf("authentication failed: invalid or expired token")
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("API error (%d): %s", resp.StatusCode, string(body))
	}

	if result != nil {
		if err := json.NewDecoder(resp.Body).Decode(result); err != nil {
			return fmt.Errorf("failed to decode response: %w", err)
		}
	}

	return nil
}

func (c *Client) Post(path string, body interface{}, result interface{}) error {
	resp, err := c.doRequest(http.MethodPost, path, body)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusUnauthorized {
		return fmt.Errorf("authentication failed: invalid or expired token")
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("API error (%d): %s", resp.StatusCode, string(respBody))
	}

	if result != nil {
		if err := json.NewDecoder(resp.Body).Decode(result); err != nil {
			return fmt.Errorf("failed to decode response: %w", err)
		}
	}

	return nil
}

func (c *Client) Put(path string, body interface{}, result interface{}) error {
	resp, err := c.doRequest(http.MethodPut, path, body)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusUnauthorized {
		return fmt.Errorf("authentication failed: invalid or expired token")
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("API error (%d): %s", resp.StatusCode, string(respBody))
	}

	if result != nil {
		if err := json.NewDecoder(resp.Body).Decode(result); err != nil {
			return fmt.Errorf("failed to decode response: %w", err)
		}
	}

	return nil
}

type User struct {
	ExternalID  string `json:"external_id"`
	Email       string `json:"email"`
	AccessToken string `json:"access_token"`
}

type Org struct {
	ExternalID string `json:"external_id"`
	Name       string `json:"name"`
	Domain     string `json:"domain"`
	IsPro      bool   `json:"is_pro"`
}

type OrgInfo struct {
	ExternalID string `json:"external_id"`
	Name       string `json:"name"`
	Domain     string `json:"domain"`
	IsPro      bool   `json:"is_pro"`
}

type Creator struct {
	ExternalID string `json:"external_id"`
	Email      string `json:"email"`
}

type Project struct {
	ExternalID  string  `json:"external_id"`
	Name        string  `json:"name"`
	Description string  `json:"description"`
	Version     string  `json:"version"`
	Modified    string  `json:"modified"`
	Created     string  `json:"created"`
	Creator     Creator `json:"creator"`
	Org         OrgInfo `json:"org"`
	Pages       []Page  `json:"pages,omitempty"`
}

type PageDetails struct {
	Content       string `json:"content,omitempty"`
	Filetype      string `json:"filetype,omitempty"`
	SchemaVersion int    `json:"schema_version,omitempty"`
}

type Page struct {
	ExternalID string       `json:"external_id"`
	Title      string       `json:"title"`
	Filetype   string       `json:"filetype,omitempty"`
	Updated    string       `json:"updated,omitempty"`
	Modified   string       `json:"modified,omitempty"`
	Created    string       `json:"created,omitempty"`
	Details    *PageDetails `json:"details,omitempty"`
}

type CreatePageRequest struct {
	ProjectID string       `json:"project_id"`
	Title     string       `json:"title"`
	Details   *PageDetails `json:"details,omitempty"`
}

type UpdatePageRequest struct {
	Title   string       `json:"title"`
	Details *PageDetails `json:"details,omitempty"`
	Mode    string       `json:"mode,omitempty"`
}

type UpdatePageContentRequest struct {
	Title   string       `json:"title"`
	Details *PageDetails `json:"details,omitempty"`
	Mode    string       `json:"mode"`
}

func (c *Client) GetCurrentUser() (*User, error) {
	var user User
	if err := c.Get("/users/me/", &user); err != nil {
		return nil, err
	}
	return &user, nil
}

func (c *Client) ListOrgs() ([]Org, error) {
	var orgs []Org
	if err := c.Get("/orgs/", &orgs); err != nil {
		return nil, err
	}
	return orgs, nil
}

func (c *Client) ListProjects(orgID string) ([]Project, error) {
	path := "/projects/"
	if orgID != "" {
		path = fmt.Sprintf("/projects/?org_id=%s", orgID)
	}
	var projects []Project
	if err := c.Get(path, &projects); err != nil {
		return nil, err
	}
	return projects, nil
}

func (c *Client) GetProject(projectID string) (*Project, error) {
	var project Project
	if err := c.Get(fmt.Sprintf("/projects/%s/?details=full", projectID), &project); err != nil {
		return nil, err
	}
	return &project, nil
}

func (c *Client) ListPages(projectID string) ([]Page, error) {
	if projectID != "" {
		project, err := c.GetProject(projectID)
		if err != nil {
			return nil, err
		}
		return project.Pages, nil
	}

	var result struct {
		Items []Page `json:"items"`
	}
	if err := c.Get("/pages/", &result); err != nil {
		return nil, err
	}
	return result.Items, nil
}

func (c *Client) GetPage(pageID string) (*Page, error) {
	var page Page
	if err := c.Get(fmt.Sprintf("/pages/%s/", pageID), &page); err != nil {
		return nil, err
	}
	return &page, nil
}

func (c *Client) CreatePage(projectID, title, content, filetype string) (*Page, error) {
	req := CreatePageRequest{
		ProjectID: projectID,
		Title:     title,
		Details: &PageDetails{
			Content:       content,
			Filetype:      filetype,
			SchemaVersion: 1,
		},
	}

	var page Page
	if err := c.Post("/pages/", req, &page); err != nil {
		return nil, err
	}
	return &page, nil
}

func (c *Client) UpdatePageContent(pageID, content, mode string) (*Page, error) {
	existingPage, err := c.GetPage(pageID)
	if err != nil {
		return nil, err
	}

	filetype := "txt"
	if existingPage.Details != nil && existingPage.Details.Filetype != "" {
		filetype = existingPage.Details.Filetype
	}

	req := UpdatePageContentRequest{
		Title: existingPage.Title,
		Details: &PageDetails{
			Content:       content,
			Filetype:      filetype,
			SchemaVersion: 1,
		},
		Mode: mode,
	}

	var page Page
	if err := c.Put(fmt.Sprintf("/pages/%s/", pageID), req, &page); err != nil {
		return nil, err
	}
	return &page, nil
}
