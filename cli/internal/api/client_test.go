package api

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// --- Request header tests ---

func TestRequestHeaders(t *testing.T) {
	var receivedHeaders http.Header
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedHeaders = r.Header
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{}`))
	}))
	defer server.Close()

	client := NewClient(server.URL, "test-token-abc")
	_ = client.Get("/test/", &struct{}{})

	if auth := receivedHeaders.Get("Authorization"); auth != "Bearer test-token-abc" {
		t.Errorf("Authorization = %q, want %q", auth, "Bearer test-token-abc")
	}
	if ct := receivedHeaders.Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type = %q, want %q", ct, "application/json")
	}
	if accept := receivedHeaders.Get("Accept"); accept != "application/json" {
		t.Errorf("Accept = %q, want %q", accept, "application/json")
	}
	clientHeader := receivedHeaders.Get("X-Hyperclast-Client")
	if !strings.HasPrefix(clientHeader, "client=cli; version=") {
		t.Errorf("X-Hyperclast-Client = %q, expected prefix 'client=cli; version='", clientHeader)
	}
}

// --- Error handling tests ---

func TestGet_Unauthorized(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		_, _ = w.Write([]byte(`{"detail": "invalid token"}`))
	}))
	defer server.Close()

	client := NewClient(server.URL, "bad-token")
	err := client.Get("/test/", &struct{}{})
	if err == nil {
		t.Fatal("expected error for 401 response")
	}
	if !strings.Contains(err.Error(), "authentication failed") {
		t.Errorf("error = %q, expected to contain 'authentication failed'", err)
	}
}

func TestPost_Unauthorized(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
	}))
	defer server.Close()

	client := NewClient(server.URL, "bad-token")
	err := client.Post("/test/", nil, &struct{}{})
	if err == nil {
		t.Fatal("expected error for 401 response")
	}
	if !strings.Contains(err.Error(), "authentication failed") {
		t.Errorf("error = %q, expected to contain 'authentication failed'", err)
	}
}

func TestPut_Unauthorized(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
	}))
	defer server.Close()

	client := NewClient(server.URL, "bad-token")
	err := client.Put("/test/", nil, &struct{}{})
	if err == nil {
		t.Fatal("expected error for 401 response")
	}
	if !strings.Contains(err.Error(), "authentication failed") {
		t.Errorf("error = %q, expected to contain 'authentication failed'", err)
	}
}

func TestDelete_Unauthorized(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
	}))
	defer server.Close()

	client := NewClient(server.URL, "bad-token")
	err := client.Delete("/test/")
	if err == nil {
		t.Fatal("expected error for 401 response")
	}
	if !strings.Contains(err.Error(), "authentication failed") {
		t.Errorf("error = %q, expected to contain 'authentication failed'", err)
	}
}

func TestGet_ServerError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = w.Write([]byte(`Internal Server Error`))
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	err := client.Get("/test/", &struct{}{})
	if err == nil {
		t.Fatal("expected error for 500 response")
	}
	if !strings.Contains(err.Error(), "API error (500)") {
		t.Errorf("error = %q, expected to contain 'API error (500)'", err)
	}
	if !strings.Contains(err.Error(), "Internal Server Error") {
		t.Errorf("error = %q, expected to contain body text", err)
	}
}

func TestGet_Forbidden(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusForbidden)
		_, _ = w.Write([]byte(`{"detail": "no access"}`))
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	err := client.Get("/test/", &struct{}{})
	if err == nil {
		t.Fatal("expected error for 403 response")
	}
	if !strings.Contains(err.Error(), "API error (403)") {
		t.Errorf("error = %q, expected to contain 'API error (403)'", err)
	}
}

func TestGet_NotFound(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"detail": "not found"}`))
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	err := client.Get("/test/", &struct{}{})
	if err == nil {
		t.Fatal("expected error for 404 response")
	}
	if !strings.Contains(err.Error(), "API error (404)") {
		t.Errorf("error = %q, expected to contain 'API error (404)'", err)
	}
}

// --- GetCurrentUser ---

func TestGetCurrentUser_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			t.Errorf("method = %q, want GET", r.Method)
		}
		if r.URL.Path != "/users/me/" {
			t.Errorf("path = %q, want /users/me/", r.URL.Path)
		}
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(User{
			ExternalID: "usr_123",
			Email:      "test@example.com",
		})
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	user, err := client.GetCurrentUser()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if user.ExternalID != "usr_123" {
		t.Errorf("ExternalID = %q, want %q", user.ExternalID, "usr_123")
	}
	if user.Email != "test@example.com" {
		t.Errorf("Email = %q, want %q", user.Email, "test@example.com")
	}
}

