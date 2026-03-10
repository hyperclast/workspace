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

// TestDetectFiletype tests the CSV auto-detection logic
func TestDetectFiletype(t *testing.T) {
	tests := []struct {
		name        string
		content     string
		defaultType string
		expected    string
	}{
		// CSV detection - comma delimited
		{
			name:        "simple CSV with commas",
			content:     "name,age,city\nAlice,30,NYC\nBob,25,LA",
			defaultType: "txt",
			expected:    "csv",
		},
		{
			name:        "CSV header only",
			content:     "col1,col2,col3",
			defaultType: "txt",
			expected:    "csv",
		},
		{
			name:        "CSV with quoted fields",
			content:     `"Company","Revenue","Notes"\n"Acme, Inc","$1,000","Good"`,
			defaultType: "txt",
			expected:    "csv",
		},

		// CSV detection - tab delimited
		{
			name:        "simple TSV with tabs",
			content:     "name\tage\tcity\nAlice\t30\tNYC",
			defaultType: "txt",
			expected:    "csv",
		},
		{
			name:        "TSV header only",
			content:     "col1\tcol2\tcol3",
			defaultType: "txt",
			expected:    "csv",
		},

		// Non-CSV content
		{
			name:        "plain text no delimiters",
			content:     "Hello world this is plain text",
			defaultType: "txt",
			expected:    "txt",
		},
		{
			name:        "single column content",
			content:     "line1\nline2\nline3",
			defaultType: "txt",
			expected:    "txt",
		},
		{
			name:        "markdown content",
			content:     "# Heading\n\nSome text here.\n\n- Item 1\n- Item 2",
			defaultType: "md",
			expected:    "md",
		},
		{
			name:        "code content",
			content:     "func main() {\n\tfmt.Println(\"hello\")\n}",
			defaultType: "txt",
			expected:    "txt",
		},
		{
			name:        "log content",
			content:     "[INFO] Starting server\n[ERROR] Failed to connect\n[INFO] Retrying",
			defaultType: "txt",
			expected:    "txt",
		},

		// Edge cases
		{
			name:        "empty content",
			content:     "",
			defaultType: "txt",
			expected:    "txt",
		},
		{
			name:        "whitespace only",
			content:     "   \n   ",
			defaultType: "txt",
			expected:    "txt",
		},
		{
			name:        "single comma not enough (2 cols, needs 3+)",
			content:     "a,b",
			defaultType: "txt",
			expected:    "txt",
		},
		{
			name:        "two commas enough (3 cols)",
			content:     "a,b,c",
			defaultType: "txt",
			expected:    "csv",
		},
		{
			name:        "CRLF line endings",
			content:     "a,b,c\r\n1,2,3\r\n4,5,6",
			defaultType: "txt",
			expected:    "csv",
		},

		// Multi-line validation
		{
			name:        "majority of lines look like CSV",
			content:     "a,b,c\n1,2,3\n4,5,6\n7,8,9",
			defaultType: "txt",
			expected:    "csv",
		},
		{
			name:        "mixed content mostly not CSV",
			content:     "Hello world\nsome text\na,b,c\nmore text\neven more",
			defaultType: "txt",
			expected:    "txt",
		},

		// Real-world examples
		{
			name: "real CSV export",
			content: `company,primary_url,sectors,camp_class
Dots,http://weplaydots.com,Gaming,Playable Media
Roxy,http://www.roxydevice.com,"Hardware,Voice",Audio
Alpine.ai,https://alpine.ai,Bots,Audio`,
			defaultType: "txt",
			expected:    "csv",
		},
		{
			name: "build log output",
			content: `==> Building project...
[1/5] Compiling main.go
[2/5] Compiling utils.go
[3/5] Linking
Build complete in 2.3s`,
			defaultType: "txt",
			expected:    "txt",
		},
		{
			name: "test output",
			content: `=== RUN   TestSomething
--- PASS: TestSomething (0.00s)
=== RUN   TestAnother
--- FAIL: TestAnother (0.01s)
FAIL`,
			defaultType: "txt",
			expected:    "txt",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := detectFiletype(tt.content, tt.defaultType)
			if result != tt.expected {
				t.Errorf("detectFiletype() = %q, want %q", result, tt.expected)
			}
		})
	}
}

// TestDetectFiletypeLargeContent tests detection with large content
func TestDetectFiletypeLargeContent(t *testing.T) {
	// Generate large CSV content (more than 10 lines)
	var content string
	content = "col1,col2,col3\n"
	for i := 0; i < 100; i++ {
		content += "a,b,c\n"
	}

	result := detectFiletype(content, "txt")
	if result != "csv" {
		t.Errorf("Large CSV should be detected as csv, got %q", result)
	}
}

// TestDetectFiletypeOnlyScansFirstLines tests that we only scan first 10 lines
func TestDetectFiletypeOnlyScansFirstLines(t *testing.T) {
	// First 10 lines are CSV, rest is not (but we only check first 10)
	var content string
	for i := 0; i < 10; i++ {
		content += "a,b,c\n"
	}
	for i := 0; i < 100; i++ {
		content += "plain text line\n"
	}

	result := detectFiletype(content, "txt")
	if result != "csv" {
		t.Errorf("Should detect CSV based on first 10 lines, got %q", result)
	}
}

// TestDetectFiletypePreservesExplicitType tests that explicit type should be used
// (this is tested in integration, but documenting the expected behavior)
func TestDetectFiletypeDefaultTypePassthrough(t *testing.T) {
	// When content doesn't look like CSV, should return default
	result := detectFiletype("plain text", "md")
	if result != "md" {
		t.Errorf("Should return default type 'md' for non-CSV, got %q", result)
	}
}