func TestGetCurrentUser_AuthFailure(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
	}))
	defer server.Close()

	client := NewClient(server.URL, "bad-token")
	_, err := client.GetCurrentUser()
	if err == nil {
		t.Fatal("expected error")
	}
	if !strings.Contains(err.Error(), "authentication failed") {
		t.Errorf("error = %q, expected 'authentication failed'", err)
	}
}

// --- ListOrgs ---

func TestListOrgs_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/orgs/" {
			t.Errorf("path = %q, want /orgs/", r.URL.Path)
		}
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode([]Org{
			{ExternalID: "org_1", Name: "Org One"},
			{ExternalID: "org_2", Name: "Org Two"},
		})
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	orgs, err := client.ListOrgs()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(orgs) != 2 {
		t.Fatalf("len(orgs) = %d, want 2", len(orgs))
	}
	if orgs[0].Name != "Org One" {
		t.Errorf("orgs[0].Name = %q, want %q", orgs[0].Name, "Org One")
	}
}

func TestListOrgs_Empty(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`[]`))
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	orgs, err := client.ListOrgs()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(orgs) != 0 {
		t.Errorf("len(orgs) = %d, want 0", len(orgs))
	}
}

// --- ListProjects ---

func TestListProjects_WithoutOrgFilter(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/projects/" {
			t.Errorf("path = %q, want /projects/", r.URL.Path)
		}
		if q := r.URL.Query().Get("org_id"); q != "" {
			t.Errorf("org_id query param = %q, want empty", q)
		}
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode([]Project{
			{ExternalID: "proj_1", Name: "Project One"},
		})
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	projects, err := client.ListProjects("")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(projects) != 1 {
		t.Fatalf("len(projects) = %d, want 1", len(projects))
	}
}

func TestListProjects_WithOrgFilter(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/projects/" {
			t.Errorf("path = %q, want /projects/", r.URL.Path)
		}
		if q := r.URL.Query().Get("org_id"); q != "org_abc" {
			t.Errorf("org_id = %q, want %q", q, "org_abc")
		}
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode([]Project{
			{ExternalID: "proj_1", Name: "Filtered Project"},
		})
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	projects, err := client.ListProjects("org_abc")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(projects) != 1 {
		t.Fatalf("len(projects) = %d, want 1", len(projects))
	}
	if projects[0].Name != "Filtered Project" {
		t.Errorf("projects[0].Name = %q, want %q", projects[0].Name, "Filtered Project")
	}
}

// --- GetProject ---

func TestGetProject_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/projects/proj_123/" {
			t.Errorf("path = %q, want /projects/proj_123/", r.URL.Path)
		}
		if q := r.URL.Query().Get("details"); q != "full" {
			t.Errorf("details = %q, want %q", q, "full")
		}
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(Project{
			ExternalID: "proj_123",
			Name:       "My Project",
			Pages: []Page{
				{ExternalID: "page_1", Title: "Page One"},
				{ExternalID: "page_2", Title: "Page Two"},
			},
		})
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	project, err := client.GetProject("proj_123")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if project.ExternalID != "proj_123" {
		t.Errorf("ExternalID = %q, want %q", project.ExternalID, "proj_123")
	}
	if len(project.Pages) != 2 {
		t.Errorf("len(Pages) = %d, want 2", len(project.Pages))
	}
}