// TestDetectFiletypeLog tests Apache/Nginx log format detection
func TestDetectFiletypeLog(t *testing.T) {
	tests := []struct {
		name        string
		content     string
		defaultType string
		expected    string
	}{
		// Apache/Nginx combined log format
		{
			name: "nginx combined log format",
			content: `192.168.1.1 - - [10/Oct/2023:13:55:36 -0700] "GET /index.html HTTP/1.1" 200 2326 "-" "Mozilla/5.0"
192.168.1.2 - - [10/Oct/2023:13:55:37 -0700] "POST /api/data HTTP/1.1" 201 512 "https://example.com" "curl/7.68.0"
10.0.0.1 - - [10/Oct/2023:13:55:38 -0700] "GET /favicon.ico HTTP/1.1" 404 0 "-" "Mozilla/5.0"`,
			defaultType: "txt",
			expected:    "log",
		},
		{
			name: "apache access log format",
			content: `203.0.113.50 - frank [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326 "http://www.example.com/start.html" "Mozilla/4.08"
203.0.113.51 - - [10/Oct/2000:13:55:37 -0700] "GET /test.html HTTP/1.0" 200 1234 "-" "Mozilla/4.08"
203.0.113.52 - - [10/Oct/2000:13:55:38 -0700] "POST /submit HTTP/1.0" 302 0 "-" "Mozilla/4.08"`,
			defaultType: "txt",
			expected:    "log",
		},
		{
			name: "various HTTP methods",
			content: `1.2.3.4 - - [01/Jan/2024:00:00:00 +0000] "GET /a HTTP/1.1" 200 100 "-" "test"
1.2.3.4 - - [01/Jan/2024:00:00:01 +0000] "POST /b HTTP/1.1" 201 100 "-" "test"
1.2.3.4 - - [01/Jan/2024:00:00:02 +0000] "PUT /c HTTP/1.1" 200 100 "-" "test"
1.2.3.4 - - [01/Jan/2024:00:00:03 +0000] "DELETE /d HTTP/1.1" 204 0 "-" "test"`,
			defaultType: "txt",
			expected:    "log",
		},
		{
			name: "HTTP/2 requests",
			content: `192.168.1.1 - - [01/Jan/2024:12:00:00 +0000] "GET /api/v2/data HTTP/2.0" 200 1234 "-" "Mozilla/5.0"
192.168.1.1 - - [01/Jan/2024:12:00:01 +0000] "POST /api/v2/submit HTTP/2.0" 201 567 "-" "Mozilla/5.0"
192.168.1.1 - - [01/Jan/2024:12:00:02 +0000] "GET /static/app.js HTTP/2.0" 200 89012 "-" "Mozilla/5.0"`,
			defaultType: "txt",
			expected:    "log",
		},

		// Not enough lines to be confident
		{
			name:        "single log line (not confident enough)",
			content:     `192.168.1.1 - - [10/Oct/2023:13:55:36 -0700] "GET /page HTTP/1.1" 200 1234 "-" "Mozilla/5.0"`,
			defaultType: "txt",
			expected:    "txt", // Only 1 line, need 3+ for confidence
		},
		{
			name: "two log lines (not confident enough)",
			content: `192.168.1.1 - - [10/Oct/2023:13:55:36 -0700] "GET /a HTTP/1.1" 200 100 "-" "Mozilla"
192.168.1.2 - - [10/Oct/2023:13:55:37 -0700] "GET /b HTTP/1.1" 200 100 "-" "Mozilla"`,
			defaultType: "txt",
			expected:    "txt", // Only 2 lines, need 3+ for confidence
		},

		// Mixed content (not enough log lines)
		{
			name: "mixed log and text lines",
			content: `192.168.1.1 - - [10/Oct/2023:13:55:36 -0700] "GET /page HTTP/1.1" 200 1234 "-" "Mozilla/5.0"
Some random text here
Another random line
192.168.1.2 - - [10/Oct/2023:13:55:37 -0700] "GET /page HTTP/1.1" 200 1234 "-" "Mozilla/5.0"
More random text`,
			defaultType: "txt",
			expected:    "txt", // Only 2/5 lines are log (40%), need 80%
		},

		// Not log format
		{
			name:        "plain text",
			content:     "Hello world\nThis is plain text\nNo log format here",
			defaultType: "txt",
			expected:    "txt",
		},
		{
			name: "application log (not HTTP access log)",
			content: `[INFO] 2023-10-10 13:55:36 Starting server
[ERROR] 2023-10-10 13:55:37 Failed to connect to database
[INFO] 2023-10-10 13:55:38 Retrying connection`,
			defaultType: "txt",
			expected:    "txt",
		},
		{
			name: "JSON logs (detected as CSV due to commas)",
			content: `{"timestamp":"2023-10-10T13:55:36Z","level":"info","message":"Starting"}
{"timestamp":"2023-10-10T13:55:37Z","level":"error","message":"Failed"}
{"timestamp":"2023-10-10T13:55:38Z","level":"info","message":"Retrying"}`,
			defaultType: "txt",
			expected:    "csv", // JSON has many commas, so CSV detection triggers
		},

		// Log takes priority over CSV
		{
			name: "log format has higher priority than CSV",
			content: `192.168.1.1 - - [10/Oct/2023:13:55:36 -0700] "GET /a,b,c HTTP/1.1" 200 100 "-" "Mozilla/5.0"
192.168.1.2 - - [10/Oct/2023:13:55:37 -0700] "GET /d,e,f HTTP/1.1" 200 100 "-" "Mozilla/5.0"
192.168.1.3 - - [10/Oct/2023:13:55:38 -0700] "GET /g,h,i HTTP/1.1" 200 100 "-" "Mozilla/5.0"`,
			defaultType: "txt",
			expected:    "log", // Should be detected as log, not CSV
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := detectFiletype(tt.content, tt.defaultType)
			if result != tt.expected {
				t.Errorf("detectFiletype() = %q, want %q", result, tt.expected)
			}
		})
	}
}

// TestLooksLikeLogLine tests the log line detection helper
func TestLooksLikeLogLine(t *testing.T) {
	tests := []struct {
		name     string
		line     string
		expected bool
	}{
		// Valid log lines
		{
			name:     "combined format",
			line:     `192.168.1.1 - - [10/Oct/2023:13:55:36 -0700] "GET /index.html HTTP/1.1" 200 2326 "-" "Mozilla/5.0"`,
			expected: true,
		},
		{
			name:     "common format",
			line:     `192.168.1.1 - - [10/Oct/2023:13:55:36 -0700] "GET /page HTTP/1.1" 200 1234`,
			expected: true,
		},
		{
			name:     "POST request",
			line:     `10.0.0.1 - - [01/Jan/2024:00:00:00 +0000] "POST /api/data HTTP/1.1" 201 512 "-" "curl"`,
			expected: true,
		},
		{
			name:     "HTTP/2",
			line:     `1.2.3.4 - - [01/Jan/2024:00:00:00 +0000] "GET /test HTTP/2.0" 200 100 "-" "test"`,
			expected: true,
		},

		// Invalid log lines
		{
			name:     "plain text",
			line:     "Hello world this is plain text",
			expected: false,
		},
		{
			name:     "too short",
			line:     "1.2.3.4 GET /",
			expected: false,
		},
		{
			name:     "no IP at start",
			line:     `abc - - [10/Oct/2023:13:55:36 -0700] "GET /page HTTP/1.1" 200 1234`,
			expected: false,
		},
		{
			name:     "no timestamp brackets",
			line:     `192.168.1.1 - - 10/Oct/2023:13:55:36 "GET /page HTTP/1.1" 200 1234`,
			expected: false,
		},
		{
			name:     "no HTTP method",
			line:     `192.168.1.1 - - [10/Oct/2023:13:55:36 -0700] "/page HTTP/1.1" 200 1234`,
			expected: false,
		},
		{
			name:     "no HTTP version",
			line:     `192.168.1.1 - - [10/Oct/2023:13:55:36 -0700] "GET /page" 200 1234`,
			expected: false,
		},
		{
			name:     "application log",
			line:     "[INFO] 2023-10-10 Starting server on port 8080",
			expected: false,
		},
		{
			name:     "JSON log",
			line:     `{"timestamp":"2023-10-10T13:55:36Z","level":"info","message":"Starting"}`,
			expected: false,
		},
		{
			name:     "empty line",
			line:     "",
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := looksLikeLogLine(tt.line)
			if result != tt.expected {
				t.Errorf("looksLikeLogLine() = %v, want %v", result, tt.expected)
			}
		})
	}
}

// TestContainsHTTPVersion tests the HTTP version detection helper
func TestContainsHTTPVersion(t *testing.T) {
	tests := []struct {
		line     string
		expected bool
	}{
		{`"GET /page HTTP/1.1" 200`, true},
		{`"GET /page HTTP/1.0" 200`, true},
		{`"GET /page HTTP/2.0" 200`, true},
		{`"GET /page" 200`, false},
		{"plain text", false},
		{"", false},
		{"short", false},  // shorter than 6 chars
		{"HTTP/1", true},  // exactly 6 chars
		{"XHTTP/", false}, // 6 chars but not matching
		{"abcde", false},  // 5 chars (less than 6)
	}

	for _, tt := range tests {
		result := containsHTTPVersion(tt.line)
		if result != tt.expected {
			t.Errorf("containsHTTPVersion(%q) = %v, want %v", tt.line, result, tt.expected)
		}
	}
}

// --- Content validation tests (T3) ---

func TestValidateTextContent(t *testing.T) {
	tests := []struct {
		name    string
		data    []byte
		wantErr string
	}{
		{
			name:    "valid UTF-8 ASCII",
			data:    []byte("Hello, world!"),
			wantErr: "",
		},
		{
			name:    "valid UTF-8 multibyte",
			data:    []byte("こんにちは世界 🌍"),
			wantErr: "",
		},
		{
			name:    "empty content",
			data:    []byte{},
			wantErr: "",
		},
		{
			name:    "null bytes detected",
			data:    []byte("hello\x00world"),
			wantErr: "binary data detected",
		},
		{
			name:    "null byte at start",
			data:    []byte("\x00hello"),
			wantErr: "binary data detected",
		},
		{
			name:    "invalid UTF-8 sequence",
			data:    []byte{0xff, 0xfe, 0x65},
			wantErr: "invalid text encoding",
		},
		{
			name:    "BOM-prefixed UTF-8 is valid",
			data:    []byte("\xef\xbb\xbfHello BOM"),
			wantErr: "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := validateTextContent(tt.data)
			if tt.wantErr == "" {
				if err != nil {
					t.Errorf("unexpected error: %v", err)
				}
			} else {
				if err == nil {
					t.Fatalf("expected error containing %q, got nil", tt.wantErr)
				}
				if !strings.Contains(err.Error(), tt.wantErr) {
					t.Errorf("error = %q, want to contain %q", err, tt.wantErr)
				}
			}
		})
	}
}