func TestGetProject_NotFound(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"detail": "not found"}`))
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	_, err := client.GetProject("proj_nonexistent")
	if err == nil {
		t.Fatal("expected error for not found project")
	}
	if !strings.Contains(err.Error(), "404") {
		t.Errorf("error = %q, expected to contain '404'", err)
	}
}

// --- CreateProject ---

func TestCreateProject_RequestBody(t *testing.T) {
	var receivedBody CreateProjectRequest
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			t.Errorf("method = %q, want POST", r.Method)
		}
		if r.URL.Path != "/projects/" {
			t.Errorf("path = %q, want /projects/", r.URL.Path)
		}
		body, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(body, &receivedBody)
		w.WriteHeader(http.StatusCreated)
		_ = json.NewEncoder(w).Encode(Project{
			ExternalID: "proj_new",
			Name:       "New Project",
		})
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	project, err := client.CreateProject("org_abc", "New Project", "A description")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if receivedBody.OrgID != "org_abc" {
		t.Errorf("request org_id = %q, want %q", receivedBody.OrgID, "org_abc")
	}
	if receivedBody.Name != "New Project" {
		t.Errorf("request name = %q, want %q", receivedBody.Name, "New Project")
	}
	if receivedBody.Description != "A description" {
		t.Errorf("request description = %q, want %q", receivedBody.Description, "A description")
	}
	if project.ExternalID != "proj_new" {
		t.Errorf("ExternalID = %q, want %q", project.ExternalID, "proj_new")
	}
}

func TestCreateProject_OmitsEmptyDescription(t *testing.T) {
	var rawBody map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(body, &rawBody)
		w.WriteHeader(http.StatusCreated)
		_ = json.NewEncoder(w).Encode(Project{ExternalID: "proj_new"})
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	_, err := client.CreateProject("org_abc", "Project", "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if _, exists := rawBody["description"]; exists {
		t.Error("expected description to be omitted from JSON when empty")
	}
}

// --- ListPages ---

func TestListPages_WithProjectID(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// ListPages with projectID calls GetProject, which hits /projects/{id}/?details=full
		if r.URL.Path != "/projects/proj_abc/" {
			t.Errorf("path = %q, want /projects/proj_abc/", r.URL.Path)
		}
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(Project{
			ExternalID: "proj_abc",
			Pages: []Page{
				{ExternalID: "page_1", Title: "Page One"},
				{ExternalID: "page_2", Title: "Page Two"},
			},
		})
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	pages, err := client.ListPages("proj_abc")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(pages) != 2 {
		t.Fatalf("len(pages) = %d, want 2", len(pages))
	}
	if pages[0].Title != "Page One" {
		t.Errorf("pages[0].Title = %q, want %q", pages[0].Title, "Page One")
	}
}

func TestListPages_WithoutProjectID(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/pages/" {
			t.Errorf("path = %q, want /pages/", r.URL.Path)
		}
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(struct {
			Items []Page `json:"items"`
		}{
			Items: []Page{
				{ExternalID: "page_a", Title: "All Page A"},
			},
		})
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	pages, err := client.ListPages("")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(pages) != 1 {
		t.Fatalf("len(pages) = %d, want 1", len(pages))
	}
	if pages[0].Title != "All Page A" {
		t.Errorf("pages[0].Title = %q, want %q", pages[0].Title, "All Page A")
	}
}

// --- GetPage ---

func TestGetPage_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/pages/page_xyz/" {
			t.Errorf("path = %q, want /pages/page_xyz/", r.URL.Path)
		}
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(Page{
			ExternalID: "page_xyz",
			Title:      "My Page",
			Details: &PageDetails{
				Content:  "Hello world",
				Filetype: "txt",
			},
		})
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	page, err := client.GetPage("page_xyz")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if page.Title != "My Page" {
		t.Errorf("Title = %q, want %q", page.Title, "My Page")
	}
	if page.Details == nil || page.Details.Content != "Hello world" {
		t.Errorf("Details.Content = %v, want 'Hello world'", page.Details)
	}
}

// --- CreatePage ---

func TestCreatePage_RequestBody(t *testing.T) {
	var receivedBody CreatePageRequest
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			t.Errorf("method = %q, want POST", r.Method)
		}
		if r.URL.Path != "/pages/" {
			t.Errorf("path = %q, want /pages/", r.URL.Path)
		}
		body, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(body, &receivedBody)
		w.WriteHeader(http.StatusCreated)
		_ = json.NewEncoder(w).Encode(Page{
			ExternalID: "page_new",
			Title:      "New Page",
		})
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	page, err := client.CreatePage("proj_abc", "New Page", "content here", "csv")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if receivedBody.ProjectID != "proj_abc" {
		t.Errorf("request project_id = %q, want %q", receivedBody.ProjectID, "proj_abc")
	}
	if receivedBody.Title != "New Page" {
		t.Errorf("request title = %q, want %q", receivedBody.Title, "New Page")
	}
	if receivedBody.Details == nil {
		t.Fatal("request details is nil")
	}
	if receivedBody.Details.Content != "content here" {
		t.Errorf("request content = %q, want %q", receivedBody.Details.Content, "content here")
	}
	if receivedBody.Details.Filetype != "csv" {
		t.Errorf("request filetype = %q, want %q", receivedBody.Details.Filetype, "csv")
	}
	if receivedBody.Details.SchemaVersion != 1 {
		t.Errorf("request schema_version = %d, want 1", receivedBody.Details.SchemaVersion)
	}
	if page.ExternalID != "page_new" {
		t.Errorf("ExternalID = %q, want %q", page.ExternalID, "page_new")
	}
}

// --- UpdatePageContent ---

func TestUpdatePageContent_GETThenPUT(t *testing.T) {
	var requestLog []string
	var putBody UpdatePageContentRequest

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestLog = append(requestLog, r.Method+" "+r.URL.Path)

		if r.Method == "GET" && r.URL.Path == "/pages/page_existing/" {
			w.WriteHeader(http.StatusOK)
			_ = json.NewEncoder(w).Encode(Page{
				ExternalID: "page_existing",
				Title:      "Existing Page",
				Details: &PageDetails{
					Content:  "old content",
					Filetype: "md",
				},
			})
			return
		}

		if r.Method == "PUT" && r.URL.Path == "/pages/page_existing/" {
			body, _ := io.ReadAll(r.Body)
			_ = json.Unmarshal(body, &putBody)
			w.WriteHeader(http.StatusOK)
			_ = json.NewEncoder(w).Encode(Page{
				ExternalID: "page_existing",
				Title:      "Existing Page",
			})
			return
		}

		t.Errorf("unexpected request: %s %s", r.Method, r.URL.Path)
		w.WriteHeader(http.StatusNotFound)
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	_, err := client.UpdatePageContent("page_existing", "appended content", "append")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Verify it makes GET then PUT
	if len(requestLog) != 2 {
		t.Fatalf("expected 2 requests, got %d: %v", len(requestLog), requestLog)
	}
	if requestLog[0] != "GET /pages/page_existing/" {
		t.Errorf("first request = %q, want 'GET /pages/page_existing/'", requestLog[0])
	}
	if requestLog[1] != "PUT /pages/page_existing/" {
		t.Errorf("second request = %q, want 'PUT /pages/page_existing/'", requestLog[1])
	}

	// Verify PUT body preserves existing title and filetype
	if putBody.Title != "Existing Page" {
		t.Errorf("PUT title = %q, want %q", putBody.Title, "Existing Page")
	}
	if putBody.Mode != "append" {
		t.Errorf("PUT mode = %q, want %q", putBody.Mode, "append")
	}
	if putBody.Details == nil {
		t.Fatal("PUT details is nil")
	}
	if putBody.Details.Filetype != "md" {
		t.Errorf("PUT filetype = %q, want %q (should preserve existing)", putBody.Details.Filetype, "md")
	}
	if putBody.Details.Content != "appended content" {
		t.Errorf("PUT content = %q, want %q", putBody.Details.Content, "appended content")
	}
}

func TestUpdatePageContent_DefaultsFiletypeToTxt(t *testing.T) {
	var putBody UpdatePageContentRequest

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "GET" {
			w.WriteHeader(http.StatusOK)
			// Page with no details (filetype is empty)
			_ = json.NewEncoder(w).Encode(Page{
				ExternalID: "page_nodetails",
				Title:      "No Details Page",
			})
			return
		}
		if r.Method == "PUT" {
			body, _ := io.ReadAll(r.Body)
			_ = json.Unmarshal(body, &putBody)
			w.WriteHeader(http.StatusOK)
			_ = json.NewEncoder(w).Encode(Page{ExternalID: "page_nodetails"})
			return
		}
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	_, err := client.UpdatePageContent("page_nodetails", "new content", "overwrite")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if putBody.Details.Filetype != "txt" {
		t.Errorf("filetype = %q, want 'txt' (default when existing is empty)", putBody.Details.Filetype)
	}
}

// --- DeletePage ---

func TestDeletePage_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "DELETE" {
			t.Errorf("method = %q, want DELETE", r.Method)
		}
		if r.URL.Path != "/pages/page_del/" {
			t.Errorf("path = %q, want /pages/page_del/", r.URL.Path)
		}
		w.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	err := client.DeletePage("page_del")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestDeletePage_NotFound(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"detail": "not found"}`))
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	err := client.DeletePage("page_nonexistent")
	if err == nil {
		t.Fatal("expected error for not found page")
	}
	if !strings.Contains(err.Error(), "404") {
		t.Errorf("error = %q, expected to contain '404'", err)
	}
}

// --- Nil result handling ---

func TestGet_NilResult(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`not json`))
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	// nil result should not attempt to decode
	err := client.Get("/test/", nil)
	if err != nil {
		t.Fatalf("unexpected error when result is nil: %v", err)
	}
}

func TestPost_NilResult(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	err := client.Post("/test/", map[string]string{"key": "value"}, nil)
	if err != nil {
		t.Fatalf("unexpected error when result is nil: %v", err)
	}
}

// --- Invalid JSON response ---

func TestGet_InvalidJSON(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`not valid json`))
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	var result struct{}
	err := client.Get("/test/", &result)
	if err == nil {
		t.Fatal("expected error for invalid JSON response")
	}
	if !strings.Contains(err.Error(), "failed to decode response") {
		t.Errorf("error = %q, expected 'failed to decode response'", err)
	}
}