// --- File reading and validation tests (T4) ---

func TestReadAndValidateFile(t *testing.T) {
	t.Run("valid file", func(t *testing.T) {
		dir := t.TempDir()
		path := filepath.Join(dir, "valid.txt")
		if err := os.WriteFile(path, []byte("Hello, valid content"), 0600); err != nil {
			t.Fatal(err)
		}

		content, err := readAndValidateFile(path)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if content != "Hello, valid content" {
			t.Errorf("content = %q, want %q", content, "Hello, valid content")
		}
	})

	t.Run("file too large", func(t *testing.T) {
		dir := t.TempDir()
		path := filepath.Join(dir, "large.txt")
		// Create file that exceeds maxContentSize (10 MB)
		data := make([]byte, maxContentSize+1)
		for i := range data {
			data[i] = 'a'
		}
		if err := os.WriteFile(path, data, 0600); err != nil {
			t.Fatal(err)
		}

		_, err := readAndValidateFile(path)
		if err == nil {
			t.Fatal("expected error for file exceeding max size")
		}
		if !strings.Contains(err.Error(), "content too large") {
			t.Errorf("error = %q, want to contain 'content too large'", err)
		}
	})

	t.Run("empty file", func(t *testing.T) {
		dir := t.TempDir()
		path := filepath.Join(dir, "empty.txt")
		if err := os.WriteFile(path, []byte(""), 0600); err != nil {
			t.Fatal(err)
		}

		_, err := readAndValidateFile(path)
		if err == nil {
			t.Fatal("expected error for empty file")
		}
		if !strings.Contains(err.Error(), "no content provided") {
			t.Errorf("error = %q, want to contain 'no content provided'", err)
		}
	})

	t.Run("missing file", func(t *testing.T) {
		_, err := readAndValidateFile("/tmp/nonexistent-hyperclast-test-file.txt")
		if err == nil {
			t.Fatal("expected error for missing file")
		}
	})

	t.Run("file with null bytes", func(t *testing.T) {
		dir := t.TempDir()
		path := filepath.Join(dir, "binary.bin")
		if err := os.WriteFile(path, []byte("hello\x00world"), 0600); err != nil {
			t.Fatal(err)
		}

		_, err := readAndValidateFile(path)
		if err == nil {
			t.Fatal("expected error for binary data")
		}
		if !strings.Contains(err.Error(), "binary data detected") {
			t.Errorf("error = %q, want to contain 'binary data detected'", err)
		}
	})

	t.Run("file exactly at max size", func(t *testing.T) {
		dir := t.TempDir()
		path := filepath.Join(dir, "exact.txt")
		data := make([]byte, maxContentSize)
		for i := range data {
			data[i] = 'x'
		}
		if err := os.WriteFile(path, data, 0600); err != nil {
			t.Fatal(err)
		}

		content, err := readAndValidateFile(path)
		if err != nil {
			t.Fatalf("unexpected error for file at exact max size: %v", err)
		}
		if len(content) != maxContentSize {
			t.Errorf("content length = %d, want %d", len(content), maxContentSize)
		}
	})
}

// --- Metadata tests (T5) ---

func TestAppendMetadata(t *testing.T) {
	t.Run("without source", func(t *testing.T) {
		pageSource = ""
		result := appendMetadata("some content")
		if !strings.HasPrefix(result, "some content") {
			t.Errorf("should start with original content")
		}
		if !strings.Contains(result, "Captured by Hyperclast CLI") {
			t.Error("should contain CLI attribution")
		}
		if !strings.Contains(result, "Time:") {
			t.Error("should contain timestamp")
		}
		if strings.Contains(result, "Source:") {
			t.Error("should not contain Source when pageSource is empty")
		}
		if !strings.Contains(result, "---") {
			t.Error("should contain metadata delimiters")
		}
	})

	t.Run("with source", func(t *testing.T) {
		pageSource = "make build"
		defer func() { pageSource = "" }()

		result := appendMetadata("build output")
		if !strings.Contains(result, "Source: make build") {
			t.Error("should contain Source when pageSource is set")
		}
	})

	t.Run("includes hostname when available", func(t *testing.T) {
		pageSource = ""
		result := appendMetadata("test")
		hostname, err := os.Hostname()
		if err == nil && hostname != "" {
			if !strings.Contains(result, "Host: "+hostname) {
				t.Errorf("should contain Host: %s", hostname)
			}
		}
	})

	t.Run("includes directory", func(t *testing.T) {
		pageSource = ""
		result := appendMetadata("test")
		cwd, err := os.Getwd()
		if err == nil && cwd != "" {
			if !strings.Contains(result, "Directory: "+cwd) {
				t.Errorf("should contain Directory: %s", cwd)
			}
		}
	})
}

// --- generateDefaultTitle tests (T7) ---

func TestGenerateDefaultTitle(t *testing.T) {
	title := generateDefaultTitle()
	if title == "" {
		t.Fatal("title should not be empty")
	}
	// The format is "Jan 2, 2006 at 3:04 PM" so it should contain " at " and either AM or PM
	if !strings.Contains(title, " at ") {
		t.Errorf("title %q should contain ' at '", title)
	}
	if !strings.Contains(title, "AM") && !strings.Contains(title, "PM") {
		t.Errorf("title %q should contain AM or PM", title)
	}
	// Should contain a comma (e.g. "Jan 2, 2026")
	if !strings.Contains(title, ",") {
		t.Errorf("title %q should contain comma in date", title)
	}
}

// --- resetPageFlags helper for page command tests ---

func resetPageFlags() {
	pageProjectID = ""
	pageTitle = ""
	pageFile = ""
	pageFiletype = "txt"
	pageMeta = false
	pageSource = ""
	pageDeleteForce = false
	pageListProjectID = ""
	outputFmt = "text"
	quiet = false
	stdinTempPath = ""
}

// --- page delete tests (T9) ---

func TestPageDelete_NotAuthenticated(t *testing.T) {
	resetPageFlags()
	cfg = &config.Config{Token: ""}

	err := pageDeleteCmd.RunE(pageDeleteCmd, []string{"page_xyz"})
	if err == nil {
		t.Fatal("expected error for unauthenticated user")
	}
	if !strings.Contains(err.Error(), "not authenticated") {
		t.Errorf("unexpected error: %s", err)
	}
}

func TestPageDelete_Force(t *testing.T) {
	resetPageFlags()

	var deletedPath string
	requestCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestCount++
		if r.Method == "GET" {
			w.WriteHeader(http.StatusOK)
			_ = json.NewEncoder(w).Encode(api.Page{
				ExternalID: "page_xyz",
				Title:      "Test Page",
			})
			return
		}
		if r.Method == "DELETE" {
			deletedPath = r.URL.Path
			w.WriteHeader(http.StatusNoContent)
			return
		}
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL: server.URL,
		Token:  "test-token",
	}
	pageDeleteForce = true

	err := pageDeleteCmd.RunE(pageDeleteCmd, []string{"page_xyz"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if deletedPath != "/pages/page_xyz/" {
		t.Errorf("deleted path = %q, want /pages/page_xyz/", deletedPath)
	}
	if requestCount != 2 {
		t.Errorf("expected 2 requests (GET + DELETE), got %d", requestCount)
	}
}

func TestPageDelete_JSONOutput(t *testing.T) {
	resetPageFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "GET" {
			w.WriteHeader(http.StatusOK)
			_ = json.NewEncoder(w).Encode(api.Page{
				ExternalID: "page_xyz",
				Title:      "Test Page",
			})
			return
		}
		if r.Method == "DELETE" {
			w.WriteHeader(http.StatusNoContent)
			return
		}
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL: server.URL,
		Token:  "test-token",
	}
	pageDeleteForce = true
	outputFmt = "json"

	// Capture stdout
	oldStdout := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	err := pageDeleteCmd.RunE(pageDeleteCmd, []string{"page_xyz"})

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
	if result["deleted"] != true {
		t.Errorf("deleted = %v, want true", result["deleted"])
	}
	if result["external_id"] != "page_xyz" {
		t.Errorf("external_id = %v, want page_xyz", result["external_id"])
	}
}

func TestPageDelete_PageNotFound(t *testing.T) {
	resetPageFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"detail": "not found"}`))
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL: server.URL,
		Token:  "test-token",
	}
	pageDeleteForce = true

	err := pageDeleteCmd.RunE(pageDeleteCmd, []string{"page_nonexistent"})
	if err == nil {
		t.Fatal("expected error for not found page")
	}
	if !strings.Contains(err.Error(), "failed to get page") {
		t.Errorf("error = %q, expected to contain 'failed to get page'", err)
	}
}

func TestPageDelete_QuietMode(t *testing.T) {
	resetPageFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "GET" {
			w.WriteHeader(http.StatusOK)
			_ = json.NewEncoder(w).Encode(api.Page{
				ExternalID: "page_xyz",
				Title:      "Test Page",
			})
			return
		}
		if r.Method == "DELETE" {
			w.WriteHeader(http.StatusNoContent)
			return
		}
	}))
	defer server.Close()

	cfg = &config.Config{
		APIURL: server.URL,
		Token:  "test-token",
	}
	pageDeleteForce = true
	quiet = true

	// Capture stdout
	oldStdout := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	err := pageDeleteCmd.RunE(pageDeleteCmd, []string{"page_xyz"})

	_ = w.Close()
	os.Stdout = oldStdout

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	output, _ := io.ReadAll(r)
	// Quiet mode for delete should produce no output (just returns nil)
	if len(strings.TrimSpace(string(output))) != 0 {
		t.Errorf("expected no output in quiet mode, got %q", string(output))
	}
}

// --- page get tests ---

func TestPageGet_NotAuthenticated(t *testing.T) {
	resetPageFlags()
	cfg = &config.Config{Token: ""}

	err := pageGetCmd.RunE(pageGetCmd, []string{"page_xyz"})
	if err == nil {
		t.Fatal("expected error for unauthenticated user")
	}
	if !strings.Contains(err.Error(), "not authenticated") {
		t.Errorf("unexpected error: %s", err)
	}
}

func TestPageGet_OutputsContent(t *testing.T) {
	resetPageFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(api.Page{
			ExternalID: "page_xyz",
			Title:      "My Page",
			Details: &api.PageDetails{
				Content: "Hello page content",
			},
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

	err := pageGetCmd.RunE(pageGetCmd, []string{"page_xyz"})

	_ = w.Close()
	os.Stdout = oldStdout

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	output, _ := io.ReadAll(r)
	if string(output) != "Hello page content" {
		t.Errorf("output = %q, want %q", string(output), "Hello page content")
	}
}

func TestPageGet_JSONOutput(t *testing.T) {
	resetPageFlags()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(api.Page{
			ExternalID: "page_xyz",
			Title:      "My Page",
			Details: &api.PageDetails{
				Content: "content",
			},
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

	err := pageGetCmd.RunE(pageGetCmd, []string{"page_xyz"})

	_ = w.Close()
	os.Stdout = oldStdout

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	output, _ := io.ReadAll(r)
	var page api.Page
	if err := json.Unmarshal(output, &page); err != nil {
		t.Fatalf("output is not valid JSON: %v\nraw: %s", err, string(output))
	}
	if page.ExternalID != "page_xyz" {
		t.Errorf("external_id = %q, want page_xyz", page.ExternalID)
	}
}
